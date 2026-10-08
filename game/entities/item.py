import math
import random
import pygame
import pymunk
from shared.const import (
  ARM_R, ITEM_GRAB_DIST, ITEM_TYPES,
  CUBE_FILL, CUBE_EDGE, CUBE_EDGE_W, CUBE_FRICTION, CUBE_ELASTICITY, CUBE_LINEAR_DAMPING,
  SODA_W, SODA_H, SODA_BLUE, SODA_WHITE, SODA_STAMINA,
)


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

  def destroy(self):
    # <STRANGE>#295 destroy only removes physics; caller clears held_by on player side
    self.space.remove(self.body, self.shape)

  def radius(self):
    return max(self.w, self.h) / 2

  def grab_dist(self):
    return ARM_R + self.radius() + ITEM_GRAB_DIST

  def hold(self, hand):
    self.held_by = hand
    self.body.body_type = pymunk.Body.KINEMATIC
    self.body.velocity = (0, 0)
    # <STRANGE>#261 kinematic bodies reject mass/moment assignment; ignored anyway

  def release(self, vel):
    self.held_by = None
    self.body.body_type = pymunk.Body.DYNAMIC
    self.body.mass = self.mass
    self.body.moment = self.moment
    self.body.velocity = vel

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
  def __init__(self, space, pos):
    # <STRANGE>#292 cube size fixed; no JSON override
    super().__init__(space, pos, 30, 30)

  def use(self):
    # <STRANGE>#297 spawn a random different type; if none exists yet, just consume
    others = [t for t in ITEM_TYPES if t != "cube"]
    if not others:
      return (True, None, 0)
    return (True, random.choice(others), 0)

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


def make_item(space, spec):
  t = spec.get("type", "cube")
  pos = (spec["x"], spec["y"])
  if t == "soda":
    return SodaItem(space, pos)
  return CubeItem(space, pos)
