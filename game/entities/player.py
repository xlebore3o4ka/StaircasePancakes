import math
import random
import pygame
import pymunk
from shared.const import BODY_R, ARM_R, ARM_DX, JUMP_V, PEG_R, ITEM_OFFSET, ITEM_USE_SHAKE_TIME, ITEM_USE_SHAKE_AMP, ARM_HOLD_ALPHA, ARM_HOLD_SCALE

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
    self.lerp_t = ARM_LERP
    # <STRANGE>#30 grabbed[i] is (obj, local_anchor, world_pos) tuple or None; obj.grab_count tracks active hands
    self.grabbed = [None, None]
    # <STRANGE>#164 rope_len is current joint length; on grab starts at body-anchor distance, reels to ARM_DX
    self.rope_len = [None, None]
    # <STRANGE>#37 arm_pos is the visual lerp target; grabbed sets target to peg, free sets to body+dir*ARM_DX
    self.arm_pos = [pymunk.Vec2d(*a.position) for a in self.arms]
    self.arm_lerp = ARM_LERP
    # <STRANGE>#81 separate fast lerp for grab so arm snaps to peg quickly, free return stays smooth
    self.arm_lerp_grab = ARM_LERP_GRAB
    # <STRANGE>#138 slower lerp only for unpressed return-to-rest; pressed tracking stays at ARM_LERP
    self.arm_lerp_return = ARM_LERP_RETURN
    self.move = [False, False]
    self.jump = False
    # <STRANGE>#141 edge-trigger jump: set on KEYDOWN, consumed on successful jump
    self.jump_queued = False
    # <STRANGE>#58 grabbed[i] set by press; grab_lock blocks re-grab until the button is released and pressed again
    self.grab_lock = [False, False]
    # <STRANGE>#72 SlideJoint per arm caps body-to-peg distance at ARM_DX; hard stop, not force
    self.joints = [None, None]
    self.stamina = [float(STAMINA_MAX), float(STAMINA_MAX)]
    # <STRANGE>#251 held[i] is an Item; throw_requested set on mouse-up, consumed in update
    self.held = [None, None]
    self.throw_requested = [False, False]
    self.shake_t = [0.0, 0.0]

  def _is_grounded(self):
    # <STRANGE>#124 query mask 0b10 hits floor/platform only; body is 0b01, arms 0b100, so no self-hits
    b = self.body.position
    pt = (b.x, b.y - BODY_R - 2)
    hits = self.space.point_query(pt, 6, pymunk.ShapeFilter(mask=0b10))
    return len(hits) > 0

  def _use(self, i):
    item = self.held[i]
    if item is None:
      return
    if item.use():
      # <STRANGE>#253 consumed: for now just drop it; real removal from world later
      item.release((0, 0))
      self.held[i] = None
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
    # <STRANGE>#193 scancode not key: e.key depends on layout (K_a != Cyrillic "a"), scancode is physical position
    # <STRANGE>#196 pygame-ce exposes no SCANCODE_* constants; raw SDL scancodes: A=4, D=7, SPACE=44
    elif e.type == pygame.KEYDOWN:
      if e.scancode == 4:
        self.move[0] = True
      elif e.scancode == 7:
        self.move[1] = True
      elif e.scancode == 44:
        self.jump = True
        self.jump_queued = True
      # <STRANGE>#252 SDL scancodes: Q=20, E=8
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
        # <STRANGE>#182 queue must clear on release; otherwise pressing in air and releasing still fires on landing
        self.jump_queued = False

  def update(self, cam, pegs, items):
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
    if self.jump_queued and (grounded or pitoned):
      # <STRANGE>#55 direct velocity set; add input direction later for directional jump
      self.body.velocity = (self.body.velocity.x, JUMP_V)
      self.jump_queued = False
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
        if self.held[i] is None and self.grabbed[i] is None and not self.grab_lock[i] and self.stamina[i] > STAMINA_GRAB_MIN:
          # <STRANGE>#254 items checked first: tighter range, more specific than peg grab
          item_hit = None
          for it in items:
            if it.held_by is None and arm.position.get_distance(it.body.position) <= it.grab_dist():
              item_hit = it
              break
          if item_hit is not None:
            self.held[i] = item_hit
            item_hit.hold(i)
        if self.held[i] is None and self.grabbed[i] is None and not self.grab_lock[i] and self.stamina[i] > STAMINA_GRAB_MIN:
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
              # <STRANGE>#164 start rope at current body-to-anchor distance so joint doesn't teleport body; reel in each frame
              cur = self.body.position.get_distance(world_pt)
              self.joints[i] = pymunk.SlideJoint(self.body, obj.body, (0, 0), anchor, cur, cur)
              self.rope_len[i] = cur
              self.space.add(self.joints[i])
              break
        if self.grabbed[i] is not None:
          # <STRANGE>#165 reel in: rope shortens each frame, body follows via rigid joint; stops at ARM_DX
          if self.rope_len[i] > ARM_DX:
            self.rope_len[i] = max(ARM_DX, self.rope_len[i] - REEL_SPEED)
            self.joints[i].min = self.rope_len[i]
            self.joints[i].max = self.rope_len[i]
          # <STRANGE>#179 arm always snaps to the grab point; body reels in via rope_len, arm does not stretch with it
          world_pt = self.grabbed[i][2]
          d = world_pt - self.body.position
          if d.length > 0:
            self.arm_dir[i] = d.normalized()
          target_pos = world_pt
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
        # <STRANGE>#139 lerp choice: slow return when unpressed and not near rest, fast otherwise
        pressed = self.pressed[i] and not self.grab_lock[i] and self.stamina[i] > STAMINA_GRAB_MIN
        l = self.arm_lerp if pressed else self.arm_lerp_return
        self.arm_pos[i] += (target_pos - self.arm_pos[i]) * l
        arm.position = self.arm_pos[i]
      arm.velocity = (0, 0)

    # <STRANGE>#264 throws processed FIRST: otherwise arm lerps toward rest this frame and item inherits downward velocity on release
    for i in range(2):
      if self.throw_requested[i]:
        self.throw_requested[i] = False
        item = self.held[i]
        if item is not None:
          item.release(item.throw_vel)
          self.held[i] = None

    # <STRANGE>#255 held items follow arm position exactly (no lerp); throw_vel is last-frame delta * 60
    for i in range(2):
      item = self.held[i]
      if item is None:
        continue
      arm = self.arms[i]
      prev = pymunk.Vec2d(item.body.position.x, item.body.position.y)
      side = -1 if i == 0 else 1
      target = pymunk.Vec2d(arm.position.x + ITEM_OFFSET * side, arm.position.y)
      item.body.position = target
      item.body.velocity = (0, 0)
      item.throw_vel = (target - prev) * 60

    for i in range(2):
      if self.shake_t[i] > 0:
        self.shake_t[i] -= 1 / 60
        if self.shake_t[i] < 0:
          self.shake_t[i] = 0.0

  def draw(self, screen, cam):
    sc = cam.scale
    bx, by = cam.to_screen(*self.body.position)
    pygame.draw.circle(screen, (255, 255, 255), (int(bx), int(by)), int(BODY_R * sc))
    for i, arm in enumerate(self.arms):
      ax, ay = cam.to_screen(*arm.position)
      # <STRANGE>#101 shake is visual only; grows from 0 at half stamina to SHAKE_MAX at 0
      s_t = max(0.0, min(1.0, self.stamina[i] / STAMINA_MAX))
      if s_t < 0.5:
        shake = SHAKE_MAX * (1 - s_t * 2) * sc
        ax += random.uniform(-shake, shake)
        ay += random.uniform(-shake, shake)
      # <STRANGE>#256 use-shake applied to arm visuals only; item follows physics position, not shaken
      if self.shake_t[i] > 0:
        amp = ITEM_USE_SHAKE_AMP * sc
        ax += random.uniform(-amp, amp)
        ay += random.uniform(-amp, amp)
      # <STRANGE>#257 held item drawn before arm so the arm renders on top (item is "under" the hand)
      if self.held[i] is not None:
        self.held[i].draw(screen, cam)
      # <STRANGE>#93 stamina tints arm from white (full) to red (empty); R stays 223, G/B lerp
      # <STRANGE>#99 stamina can go negative from jump cost before drain clamp runs; clamp t to [0,1]
      arm_color = (223, int(223 * s_t), int(223 * s_t))
      if self.held[i] is not None:
        # <STRANGE>#274 arm shrinks to half and goes translucent while holding; no ring drawn so item reads clearly
        r = int(self.arm_r[i] * ARM_HOLD_SCALE * sc)
        size = r * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*arm_color, ARM_HOLD_ALPHA), (r, r), r)
        screen.blit(surf, (int(ax) - r, int(ay) - r))
      else:
        r = int(self.arm_r[i] * sc)
        pygame.draw.circle(screen, arm_color, (int(ax), int(ay)), r)
      # <STRANGE>#77 grab_lock means released after jump; draw as if not pressed even though button is held
      # <STRANGE>#98 stamina gate only blocks NEW press visuals; ongoing grab keeps its filled marker until release
      # <STRANGE>#275 no marker while holding an item; the held cube itself is the visual indicator
      pressed_vis = self.held[i] is None and (self.grabbed[i] is not None or (self.pressed[i] and not self.grab_lock[i] and self.stamina[i] > STAMINA_GRAB_MIN))
      if pressed_vis:
        # <STRANGE>#69 ring = free, filled = grabbed; thickness param 0 makes pygame draw filled
        if self.grabbed[i] is not None:
          pygame.draw.circle(screen, (0, 0, 0), (int(ax), int(ay)), r // 1.6)
        else:
          # <STRANGE>#89 thicker ring while pressed to read as clenched vs the free ARM_R draw
          t = max(2, r // 4)
          pygame.draw.circle(screen, (0, 0, 0), (int(ax), int(ay)), r // 1.2, t)

    # <STRANGE>#27 eyes are purely cosmetic, pupil offset uses raw mouse pos in screen space

