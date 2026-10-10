import math
import random
import pygame
import pymunk
from shared.const import (
  ARM_R, ITEM_GRAB_DIST, ITEM_TYPES,
  CUBE_FILL, CUBE_EDGE, CUBE_EDGE_W, CUBE_FRICTION, CUBE_ELASTICITY, CUBE_LINEAR_DAMPING,
  SODA_W, SODA_H, SODA_BLUE, SODA_WHITE, SODA_STAMINA, LAYER_ITEM,
  PEG_R, PEG_FILL, PEG_EDGE, PEG_EDGE_W,
  REBAR_W, REBAR_H, REBAR_FILL, REBAR_EDGE, REBAR_EDGE_W, REBAR_GRAB_R,
  REBAR_SHOOT_V, REBAR_RECOIL_AIR, REBAR_RECOIL_GROUND, REBAR_STUCK_POINTS, JUMP_V,
)
from shared.physics_util import has_ground_contact


def _corners(pos, angle, hw, hh):
  c, sn = math.cos(angle), math.sin(angle)
  return [
    (pos[0] + lx * c - ly * sn, pos[1] + lx * sn + ly * c)
    for lx, ly in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))
  ]


def _band(pos, angle, lx0, ly0, lx1, ly1):
  c, sn = math.cos(angle), math.sin(angle)
  return [
    (pos[0] + lx * c - ly * sn, pos[1] + lx * sn + ly * c)
    for lx, ly in ((lx0, ly0), (lx1, ly0), (lx1, ly1), (lx0, ly1))
  ]


def _blit_bands(screen, cam, bands):
  # <STRANGE>#334 bands = [(world_pts, color_or_rgba, width)]; width 0 fills, >0 strokes; single SRCALPHA when alpha needed
  needs_alpha = any(len(c) == 4 and c[3] < 255 for _, c, _ in bands)
  if not needs_alpha:
    for pts, color, w in bands:
      pygame.draw.polygon(screen, color, [cam.to_screen(x, y) for x, y in pts], w)
    return
  all_pts = [cam.to_screen(x, y) for pts, _, _ in bands for x, y in pts]
  xs = [q[0] for q in all_pts]
  ys = [q[1] for q in all_pts]
  x0, y0 = int(min(xs)) - 2, int(min(ys)) - 2
  sw = int(max(xs)) - x0 + 4
  sh = int(max(ys)) - y0 + 4
  surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
  for pts, color, w in bands:
    local = [(cam.to_screen(x, y)[0] - x0, cam.to_screen(x, y)[1] - y0) for x, y in pts]
    pygame.draw.polygon(surf, color, local, w)
  screen.blit(surf, (x0, y0))


class Item:
  layer = LAYER_ITEM
  # <STRANGE>#702 sfx name played on pickup; each subclass overrides
  pickup_sound = None
  # <STRANGE>#744 sfx name played when use() consumes this item; None = silent
  use_sound = None

  def on_use(self, player, hand):
    # <STRANGE>#521 default: return False to fall through to use() (consume/shake)
    return False
  # <NOTE>#461 local-space offset from body center to the grab point; when held, body.position = arm.pos - R(angle) * hold_offset
  hold_offset = (0, 0)
  # <NOTE>#462 override when max(w,h) is a bad reach metric (long thin items); None means use max/2
  grab_radius = None
  # <NOTE>#481 per-hand target angle while held; None means 0 (upright) for both hands
  hand_angle = None

  def __init__(self, space, pos, w, h):
    self.space = space
    self.w = w
    self.h = h
    self.held_by = None
    self.throw_vel = (0, 0)
    self.mass = 1
    self.moment = pymunk.moment_for_box(self.mass, (w, h))
    self.body = pymunk.Body(self.mass, self.moment)
    self.body.position = pos
    shape = pymunk.Poly.create_box(self.body, (w, h))
    # <STRANGE>#246 item collides only with floor/platform (0b10); player is 0b01/0b100, peg will get 0b100000
    shape.filter = pymunk.ShapeFilter(categories=0b1000, mask=0b10 | 0b1000)
    # <STRANGE>#263 high friction stops sliding forever; elasticity gives a small bounce on impact
    shape.friction = CUBE_FRICTION
    shape.elasticity = CUBE_ELASTICITY
    self.shape = shape
    # <STRANGE>#376 linear damping bleeds off energy so items settle instead of drifting; does not affect held (kinematic) state
    self.body.linear_damping = CUBE_LINEAR_DAMPING
    space.add(self.body, shape)
    # <STRANGE>#713 sound manager ref, attached by Level after creation
    self.sound = None
    self._hit_cd = 0.0

  def destroy(self):
    # <STRANGE>#295 destroy only removes physics; caller clears held_by on player side
    self.space.remove(self.body, self.shape)


  def post_step(self, cam=None):
    # <STRANGE>#653 ignore kinematic items
    if self.body.body_type != pymunk.Body.DYNAMIC:
      return
    # <STRANGE>#721 bias clamp: upward vy while touching ground is solver artifact
    if self.body.velocity.y > 0 and has_ground_contact(self.body):
      self.body.velocity = (self.body.velocity.x, 0.0)
    # <STRANGE>#717 impact sfx only for items currently visible on screen
    if self._hit_cd > 0:
      self._hit_cd -= 1 / 120
    if self.sound is not None and self._hit_cd <= 0 and cam is not None and _on_screen(self, cam):
      hit = [False]
      def cb(arb, _):
        if hit[0] or not arb.is_first_contact:
          return True
        a, b = arb.shapes
        if a.body is self.body:
          other = b
        elif b.body is self.body:
          other = a
        else:
          return True
        if other.filter.categories & 0b10:
          hit[0] = True
          return False
        return True
      self.body.each_arbiter(cb, None)
      if hit[0]:
        # <STRANGE>#718 volume = 1/3 of player's half, per request
        self.sound.play("hit", volume=0.05)
        self._hit_cd = 0.08

  def radius(self):
    return max(self.w, self.h) / 2

  def grab_dist(self):
    r = self.grab_radius if self.grab_radius is not None else self.radius()
    return ARM_R + r + ITEM_GRAB_DIST

  def hold(self, hand):
    self.held_by = hand
    self.body.body_type = pymunk.Body.KINEMATIC
    self.body.velocity = (0, 0)
    # <STRANGE>#544 while held, mask=0: kinematic position is set every frame and may end up inside static geometry;
    # <STRANGE>#544 solver would register deep penetration contacts and later release impulse spikes
    self.shape.filter = pymunk.ShapeFilter(categories=0b1000, mask=0)
    # <STRANGE>#261 kinematic bodies reject mass/moment assignment; ignored anyway

  def release(self, vel):
    self.held_by = None
    self.body.body_type = pymunk.Body.DYNAMIC
    self.body.mass = self.mass
    self.body.moment = self.moment
    self.body.velocity = vel
    # <STRANGE>#545 restore collision mask on release; item becomes physical again
    self.shape.filter = pymunk.ShapeFilter(categories=0b1000, mask=0b10 | 0b1000)

  # <STRANGE>#412 center_anim items play the "fly to player center" fx on consume; base off
  center_anim = False

  def use(self):
    # <STRANGE>#303 returns (consumed, spawn_type, stamina_gain); None spawn just vanishes
    return (False, None, 0)

  def draw(self, screen, cam):
    self.draw_at(screen, cam, self.body.position, self.body.angle, 255, 1.0)

  def draw_at(self, screen, cam, pos, angle, alpha, scale):
    pass


class CubeItem(Item):
  pickup_sound = "pickup_cube"
  use_sound = "open_cube"

  def __init__(self, space, pos, contents=None):
    # <STRANGE>#292 cube size fixed; no JSON override
    super().__init__(space, pos, 30, 30)
    # <NOTE>#566 contents is a list of {"type", "count"}; None means fall back to "any other type"
    self.contents = contents

  def use(self):
    # <STRANGE>#567 weighted roll if contents provided; entry spec carries contents so nested cubes work
    if self.contents:
      total = sum(e.get("count", 0) for e in self.contents)
      if total > 0:
        r = random.uniform(0, total)
        acc = 0.0
        for e in self.contents:
          acc += e.get("count", 0)
          if r <= acc:
            t = e.get("type")
            if t is None or t == "nothing":
              return (True, None, 0)
            spec = {"type": t}
            for k, v in e.items():
              if k not in ("type", "count"):
                spec[k] = v
            return (True, spec, 0)
    # <STRANGE>#571 default loot: soda weight 2, nothing weight 1 -> ~2/3 soda, 1/3 empty
    total = 3
    r = random.uniform(0, total)
    if r <= 2:
      return (True, {"type": "soda"}, 0)
    return (True, None, 0)

  def draw_at(self, screen, cam, pos, angle, alpha, scale):
    sc = cam.scale * scale
    hw, hh = self.w / 2 * scale, self.h / 2 * scale
    pts = _corners(pos, angle, hw, hh)
    fill = (*CUBE_FILL, alpha) if alpha < 255 else CUBE_FILL
    edge = (*CUBE_EDGE, alpha) if alpha < 255 else CUBE_EDGE
    w_edge = max(1, int(CUBE_EDGE_W * sc))
    _blit_bands(screen, cam, [(pts, fill, 0), (pts, edge, w_edge)])


class SodaItem(Item):
  center_anim = True
  pickup_sound = "pickup_soda"

  def __init__(self, space, pos):
    super().__init__(space, pos, SODA_W, SODA_H)

  def use(self):
    return (True, None, SODA_STAMINA)

  def draw_at(self, screen, cam, pos, angle, alpha, scale):
    hw, hh = self.w / 2 * scale, self.h / 2 * scale
    blue = (*SODA_BLUE, alpha) if alpha < 255 else SODA_BLUE
    white = (*SODA_WHITE, alpha) if alpha < 255 else SODA_WHITE
    bands = [
      (_band(pos, angle, -hw, hh * 0.5, hw, hh), blue, 0),
      (_band(pos, angle, -hw, -hh * 0.5, hw, hh * 0.5), white, 0),
      (_band(pos, angle, -hw, -hh, hw, -hh * 0.5), blue, 0),
    ]
    _blit_bands(screen, cam, bands)


class RebarItem(Item):
  pickup_sound = "pickup_rebar"
  # <STRANGE>#513 hold offset toward the near end: local -Y is the end facing away from cursor
  hold_offset = (0, REBAR_H / 6)
  grab_radius = REBAR_GRAB_R
  # <STRANGE>#480 base angle per hand: -pi/2 for left (index 0), +pi/2 for right (index 1); item's local +Y ends up horizontal
  # <STRANGE>#491 per-hand hold angle: left hand rotates +90deg, right -90deg
  hand_angle = (-math.pi / 2, math.pi / 2)

  def __init__(self, space, pos):
    super().__init__(space, pos, REBAR_W, REBAR_H)
    self.stuck = False
    self.flying = False
    # <STRANGE>#535 player grab loop increments obj.grab_count for peg-style targets; stuck rebar joins that list
    self.grab_count = 0

  def on_use(self, player, hand):
    # <STRANGE>#516 "release" tells Player to drop it and lock the hand; False falls through to normal use()
    if self.stuck or self.flying:
      return False
    # <STRANGE>#534 shot direction is local -Y in world space (opposite of hold_offset axis) so it aligns with the cursor
    a = self.body.angle
    dx = math.sin(a)
    dy = -math.cos(a)
    recoil = REBAR_RECOIL_AIR if not player._is_grounded() else REBAR_RECOIL_GROUND
    vx, vy = player.body.velocity
    player.body.velocity = (vx - dx * JUMP_V * recoil, vy - dy * JUMP_V * recoil)
    self.body.body_type = pymunk.Body.DYNAMIC
    self.body.mass = self.mass
    self.body.moment = self.moment
    self.body.velocity = (dx * REBAR_SHOOT_V, dy * REBAR_SHOOT_V)
    self.shape.filter = pymunk.ShapeFilter(categories=0b1000, mask=0b10)
    self.flying = True
    # <STRANGE>#530 release from hand: Level.drawables filters held_by; forgetting this hides the flying rebar
    self.held_by = None
    # <STRANGE>#748 throw sfx; fires on Q/E release
    if self.sound is not None:
      self.sound.play("rebar_throw")
    return "release"

  def grab_points(self):
    # <STRANGE>#519 stuck rebar exposes anchors along its length; free one uses its center
    if not self.stuck:
      return [(self.body.position, pymunk.Vec2d(0, 0))]
    a = self.body.angle
    c, sn = math.cos(a), math.sin(a)
    n = REBAR_STUCK_POINTS
    half = self.h / 2 - REBAR_W
    pts = []
    for k in range(n):
      t = (k / (n - 1)) * 2 - 1
      ly = t * half
      wx = self.body.position.x - ly * sn
      wy = self.body.position.y + ly * c
      pts.append((pymunk.Vec2d(wx, wy), pymunk.Vec2d(0, ly)))
    return pts

  def stick(self, cam=None):
    # <STRANGE>#520 freeze in place; mask=0 stops all collisions
    self.flying = False
    self.stuck = True
    self.body.body_type = pymunk.Body.STATIC
    self.body.velocity = (0, 0)
    self.shape.filter = pymunk.ShapeFilter(categories=0b1000, mask=0)
    # <STRANGE>#749 sticking sfx, but only if the rebar is on screen when it lands
    if self.sound is not None and cam is not None and _on_screen(self, cam):
      self.sound.play("rebar_stick")

  def draw_at(self, screen, cam, pos, angle, alpha, scale):
    sc = cam.scale * scale
    hw, hh = self.w / 2 * scale, self.h / 2 * scale
    pts = _corners(pos, angle, hw, hh)
    fill = (*REBAR_FILL, alpha) if alpha < 255 else REBAR_FILL
    edge = (*REBAR_EDGE, alpha) if alpha < 255 else REBAR_EDGE
    w_edge = max(1, int(REBAR_EDGE_W * sc))
    _blit_bands(screen, cam, [(pts, fill, 0), (pts, edge, w_edge)])


def _on_screen(item, cam):
  # <STRANGE>#717 cheap axis check against camera viewport
  sx, sy = cam.to_screen(item.body.position.x, item.body.position.y)
  vw = cam.w * cam.scale
  vh = cam.h * cam.scale
  return -50 <= sx <= vw + 50 and -50 <= sy <= vh + 50


class PortablePegItem(Item):
  # <STRANGE>#778 carryable peg: same look and size as a static Peg, but a plain item (no grapplable hooks)
  def __init__(self, space, pos):
    super().__init__(space, pos, PEG_R * 2, PEG_R * 2)

  def draw_at(self, screen, cam, pos, angle, alpha, scale):
    sc = cam.scale * scale
    x, y = cam.to_screen(pos[0], pos[1])
    r = max(1, int(PEG_R * sc))
    if alpha < 255:
      surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
      pygame.draw.circle(surf, (*PEG_FILL, alpha), (r, r), r)
      pygame.draw.circle(surf, (*PEG_EDGE, alpha), (r, r), r, max(1, int(PEG_EDGE_W * sc)))
      screen.blit(surf, (int(x) - r, int(y) - r))
    else:
      pygame.draw.circle(screen, PEG_FILL, (int(x), int(y)), r)
      pygame.draw.circle(screen, PEG_EDGE, (int(x), int(y)), r, max(1, int(PEG_EDGE_W * sc)))


def make_item(space, spec):
  t = spec.get("type", "cube")
  pos = (spec["x"], spec["y"])
  if t == "soda":
    return SodaItem(space, pos)
  if t == "rebar":
    return RebarItem(space, pos)
  if t == "peg":
    return PortablePegItem(space, pos)
  if t == "cube":
    return CubeItem(space, pos, contents=spec.get("contents"))
  return CubeItem(space, pos)
