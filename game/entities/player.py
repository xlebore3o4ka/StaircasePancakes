import math
import random
import pygame
import pymunk
from shared.const import BODY_R, ARM_R, ARM_DX, JUMP_V, PEG_R, ITEM_OFFSET, ITEM_USE_SHAKE_TIME, ITEM_USE_SHAKE_AMP, ARM_HOLD_ALPHA, ARM_HOLD_SCALE, THROW_MAX_SPEED, THROW_SMOOTH_FRAMES, SPAWN_BOUNCE_V
from shared.smooth import smooth, per_sec

ARM_MASS = 0.1
ARM_MIN_ANG = math.radians(15)
ARM_LERP = 0.6
ARM_LERP_GRAB = 0.9
ARM_LERP_RETURN = 0.3
REEL_SPEED = 25
PRESS_R = 15
MOVE_ACC = 2000
AIR_DRAG = 0.005
GROUND_DRAG = 0.25
PULL_ACC = 8000
PULL_RANGE = 400
MAX_WALK_VX = 400
STAMINA_MAX = 100
STAMINA_HOLD_DRAIN = 0.2
STAMINA_JUMP_COST = 20
STAMINA_REGEN = 0.08
STAMINA_LOW_THRESH = 50
STAMINA_LOW_MUL = 1.5
STAMINA_GRAB_MIN = 15
SHAKE_MAX = 2

class Player:
  def __init__(self, space, pos):
    self.space = space
    self.body = pymunk.Body(1, pymunk.moment_for_circle(1, 0, BODY_R))
    self.body.position = pos
    body_shape = pymunk.Circle(self.body, BODY_R)
    body_shape.filter = pymunk.ShapeFilter(group=1, categories=0b01)
    # <STRANGE>#364 player is perfectly inelastic; without this a 0.5 platform elasticity multiplied by player default could still bounce
    body_shape.elasticity = 0.0
    space.add(self.body, body_shape)
    # <STRANGE>#365 custom velocity_func: small vertical jitter near ground gets snapped to zero to kill micro-bounces
    self.body.velocity_func = self._velocity_func

    self.arms = []
    for dx in (-ARM_DX, ARM_DX):
      a = pymunk.Body(ARM_MASS, pymunk.moment_for_circle(ARM_MASS, 0, ARM_R))
      a.position = (pos[0] + dx, pos[1])
      a_shape = pymunk.Circle(a, ARM_R)
      a_shape.filter = pymunk.ShapeFilter(group=1, categories=0b100)
      space.add(a, a_shape)
      self.arms.append(a)

    self.pressed = [False, False]
    self.arm_dir = [pymunk.Vec2d(-1, 0), pymunk.Vec2d(1, 0)]
    self.arm_r = [float(ARM_R), float(ARM_R)]
    self.lerp_t = ARM_LERP
    self.grabbed = [None, None]
    self.rope_len = [None, None]
    self.arm_pos = [pymunk.Vec2d(*a.position) for a in self.arms]
    self.arm_lerp = ARM_LERP
    self.arm_lerp_grab = ARM_LERP_GRAB
    self.arm_lerp_return = ARM_LERP_RETURN
    self.move = [False, False]
    self.jump = False
    self.jump_queued = False
    self.grab_lock = [False, False]
    self.joints = [None, None]
    self.stamina = [float(STAMINA_MAX), float(STAMINA_MAX)]
    self.held = [None, None]
    self.throw_requested = [False, False]
    self.shake_t = [0.0, 0.0]
    self.throw_hist = [[], []]
    self.spawn_queue = []

  def _velocity_func(self, body, gravity, damping, dt):
    # <STRANGE>#366 default pymunk integrator first, then post-filter micro-bounces
    pymunk.Body.update_velocity(body, gravity, damping, dt)
    if abs(body.velocity.y) < 30 and self._is_grounded():
      body.velocity = (body.velocity.x, 0.0)

  def _is_grounded(self):
    b = self.body.position
    pt = (b.x, b.y - BODY_R - 2)
    hits = self.space.point_query(pt, 6, pymunk.ShapeFilter(mask=0b10))
    return len(hits) > 0

  def _use(self, i):
    item = self.held[i]
    if item is None:
      return
    consumed, spawn_type, stamina_gain = item.use()
    if consumed:
      # <STRANGE>#344 pos captured BEFORE destroy; reading body after removal crashes or returns garbage
      pos = item.body.position
      # <STRANGE>#369 spawn inherits the throw velocity the item would have had; a bouncy +Y gives the "pop out" feel
      vx, vy = item.throw_vel
      vy += SPAWN_BOUNCE_V
      item.destroy()
      self.held[i] = None
      # <STRANGE>#362 lock this hand until mouse is released; otherwise the freshly spawned item lands in the arm and gets grabbed next frame
      self.grab_lock[i] = True
      if stamina_gain:
        for j in range(2):
          self.stamina[j] = min(STAMINA_MAX, self.stamina[j] + stamina_gain)
      if spawn_type is not None:
        self.spawn_queue.append((pos, spawn_type, (vx, vy)))
    else:
      self.shake_t[i] = ITEM_USE_SHAKE_TIME

  def _release(self, i):
    if self.joints[i] is not None:
      self.space.remove(self.joints[i])
      self.joints[i] = None
    if self.grabbed[i] is not None:
      self.grabbed[i][0].grab_count -= 1
    self.grabbed[i] = None
    self.rope_len[i] = None

  def _release_item(self, i, item):
    vx, vy = item.throw_vel
    mag = (vx * vx + vy * vy) ** 0.5
    if mag > THROW_MAX_SPEED:
      vx, vy = vx / mag * THROW_MAX_SPEED, vy / mag * THROW_MAX_SPEED
    self.throw_hist[i].clear()
    self.held[i] = None
    item.release((vx, vy))

  def handle_event(self, e):
    if e.type == pygame.MOUSEBUTTONDOWN:
      if e.button == 1:
        self.pressed[0] = True
      elif e.button == 3:
        self.pressed[1] = True
    elif e.type == pygame.MOUSEBUTTONUP:
      if e.button == 1:
        self.pressed[0] = False
        self.grab_lock[0] = False
        if self.held[0] is not None:
          self.throw_requested[0] = True
      elif e.button == 3:
        self.pressed[1] = False
        self.grab_lock[1] = False
        if self.held[1] is not None:
          self.throw_requested[1] = True
    elif e.type == pygame.KEYDOWN:
      if e.scancode == 4:
        self.move[0] = True
      elif e.scancode == 7:
        self.move[1] = True
      elif e.scancode == 44:
        self.jump = True
        self.jump_queued = True
      elif e.scancode == 20:
        self._use(0)
      elif e.scancode == 8:
        self._use(1)
    elif e.type == pygame.KEYUP:
      if e.scancode == 4:
        self.move[0] = False
      elif e.scancode == 7:
        self.move[1] = False
      elif e.scancode == 44:
        self.jump = False
        self.jump_queued = False

  def update(self, cam, pegs, items, dt):
    num_grabbed = sum(1 for g in self.grabbed if g is not None)
    for i in range(2):
      if self.grabbed[i] is not None:
        self.stamina[i] -= per_sec(STAMINA_HOLD_DRAIN, dt) / max(num_grabbed, 1)
        if self.stamina[i] <= 0:
          self.stamina[i] = 0.0
          self._release(i)
      else:
        mul = STAMINA_LOW_MUL if self.stamina[i] > STAMINA_LOW_THRESH else 1.0
        self.stamina[i] = min(STAMINA_MAX, self.stamina[i] + per_sec(STAMINA_REGEN * mul, dt))
    grounded = self._is_grounded()
    pitoned = any(g is not None for g in self.grabbed)
    drag = GROUND_DRAG if grounded else AIR_DRAG
    if self.jump_queued and (grounded or pitoned):
      self.body.velocity = (self.body.velocity.x, JUMP_V)
      self.jump_queued = False
      n = sum(1 for g in self.grabbed if g is not None)
      if n > 0:
        cost = STAMINA_JUMP_COST / n
        for i in range(2):
          if self.grabbed[i] is not None:
            self.stamina[i] -= cost
      for i in range(2):
        self._release(i)
        if self.pressed[i]:
          self.grab_lock[i] = True
    if self.move[0] and self.body.velocity.x > -MAX_WALK_VX:
      self.body.apply_force_at_local_point((-MOVE_ACC * self.body.mass, 0), (0, 0))
    if self.move[1] and self.body.velocity.x < MAX_WALK_VX:
      self.body.apply_force_at_local_point((MOVE_ACC * self.body.mass, 0), (0, 0))
    if not self.move[0] and not self.move[1]:
      # <STRANGE>#342 drag is per-frame decay; raise to dt*60 so 165fps doesn't brake 2.75x harder
      self.body.velocity = (self.body.velocity.x * (1 - drag) ** (dt * 60.0), self.body.velocity.y)
    mx, my = pygame.mouse.get_pos()
    mx, wy = cam.from_screen(mx, my)
    GRAB_DIST = PEG_R + ARM_R + 20
    for i, arm in enumerate(self.arms):
      if arm.body_type != pymunk.Body.KINEMATIC:
        arm.body_type = pymunk.Body.KINEMATIC
      if self.pressed[i]:
        if self.held[i] is None and self.grabbed[i] is None and not self.grab_lock[i] and self.stamina[i] > STAMINA_GRAB_MIN:
          item_hit = None
          for it in items:
            if it.held_by is None and arm.position.get_distance(it.body.position) <= it.grab_dist():
              item_hit = it
              break
          if item_hit is not None:
            self.held[i] = item_hit
            item_hit.hold(i)
        if self.held[i] is None and self.grabbed[i] is None and not self.grab_lock[i] and self.stamina[i] > STAMINA_GRAB_MIN:
          for obj in pegs:
            hit = None
            for world_pt, anchor in obj.grab_points():
              if arm.position.get_distance(world_pt) <= GRAB_DIST:
                hit = (world_pt, anchor)
                break
            if hit:
              world_pt, anchor = hit
              self.grabbed[i] = (obj, anchor, world_pt)
              obj.grab_count += 1
              cur = self.body.position.get_distance(world_pt)
              self.joints[i] = pymunk.SlideJoint(self.body, obj.body, (0, 0), anchor, cur, cur)
              self.rope_len[i] = cur
              self.space.add(self.joints[i])
              break
        if self.grabbed[i] is not None:
          if self.rope_len[i] > ARM_DX:
            self.rope_len[i] = max(ARM_DX, self.rope_len[i] - per_sec(REEL_SPEED, dt))
            self.joints[i].min = self.rope_len[i]
            self.joints[i].max = self.rope_len[i]
          world_pt = self.grabbed[i][2]
          d = world_pt - self.body.position
          if d.length > 0:
            self.arm_dir[i] = d.normalized()
          target_pos = world_pt
          self.arm_pos[i] += (target_pos - self.arm_pos[i]) * smooth(self.arm_lerp_grab, dt)
          arm.position = self.arm_pos[i]
          arm.velocity = (0, 0)
          target_r = PRESS_R if self.pressed[i] and not self.grab_lock[i] and self.grabbed[i] is None and self.stamina[i] > STAMINA_GRAB_MIN else ARM_R
          self.arm_r[i] += (target_r - self.arm_r[i]) * smooth(self.lerp_t, dt)
          continue
        target = pymunk.Vec2d(mx - self.body.position.x, wy - self.body.position.y)
      else:
        self._release(i)
        target = pymunk.Vec2d(-1 if i == 0 else 1, 0)
      if target.length > 0:
        target = target.normalized()
      else:
        target = self.arm_dir[i]
      self.arm_dir[i] = (self.arm_dir[i] + (target - self.arm_dir[i]) * smooth(self.lerp_t, dt)).normalized()
      target_r = PRESS_R if self.pressed[i] and not self.grab_lock[i] and self.grabbed[i] is None and self.stamina[i] > STAMINA_GRAB_MIN else ARM_R
      self.arm_r[i] += (target_r - self.arm_r[i]) * smooth(self.lerp_t, dt)

    a0, a1 = self.arm_dir[0].angle, self.arm_dir[1].angle
    diff = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    if abs(diff) < ARM_MIN_ANG:
      sign = 1 if diff >= 0 else -1
      push = (ARM_MIN_ANG - abs(diff)) / 2
      a0 -= sign * push
      a1 += sign * push
      self.arm_dir[0] = pymunk.Vec2d(1, 0).rotated(a0)
      self.arm_dir[1] = pymunk.Vec2d(1, 0).rotated(a1)

    for i, arm in enumerate(self.arms):
      if self.grabbed[i] is None:
        target_pos = self.body.position + self.arm_dir[i] * ARM_DX
        pressed = self.pressed[i] and not self.grab_lock[i] and self.stamina[i] > STAMINA_GRAB_MIN
        l = self.arm_lerp if pressed else self.arm_lerp_return
        self.arm_pos[i] += (target_pos - self.arm_pos[i]) * smooth(l, dt)
        arm.position = self.arm_pos[i]
      arm.velocity = (0, 0)

    for i in range(2):
      if self.throw_requested[i]:
        self.throw_requested[i] = False
        item = self.held[i]
        if item is not None:
          self._release_item(i, item)

    for i in range(2):
      item = self.held[i]
      if item is None:
        continue
      arm = self.arms[i]
      prev = pymunk.Vec2d(item.body.position.x, item.body.position.y)
      side = -1 if i == 0 else 1
      tx = arm.position.x + ITEM_OFFSET * side
      ty = arm.position.y
      r = item.radius()
      if ty < r:
        ty = r
      item.body.position = pymunk.Vec2d(tx, ty)
      item.body.velocity = (0, 0)
      # <STRANGE>#349 while held, angle lerps to 0 (upright); smooth() keeps this fps-independent
      k = smooth(0.25, dt)
      if abs(item.body.angle) > 1e-3:
        item.body.angle += (0 - item.body.angle) * k
      else:
        item.body.angle = 0.0
      # <STRANGE>#343 dt-correct instantaneous throw velocity: screen px per second
      inst = (pymunk.Vec2d(tx, ty) - prev) / dt
      hist = self.throw_hist[i]
      hist.append((inst.x, inst.y))
      if len(hist) > THROW_SMOOTH_FRAMES:
        hist.pop(0)
      ax = sum(h[0] for h in hist) / len(hist)
      ay = sum(h[1] for h in hist) / len(hist)
      item.throw_vel = (ax, ay)

    for i in range(2):
      if self.shake_t[i] > 0:
        self.shake_t[i] -= dt
        if self.shake_t[i] < 0:
          self.shake_t[i] = 0.0


  def draw(self, screen, cam):
    sc = cam.scale
    bx, by = cam.to_screen(*self.body.position)
    pygame.draw.circle(screen, (255, 255, 255), (int(bx), int(by)), int(BODY_R * sc))
    for i, arm in enumerate(self.arms):
      ax, ay = cam.to_screen(*arm.position)
      s_t = max(0.0, min(1.0, self.stamina[i] / STAMINA_MAX))
      if s_t < 0.5:
        shake = SHAKE_MAX * (1 - s_t * 2) * sc
        ax += random.uniform(-shake, shake)
        ay += random.uniform(-shake, shake)
      if self.shake_t[i] > 0:
        amp = ITEM_USE_SHAKE_AMP * sc
        ax += random.uniform(-amp, amp)
        ay += random.uniform(-amp, amp)
      if self.held[i] is not None:
        self.held[i].draw(screen, cam)
      arm_color = (223, int(223 * s_t), int(223 * s_t))
      if self.held[i] is not None:
        r = int(self.arm_r[i] * ARM_HOLD_SCALE * sc)
        size = r * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*arm_color, ARM_HOLD_ALPHA), (r, r), r)
        screen.blit(surf, (int(ax) - r, int(ay) - r))
      else:
        r = int(self.arm_r[i] * sc)
        pygame.draw.circle(screen, arm_color, (int(ax), int(ay)), r)
      pressed_vis = self.held[i] is None and (self.grabbed[i] is not None or (self.pressed[i] and not self.grab_lock[i] and self.stamina[i] > STAMINA_GRAB_MIN))
      if pressed_vis:
        if self.grabbed[i] is not None:
          pygame.draw.circle(screen, (0, 0, 0), (int(ax), int(ay)), r // 1.6)
        else:
          t = max(2, r // 4)
          pygame.draw.circle(screen, (0, 0, 0), (int(ax), int(ay)), r // 1.2, t)

  def draw_hud(self, screen, cam):
    # <STRANGE>#351 HUD is screen-space; identity cam trick reuses item.draw_at without touching world logic
    sc = cam.scale
    sw, sh = screen.get_size()
    cx, cy = sw / 2, sh / 2
    # <STRANGE>#352 offset = 4 player diameters / 2 = 4*BODY_R; distance between circle centers is 8*BODY_R
    offset = 4 * BODY_R * sc
    r = int(BODY_R * sc)
    for i in range(2):
      hx = cx + (-offset if i == 0 else offset)
      hy = cy
      s_t = max(0.0, min(1.0, self.stamina[i] / STAMINA_MAX))
      arm_color = (223, int(223 * s_t), int(223 * s_t))
      surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
      # <STRANGE>#357 fill-only HUD circle, low alpha so it reads as an overlay, not a solid disc
      pygame.draw.circle(surf, (*arm_color, 35), (r, r), r)
      screen.blit(surf, (int(hx) - r, int(hy) - r))
      it = self.held[i]
      if it is not None:
        # <STRANGE>#353 identity cam: to_screen returns coords unchanged so item renders in HUD space; scale 1.0
        it.draw_at(screen, _HUDScreenCam(sc), (hx, hy), 0.0, 160, 1.0)


class _HUDScreenCam:
  # <STRANGE>#354 minimal stand-in for Camera; item.draw_at only needs .scale and .to_screen
  def __init__(self, scale):
    self.scale = scale
  def to_screen(self, x, y):
    return (x, y)
