import math
import random
import pygame
import pymunk
from .peg import PEG_R

BODY_R = 36
ARM_R = 13
ARM_MASS = 0.1
ARM_DX = 45
ARM_MIN_ANG = math.radians(15)
PRESS_R = 15
MOVE_ACC = 2000
AIR_DRAG = 0.005
GROUND_DRAG = 0.25
PULL_ACC = 8000
PULL_RANGE = 400
MAX_WALK_VX = 400
JUMP_V = 500
STAMINA_MAX = 100
STAMINA_HOLD_DRAIN = 0.2
STAMINA_JUMP_COST = 10
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
    # <STRANGE>#22 non-zero group=1 disables collision between player parts (body<->arms, arm<->arm)
    body_shape.filter = pymunk.ShapeFilter(group=1, categories=0b01)
    space.add(self.body, body_shape)

    self.arms = []
    for dx in (-ARM_DX, ARM_DX):
      a = pymunk.Body(ARM_MASS, pymunk.moment_for_circle(ARM_MASS, 0, ARM_R))
      a.position = (pos[0] + dx, pos[1])
      a_shape = pymunk.Circle(a, ARM_R)
      a_shape.filter = pymunk.ShapeFilter(group=1, categories=0b100)
      space.add(a, a_shape)
      self.arms.append(a)

    # <STRANGE>#10 index 0 = left (LMB), 1 = right (RMB); physics circle stays ARM_R, only draw grows
    self.pressed = [False, False]
    # <STRANGE>#20 arm_dir/arm_r are visual-only state; arms themselves are kinematic points
    self.arm_dir = [pymunk.Vec2d(-1, 0), pymunk.Vec2d(1, 0)]
    self.arm_r = [float(ARM_R), float(ARM_R)]
    self.lerp_t = 0.45
    # <STRANGE>#30 grabbed[i] is (obj, local_anchor, world_pos) tuple or None; obj.grab_count tracks active hands
    self.grabbed = [None, None]
    # <STRANGE>#37 arm_pos is the visual lerp target; grabbed sets target to peg, free sets to body+dir*ARM_DX
    self.arm_pos = [pymunk.Vec2d(*a.position) for a in self.arms]
    self.arm_lerp = 0.25
    # <STRANGE>#81 separate fast lerp for grab so arm snaps to peg quickly, free return stays smooth
    self.arm_lerp_grab = 0.7
    self.move = [False, False]
    self.jump = False
    # <STRANGE>#58 grabbed[i] set by press; grab_lock blocks re-grab until the button is released and pressed again
    self.grab_lock = [False, False]
    # <STRANGE>#72 SlideJoint per arm caps body-to-peg distance at ARM_DX; hard stop, not force
    self.joints = [None, None]
    self.stamina = [float(STAMINA_MAX), float(STAMINA_MAX)]

  def _is_grounded(self):
    # <STRANGE>#124 query mask 0b10 hits floor/platform only; body is 0b01, arms 0b100, so no self-hits
    b = self.body.position
    pt = (b.x, b.y - BODY_R - 2)
    hits = self.space.point_query(pt, 6, pymunk.ShapeFilter(mask=0b10))
    return len(hits) > 0

  def _release(self, i):
    if self.joints[i] is not None:
      self.space.remove(self.joints[i])
      self.joints[i] = None
    if self.grabbed[i] is not None:
      self.grabbed[i][0].grab_count -= 1
    self.grabbed[i] = None

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
      elif e.button == 3:
        self.pressed[1] = False
        self.grab_lock[1] = False
    elif e.type == pygame.KEYDOWN:
      if e.key == pygame.K_a:
        self.move[0] = True
      elif e.key == pygame.K_d:
        self.move[1] = True
      elif e.key == pygame.K_SPACE:
        self.jump = True
    elif e.type == pygame.KEYUP:
      if e.key == pygame.K_a:
        self.move[0] = False
      elif e.key == pygame.K_d:
        self.move[1] = False
      elif e.key == pygame.K_SPACE:
        self.jump = False

  def update(self, cam, pegs):
    # <STRANGE>#18 arms kinematic, pinned to body at fixed offset; body only moves from gravity and future peg grabs
    # <STRANGE>#39 accel applied per-frame, so real accel scales with fps; 60fps assumption baked into MOVE_ACC
    # <STRANGE>#91 stamina drain shared across grabbed arms, regen only when free; force-release at 0
    num_grabbed = sum(1 for g in self.grabbed if g is not None)
    for i in range(2):
      if self.grabbed[i] is not None:
        self.stamina[i] -= STAMINA_HOLD_DRAIN / max(num_grabbed, 1)
        if self.stamina[i] <= 0:
          self.stamina[i] = 0.0
          self._release(i)
      else:
        # <STRANGE>#135 above half stamina regen is faster; tail-end of recovery is slower
        mul = STAMINA_LOW_MUL if self.stamina[i] > STAMINA_LOW_THRESH else 1.0
        self.stamina[i] = min(STAMINA_MAX, self.stamina[i] + STAMINA_REGEN * mul)
    grounded = self._is_grounded()
    # <STRANGE>#54 pitoned check via any grabbed arm; jump works on ground or while held to a peg
    pitoned = any(g is not None for g in self.grabbed)
    drag = GROUND_DRAG if grounded else AIR_DRAG
    if self.jump and (grounded or pitoned):
      # <STRANGE>#55 direct velocity set; add input direction later for directional jump
      self.body.velocity = (self.body.velocity.x, JUMP_V)
      # <STRANGE>#92 jump cost split evenly among grabbed arms; ground jump is free (no arm spent)
      n = sum(1 for g in self.grabbed if g is not None)
      if n > 0:
        cost = STAMINA_JUMP_COST / n
        for i in range(2):
          if self.grabbed[i] is not None:
            self.stamina[i] -= cost
      # <STRANGE>#59 release both arms on jump and lock until button released; pitoned is pre-jump value so it fired above
      for i in range(2):
        self._release(i)
        if self.pressed[i]:
          self.grab_lock[i] = True
    # <STRANGE>#52 walk cap only blocks ADDING speed in walk direction; external speed (swing, pull) above cap untouched
    if self.move[0] and self.body.velocity.x > -MAX_WALK_VX:
      self.body.apply_force_at_local_point((-MOVE_ACC * self.body.mass, 0), (0, 0))
    if self.move[1] and self.body.velocity.x < MAX_WALK_VX:
      self.body.apply_force_at_local_point((MOVE_ACC * self.body.mass, 0), (0, 0))
    # <STRANGE>#128 drag only when no input: full speed while walking, sharp stop when released
    if not self.move[0] and not self.move[1]:
      self.body.velocity = (self.body.velocity.x * (1 - drag), self.body.velocity.y)
    mx, my = pygame.mouse.get_pos()
    mx, wy = cam.from_screen(mx, my)
    # <STRANGE>#31 grab radius vs peg radius; tune GRAB_DIST if grabbing feels too easy/hard
    GRAB_DIST = PEG_R + ARM_R + 20
    for i, arm in enumerate(self.arms):
      if arm.body_type != pymunk.Body.KINEMATIC:
        arm.body_type = pymunk.Body.KINEMATIC
      if self.pressed[i]:
        if self.grabbed[i] is None and not self.grab_lock[i] and self.stamina[i] > STAMINA_GRAB_MIN:
          # <STRANGE>#34 grab check uses arm's current world pos, not mouse; cursor may be anywhere, arm is what must touch the peg
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
              # <STRANGE>#114 local anchor on the target so distance is measured to the edge, not the body center
              self.joints[i] = pymunk.SlideJoint(self.body, obj.body, (0, 0), anchor, ARM_DX, ARM_DX)
              self.space.add(self.joints[i])
              break
        if self.grabbed[i] is not None:
          d = self.grabbed[i][2] - self.body.position
          # <STRANGE>#68 arm reach capped at ARM_DX from body; if peg is farther, arm stays extended toward it, body gets pulled in
          if d.length > 0:
            self.arm_dir[i] = d.normalized()
            target_pos = self.body.position + self.arm_dir[i] * min(d.length, ARM_DX)
          else:
            target_pos = self.arm_pos[i]
          self.arm_pos[i] += (target_pos - self.arm_pos[i]) * self.arm_lerp_grab
          arm.position = self.arm_pos[i]
          arm.velocity = (0, 0)
          # <STRANGE>#79 grabbed arm stays ARM_R; PRESS_R only while pressed, unlocked, not grabbed, and stamina above grab min
          target_r = PRESS_R if self.pressed[i] and not self.grab_lock[i] and self.grabbed[i] is None and self.stamina[i] > STAMINA_GRAB_MIN else ARM_R
          self.arm_r[i] += (target_r - self.arm_r[i]) * self.lerp_t
          continue
        target = pymunk.Vec2d(mx - self.body.position.x, wy - self.body.position.y)
      else:
        self._release(i)
        target = pymunk.Vec2d(-1 if i == 0 else 1, 0)
      if target.length > 0:
        target = target.normalized()
      else:
        target = self.arm_dir[i]
      self.arm_dir[i] = (self.arm_dir[i] + (target - self.arm_dir[i]) * self.lerp_t).normalized()
      target_r = PRESS_R if self.pressed[i] and not self.grab_lock[i] and self.grabbed[i] is None and self.stamina[i] > STAMINA_GRAB_MIN else ARM_R
      self.arm_r[i] += (target_r - self.arm_r[i]) * self.lerp_t

    # <STRANGE>#24 min angular gap between arms; both arms pulled to same cursor get pushed apart equally
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
        self.arm_pos[i] += (target_pos - self.arm_pos[i]) * self.arm_lerp
        arm.position = self.arm_pos[i]
      arm.velocity = (0, 0)

  def draw(self, screen, cam):
    bx, by = cam.to_screen(*self.body.position)
    pygame.draw.circle(screen, (255, 255, 255), (int(bx), int(by)), BODY_R)
    # <STRANGE>#27 eyes offset in world coords then pushed toward cursor; reuses raw mouse, not world mouse, for direction simplicity
    mx, my = pygame.mouse.get_pos()
    dx, dy = mx - bx, my - by
    d = math.hypot(dx, dy)
    for i, arm in enumerate(self.arms):
      ax, ay = cam.to_screen(*arm.position)
      # <STRANGE>#101 shake is visual only; grows from 0 at half stamina to SHAKE_MAX at 0
      s_t = max(0.0, min(1.0, self.stamina[i] / STAMINA_MAX))
      shake = 0.0
      if s_t < 0.5:
        shake = SHAKE_MAX * (1 - s_t * 2)
        ax += random.uniform(-shake, shake)
        ay += random.uniform(-shake, shake)
      r = int(self.arm_r[i])
      # <STRANGE>#93 stamina tints arm from white (full) to red (empty); R stays 223, G/B lerp
      # <STRANGE>#99 stamina can go negative from jump cost before drain clamp runs; clamp t to [0,1]
      arm_color = (223, int(223 * s_t), int(223 * s_t))
      pygame.draw.circle(screen, arm_color, (int(ax), int(ay)), r)
      # <STRANGE>#77 grab_lock means released after jump; draw as if not pressed even though button is held
      # <STRANGE>#98 stamina gate only blocks NEW press visuals; ongoing grab keeps its filled marker until release
      pressed_vis = self.grabbed[i] is not None or (self.pressed[i] and not self.grab_lock[i] and self.stamina[i] > STAMINA_GRAB_MIN)
      if pressed_vis:
        # <STRANGE>#69 ring = free, filled = grabbed; thickness param 0 makes pygame draw filled
        if self.grabbed[i] is not None:
          pygame.draw.circle(screen, (0, 0, 0), (int(ax), int(ay)), r // 1.6)
        else:
          # <STRANGE>#89 thicker ring while pressed to read as clenched vs the free ARM_R draw
          t = max(2, r // 4)
          pygame.draw.circle(screen, (0, 0, 0), (int(ax), int(ay)), r // 1.2, t)

    # <STRANGE>#27 eyes are purely cosmetic, pupil offset uses raw mouse pos in screen space

