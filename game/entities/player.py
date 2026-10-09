import math
import random
import pygame
import pymunk
from shared.const import BODY_R, ARM_R, ARM_DX, JUMP_V, PEG_R, ITEM_OFFSET, ITEM_USE_SHAKE_TIME, ITEM_USE_SHAKE_AMP, ARM_HOLD_ALPHA, ARM_HOLD_SCALE, THROW_MAX_SPEED, THROW_SMOOTH_FRAMES, SPAWN_BOUNCE_V, REEL_MAX_FORCE, HUD_BASE_ALPHA, HUD_BASE_ALPHA_EMPTY, HUD_LABEL_ALPHA, HUD_LABEL_ALPHA_EMPTY, HUD_LABEL_ALPHA_HELD, HUD_LABEL_SCALE_HELD, HUD_FLASH_ALPHA, HUD_FLASH_DURATION, STAMINA_BOOST_RATE, LAYER_PLAYER, HUD_ITEMSMODE_RING_ALPHA, HUD_ITEMSMODE_RING_W, HIT_VOL_MIN, HIT_VOL_MAX, HIT_COOLDOWN
from shared.smooth import smooth, per_sec
from shared.physics_util import has_ground_contact
from .consume_fx import SodaConsumeFx

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
  layer = LAYER_PLAYER

  def __init__(self, space, pos, cheats=False, sound=None):
    self.space = space
    # <STRANGE>#683 optional; None in tests/editor
    self.sound = sound
    # <STRANGE>#429 cheats flag bypasses stamina accounting and air-jump gating
    self.cheats = cheats
    self.body = pymunk.Body(1, pymunk.moment_for_circle(1, 0, BODY_R))
    self.body.position = pos
    body_shape = pymunk.Circle(self.body, BODY_R)
    body_shape.filter = pymunk.ShapeFilter(group=1, categories=0b01)
    # <STRANGE>#364 player is perfectly inelastic
    body_shape.elasticity = 0.0
    # <STRANGE>#731 zero friction on the player shape: brushing floor mid-swing would otherwise kill tangential velocity
    body_shape.friction = 0.0
    space.add(self.body, body_shape)
    self.arms = []
    for dx in (-ARM_DX, ARM_DX):
      a = pymunk.Body(ARM_MASS, pymunk.moment_for_circle(ARM_MASS, 0, ARM_R))
      a.position = (pos[0] + dx, pos[1])
      a_shape = pymunk.Circle(a, ARM_R)
      # <STRANGE>#546 arms are pure visuals: kinematic, position set every frame, mask=0 so deep penetrations don't generate solver bias
      a_shape.filter = pymunk.ShapeFilter(group=1, categories=0b100, mask=0)
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
    # <STRANGE>#591 set in the frame a jump is committed; post_step skips clamping then
    self.jumped_this_frame = False
    # <STRANGE>#678 vy before the last physics step; used to tell ballistic motion from bias spikes
    self._pre_vy = 0.0
    self._pre_v = pymunk.Vec2d(0, 0)
    self._hit_cd = 0.0
    # <STRANGE>#551 f-mode: hands grab items only, pegs are ignored; toggle on KEYDOWN F
    self.items_only = False
    self.grab_lock = [False, False]
    # <STRANGE>#646 cooldown seconds per hand; blocks NEW grabs even while button is held
    self.grab_cooldown = [0.0, 0.0]
    self.joints = [None, None]
    self.stamina = [float(STAMINA_MAX), float(STAMINA_MAX)]
    self.held = [None, None]
    self.throw_requested = [False, False]
    self.shake_t = [0.0, 0.0]
    self.throw_hist = [[], []]
    self.spawn_queue = []
    # <STRANGE>#413 visual fx from consumed items; player-owned, ticked in update
    self.consume_fx = []
    # <STRANGE>#390 HUD feedback state: per-hand flash (0..1) on use, lazy-cached Q/E surfaces
    self.hud_flash = [0.0, 0.0]
    self._hud_labels = None
    # <STRANGE>#434 pending stamina from soda; drips into stamina[] at STAMINA_BOOST_RATE per second
    self.stamina_boost = [0.0, 0.0]

  def _is_grounded(self):
    b = self.body.position
    pt = (b.x, b.y - BODY_R - 2)
    hits = self.space.point_query(pt, 6, pymunk.ShapeFilter(mask=0b10))
    return len(hits) > 0


  def record_pre_step(self):
    # <STRANGE>#678 store pre-step velocity; post_step compares vy for bias and full v for impact volume
    self._pre_vy = self.body.velocity.y
    self._pre_v = pymunk.Vec2d(self.body.velocity.x, self.body.velocity.y)

  def post_step(self, dt):
    # <STRANGE>#736 bias means vy was ~0 before step and became large after: solver kicked, not gameplay
    if self.jumped_this_frame:
      return
    v = self.body.velocity.y
    # <TODO>#741 diagnostic: log any positive vy jump; remove when filters are solid
    if v > 200 and (v - self._pre_vy) > 100:
      print(f"JUMP vy={v:.0f} pre_vy={self._pre_vy:.0f} dv={v - self._pre_vy:.0f} grabbed={[g is not None for g in self.grabbed]} jumped={self.jumped_this_frame}")
    if v > JUMP_V * 1.05 and self._pre_vy < 50 and not any(g is not None for g in self.grabbed):
      self.body.velocity = (self.body.velocity.x, 0.0)
    # <STRANGE>#694 impact sfx: any new contact with floor/platform while moving into it fast
    if self.sound is not None and self._hit_cd <= 0:
      max_proj = 0.0
      def cb(arb, _):
        nonlocal max_proj
        if not arb.is_first_contact:
          return True
        a, b = arb.shapes
        if a.body is self.body:
          other = b
          n = -arb.contact_point_set.normal
        elif b.body is self.body:
          other = a
          n = arb.contact_point_set.normal
        else:
          return True
        if not (other.filter.categories & 0b10):
          return True
        p = -(self._pre_v.x * n.x + self._pre_v.y * n.y)
        if p > max_proj:
          max_proj = p
        return True
      self.body.each_arbiter(cb, None)
      if max_proj >= HIT_VOL_MIN:
        vol = (max_proj - HIT_VOL_MIN) / max(1, HIT_VOL_MAX - HIT_VOL_MIN)
        vol = min(1.0, max(0.15, vol))
        self.sound.play("hit", volume=vol)
        self._hit_cd = HIT_COOLDOWN
    if self._hit_cd > 0:
      self._hit_cd -= dt

  def _use(self, i):
    item = self.held[i]
    if item is None:
      return
    self.hud_flash[i] = 1.0
    # <STRANGE>#522 on_use can consume the action entirely (rebar shoot); "release" also drops it from the hand
    r = item.on_use(self, i)
    if r == "release":
      self.held[i] = None
      self.grab_lock[i] = True
      # <STRANGE>#647 rebar shoots out of hand; block re-grab for a moment so it clears the arm radius
      self.grab_cooldown[i] = 0.5
      # <STRANGE>#650 recoil kicks the body away from any peg it was holding; release both hands like a jump does
      for j in range(2):
        if j == i:
          continue
        self._release(j)
        if self.pressed[j]:
          self.grab_lock[j] = True
      return
    if r:
      return
    consumed, spawn_spec, stamina_gain = item.use()
    if consumed:
      if self.sound is not None and item.use_sound:
        # <STRANGE>#744 fire before item.destroy in case subclass cleanup nulls state
        self.sound.play(item.use_sound)
      # <STRANGE>#344 pos captured BEFORE destroy; reading body after removal crashes or returns garbage
      pos = item.body.position
      angle = item.body.angle
      # <STRANGE>#369 spawn inherits the throw velocity the item would have had; a bouncy +Y gives the "pop out" feel
      vx, vy = item.throw_vel
      vy += SPAWN_BOUNCE_V
      self.held[i] = None
      # <STRANGE>#362 lock this hand until mouse is released; otherwise the freshly spawned item lands in the arm and gets grabbed next frame
      self.grab_lock[i] = True
      if item.center_anim:
        # <STRANGE>#414 defer stamina to fx completion; item must be alive for draw_at during the anim
        self.consume_fx.append(SodaConsumeFx(self, item, angle, stamina_gain))
        # <STRANGE>#697 soda sfx plays as the drink animation starts
        if self.sound is not None:
          self.sound.play("soda")
      else:
        item.destroy()
        if stamina_gain:
          for j in range(2):
            self.stamina[j] = min(STAMINA_MAX, self.stamina[j] + stamina_gain)
      # <STRANGE>#574 spawn_spec dict carries type + extras like contents; nested cubes keep their loot table
      if spawn_spec is not None:
        self.spawn_queue.append((pos, spawn_spec, (vx, vy)))
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
      # <STRANGE>#552 SDL scancode F=9; hold F for items-only grabbing
      elif e.scancode == 9:
        self.items_only = True
    elif e.type == pygame.KEYUP:
      if e.scancode == 4:
        self.move[0] = False
      elif e.scancode == 7:
        self.move[1] = False
      elif e.scancode == 44:
        self.jump = False
        self.jump_queued = False
        # <STRANGE>#432 on space release, unlock arms that are still held down so they re-clench and can re-grab
        for i in range(2):
          if self.pressed[i]:
            self.grab_lock[i] = False
      # <STRANGE>#558 F release clears items-only mode
      elif e.scancode == 9:
        self.items_only = False

  def update(self, cam, pegs, items, dt):
    # <STRANGE>#592 new frame: clear the jump flag so post_step can clamp again unless we jump this frame
    self.jumped_this_frame = False
    num_grabbed = sum(1 for g in self.grabbed if g is not None)
    for i in range(2):
      if self.cheats:
        self.stamina[i] = STAMINA_MAX
        self.stamina_boost[i] = 0.0
        continue
      # <STRANGE>#434 boost drains into stamina at a capped rate; leftover kept for next frame
      if self.stamina_boost[i] > 0:
        step = per_sec(STAMINA_BOOST_RATE, dt)
        if step > self.stamina_boost[i]:
          step = self.stamina_boost[i]
        self.stamina_boost[i] -= step
        self.stamina[i] = min(STAMINA_MAX, self.stamina[i] + step)
      if self.grabbed[i] is not None:
        self.stamina[i] -= per_sec(STAMINA_HOLD_DRAIN, dt) / max(num_grabbed, 1)
        if self.stamina[i] <= 0:
          self.stamina[i] = 0.0
          self._release(i)
      else:
        mul = STAMINA_LOW_MUL if self.stamina[i] > STAMINA_LOW_THRESH else 1.0
        self.stamina[i] = min(STAMINA_MAX, self.stamina[i] + per_sec(STAMINA_REGEN * mul, dt))
    grounded = self._is_grounded()
    # <TODO>#385 diagnostic: only fire on a truly anomalous spike; legit swings exceed JUMP_V all the time
    if (self.body.velocity.y > JUMP_V * 1.6
        and not any(g is not None for g in self.grabbed)
        and not self.move[0] and not self.move[1]
        and self.body.position.y < BODY_R * 4):
      print(f"BOUNCE v.y={self.body.velocity.y:.0f} v.x={self.body.velocity.x:.0f} pos=({self.body.position.x:.1f},{self.body.position.y:.1f}) grounded={grounded}")
    # <STRANGE>#385 diagnostic: catch the phantom bounce moment; remove once root cause is confirmed
    if self.body.velocity.y > 550 and self.body.position.y < BODY_R * 3:
      print(f"BOUNCE v.y={self.body.velocity.y:.0f} y={self.body.position.y:.0f} grounded={grounded} grabbed={[g is not None for g in self.grabbed]} move={self.move}")
    pitoned = any(g is not None for g in self.grabbed)
    # <STRANGE>#729 while held to a peg, never use ground drag; brushing floor mid-swing would kill momentum
    drag = AIR_DRAG if pitoned else (GROUND_DRAG if grounded else AIR_DRAG)
    # <STRANGE>#430 cheats re-queue every frame while space is held, so air-jump becomes flight
    if self.cheats and self.jump:
      self.jump_queued = True
    if self.jump_queued and (grounded or pitoned or self.cheats):
      self.body.velocity = (self.body.velocity.x, JUMP_V)
      self.jump_queued = False
      self.jumped_this_frame = True
      if self.sound is not None:
        self.sound.play("jump")
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
        if (self.held[i] is None and self.grabbed[i] is None and not self.grab_lock[i]
            and self.grab_cooldown[i] <= 0 and self.stamina[i] > STAMINA_GRAB_MIN):
          item_hit = None
          for it in items:
            # <STRANGE>#539 stuck rebar is a grapplable, not a carryable; skip it here so it goes to the peg-style path
            if getattr(it, "stuck", False):
              continue
            if it.held_by is None and arm.position.get_distance(it.body.position) <= it.grab_dist():
              item_hit = it
              break
          if item_hit is not None:
            self.held[i] = item_hit
            item_hit.hold(i)
            # <STRANGE>#703 per-type pickup sfx, name from item class
            if self.sound is not None and item_hit.pickup_sound:
              self.sound.play(item_hit.pickup_sound)
        if (not self.items_only and self.held[i] is None and self.grabbed[i] is None
            and not self.grab_lock[i] and self.grab_cooldown[i] <= 0
            and self.stamina[i] > STAMINA_GRAB_MIN):
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
              # <STRANGE>#617 rope not rod: min=0 so body can hug walls without the joint fighting collision; max caps distance
              max_len = max(cur, ARM_DX)
              self.joints[i] = pymunk.SlideJoint(self.body, obj.body, (0, 0), anchor, 0, max_len)
              self.joints[i].max_force = REEL_MAX_FORCE
              self.rope_len[i] = max_len
              self.space.add(self.joints[i])
              break
        if self.grabbed[i] is not None:
          if self.rope_len[i] > ARM_DX:
            self.rope_len[i] = max(ARM_DX, self.rope_len[i] - per_sec(REEL_SPEED, dt))
            # <STRANGE>#618 min stays 0; only max reels in. Body can go closer than ARM_DX if physics pushes it
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
        # <STRANGE>#499 rebar offsets the free-hand rest position by ±90deg (left -90, right +90)
        held_item = self.held[i]
        if held_item is not None and held_item.hand_angle is not None:
          # <STRANGE>#541 rebar hand must never sit below the body; pick the perpendicular with positive Y from the two options
          d = self.arm_dir[i]
          a1 = d.rotated(math.pi / 2)
          a2 = d.rotated(-math.pi / 2)
          rest_dir = a1 if a1.y >= a2.y else a2
        else:
          rest_dir = self.arm_dir[i]
        target_pos = self.body.position + rest_dir * ARM_DX
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
      # <NOTE>#463 offset so the item's hold point lands under the hand, not its center
      # <STRANGE>#484 angle must be resolved first; hold_offset is local so it rotates with the item
      k = smooth(0.25, dt)
      # <STRANGE>#493 rebar angle follows arm direction plus per-hand offset; arm_dir already points at cursor
      # <STRANGE>#510 rebar tip points at the cursor: angle from hand position to mouse, +pi/2 because local +Y is the far end
      if item.hand_angle is not None:
        hx = arm.position.x + ITEM_OFFSET * side
        hy = arm.position.y
        ddx = mx - hx
        ddy = wy - hy
        if ddx * ddx + ddy * ddy < 1:
          target_a = item.body.angle
        else:
          target_a = math.atan2(ddy, ddx) + math.pi / 2
      else:
        target_a = 0.0
      a = item.body.angle
      da = (target_a - a + math.pi) % (2 * math.pi) - math.pi
      if abs(da) > 1e-3:
        item.body.angle = a + da * k
      else:
        item.body.angle = target_a
      hox, hoy = item.hold_offset
      c, sn = math.cos(item.body.angle), math.sin(item.body.angle)
      rx = hox * c - hoy * sn
      ry = hox * sn + hoy * c
      tx = arm.position.x + ITEM_OFFSET * side - rx
      ty = arm.position.y - ry
      # <STRANGE>#506 rebar is allowed to visually sink below the floor while held; clamp only round items so they don't fall through
      if item.hand_angle is None:
        r = item.radius()
        if ty < r:
          ty = r
      item.body.position = pymunk.Vec2d(tx, ty)
      item.body.velocity = (0, 0)
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
      if self.grab_cooldown[i] > 0:
        self.grab_cooldown[i] = max(0.0, self.grab_cooldown[i] - dt)

    # <STRANGE>#391 HUD decay per frame: flash fades linearly on use
    for i in range(2):
      if self.hud_flash[i] > 0:
        self.hud_flash[i] = max(0.0, self.hud_flash[i] - dt / HUD_FLASH_DURATION)

    # <STRANGE>#415 fx tick: soda completion applies stamina; dead fx also destroy their item ref
    for fx in self.consume_fx:
      fx.update(dt)
      if fx.dead and fx.item is not None:
        fx.item.destroy()
        fx.item = None
    self.consume_fx = [fx for fx in self.consume_fx if not fx.dead]


  def draw(self, screen, cam):
    sc = cam.scale
    bx, by = cam.to_screen(*self.body.position)
    pygame.draw.circle(screen, (255, 255, 255), (int(bx), int(by)), int(BODY_R * sc))
    # <STRANGE>#416 consume fx draws on top of the body so the fly-in reads clearly
    for fx in self.consume_fx:
      fx.draw(screen, cam)
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
        it = self.held[i]
        # <STRANGE>#672 held item shakes along with the arm when stamina is low; shake is screen px, convert to world for draw_at
        if s_t < 0.5:
          shx = random.uniform(-shake, shake) / sc
          shy = random.uniform(-shake, shake) / sc
          it.draw_at(screen, cam, (it.body.position.x + shx, it.body.position.y + shy), it.body.angle, 255, 1.0)
        else:
          it.draw(screen, cam)
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

  def _ensure_hud_labels(self):
    # <STRANGE>#392 lazy cache; Q/E rendered once with white, alpha applied per blit via set_alpha
    if self._hud_labels is not None:
      return
    font = pygame.font.SysFont(None, 64)
    self._hud_labels = [font.render("Q", True, (255, 255, 255)), font.render("E", True, (255, 255, 255))]

  def draw_hud(self, screen, cam):
    # <STRANGE>#351 HUD is screen-space; identity cam trick reuses item.draw_at without touching world logic
    sc = cam.scale
    sw, sh = screen.get_size()
    cx, cy = sw / 2, sh / 2
    # <STRANGE>#352 offset = 4 player diameters / 2 = 4*BODY_R; distance between circle centers is 8*BODY_R
    offset = 4 * BODY_R * sc
    r = int(BODY_R * sc)
    self._ensure_hud_labels()
    for i in range(2):
      hx = cx + (-offset if i == 0 else offset)
      hy = cy
      s_t = max(0.0, min(1.0, self.stamina[i] / STAMINA_MAX))
      # <STRANGE>#673 HUD slot shakes as one unit when stamina is low; same amplitude as the world arm
      if s_t < 0.5:
        hud_shake = SHAKE_MAX * (1 - s_t * 2) * sc
        hx += random.uniform(-hud_shake, hud_shake)
        hy += random.uniform(-hud_shake, hud_shake)
      arm_color = (223, int(223 * s_t), int(223 * s_t))
      it = self.held[i]
      base_a = HUD_BASE_ALPHA if it is not None else HUD_BASE_ALPHA_EMPTY
      alpha = int(base_a + HUD_FLASH_ALPHA * self.hud_flash[i])
      surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
      # <STRANGE>#357 fill-only HUD circle, low alpha; alpha rises briefly on use then decays
      pygame.draw.circle(surf, (*arm_color, alpha), (r, r), r)
      # <STRANGE>#555 f-mode indicator: semi-transparent white ring around each hud circle
      if self.items_only:
        ring_w = max(1, int(HUD_ITEMSMODE_RING_W * sc))
        pygame.draw.circle(surf, (255, 255, 255, HUD_ITEMSMODE_RING_ALPHA), (r, r), r - ring_w // 2, ring_w)
      screen.blit(surf, (int(hx) - r, int(hy) - r))
      # <STRANGE>#402 label always visible: big center when empty, small on the bottom edge when holding
      lbl = self._hud_labels[i]
      if it is None:
        lbl.set_alpha(HUD_LABEL_ALPHA_EMPTY)
        screen.blit(lbl, lbl.get_rect(center=(int(hx), int(hy))))
      else:
        # <STRANGE>#353 identity cam: to_screen returns coords unchanged so item renders in HUD space; scale 1.0
        it.draw_at(screen, _HUDScreenCam(sc), (hx, hy), 0.0, 160, 1.0)
        # <STRANGE>#403 small label at bottom of the circle outline, alpha slightly higher than the empty variant
        sw2 = max(1, int(lbl.get_width() * HUD_LABEL_SCALE_HELD))
        sh2 = max(1, int(lbl.get_height() * HUD_LABEL_SCALE_HELD))
        small = pygame.transform.smoothscale(lbl, (sw2, sh2))
        small.set_alpha(HUD_LABEL_ALPHA_HELD)
        # <STRANGE>#405 small text sits slightly inside the circle outline near the bottom
        ly = int(hy + r - sh2 * 0.35)
        screen.blit(small, small.get_rect(center=(int(hx), ly)))

class _HUDScreenCam:
  # <STRANGE>#354 minimal stand-in for Camera; item.draw_at only needs .scale and .to_screen
  def __init__(self, scale):
    self.scale = scale
  def to_screen(self, x, y):
    return (x, y)
