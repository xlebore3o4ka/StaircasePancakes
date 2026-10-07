#!/bin/sh
set -e

python - <<'PYEOF'
p = "shared/const.py"
s = open(p).read()

old = "CUBE_ELASTICITY = 0.35\n"
new = """CUBE_ELASTICITY = 0.35
THROW_MAX_SPEED = 1400
THROW_SMOOTH_FRAMES = 4
"""
assert old in s, "CUBE_ELASTICITY"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

old = "from shared.const import BODY_R, ARM_R, ARM_DX, JUMP_V, PEG_R, ITEM_OFFSET, ITEM_USE_SHAKE_TIME, ITEM_USE_SHAKE_AMP, ARM_HOLD_ALPHA, ARM_HOLD_SCALE\n"
new = "from shared.const import BODY_R, ARM_R, ARM_DX, JUMP_V, PEG_R, ITEM_OFFSET, ITEM_USE_SHAKE_TIME, ITEM_USE_SHAKE_AMP, ARM_HOLD_ALPHA, ARM_HOLD_SCALE, THROW_MAX_SPEED, THROW_SMOOTH_FRAMES\n"
assert old in s, "imports"
s = s.replace(old, new, 1)

old = """    # <STRANGE>#251 held[i] is an Item; throw_requested set on mouse-up, consumed in update
    self.held = [None, None]
    self.throw_requested = [False, False]
    self.shake_t = [0.0, 0.0]"""
new = """    # <STRANGE>#251 held[i] is an Item; throw_requested set on mouse-up, consumed in update
    self.held = [None, None]
    self.throw_requested = [False, False]
    self.shake_t = [0.0, 0.0]
    # <STRANGE>#288 rolling history of instant throw velocities to smooth lerp spikes
    self.throw_hist = [[], []]"""
assert old in s, "held state"
s = s.replace(old, new, 1)

old = """    # <STRANGE>#264 throws processed FIRST: otherwise arm lerps toward rest this frame and item inherits downward velocity on release
    for i in range(2):
      if self.throw_requested[i]:
        self.throw_requested[i] = False
        item = self.held[i]
        if item is not None:
          item.release(item.throw_vel)
          self.held[i] = None

    # <STRANGE>#255 held items follow arm position exactly (no lerp); throw_vel is last-frame delta * 60"""
new = """    # <STRANGE>#264 throws processed FIRST: otherwise arm lerps toward rest this frame and item inherits downward velocity on release
    for i in range(2):
      if self.throw_requested[i]:
        self.throw_requested[i] = False
        item = self.held[i]
        if item is not None:
          self._release_item(i, item)

    # <STRANGE>#255 held items follow arm position exactly (no lerp); throw_vel is last-frame delta * 60"""
assert old in s, "throw block"
s = s.replace(old, new, 1)

old = """      tx = arm.position.x + ITEM_OFFSET * side
      ty = arm.position.y
      # <STRANGE>#278 clamp held item above floor; arm can dip below y=0 and release item through the world
      # <STRANGE>#283 Vec2d is immutable, so rebuild instead of mutating .y
      r = item.radius()
      if ty < r:
        ty = r
      item.body.position = pymunk.Vec2d(tx, ty)
      item.body.velocity = (0, 0)
      item.throw_vel = (target - prev) * 60"""
new = """      tx = arm.position.x + ITEM_OFFSET * side
      ty = arm.position.y
      # <STRANGE>#278 clamp held item above floor; arm can dip below y=0 and release item through the world
      # <STRANGE>#283 Vec2d is immutable, so rebuild instead of mutating .y
      r = item.radius()
      if ty < r:
        ty = r
      item.body.position = pymunk.Vec2d(tx, ty)
      item.body.velocity = (0, 0)
      # <STRANGE>#289 average last few frames so a single lerp jump doesn't blow up throw speed
      inst = (pymunk.Vec2d(tx, ty) - prev) * 60
      hist = self.throw_hist[i]
      hist.append((inst.x, inst.y))
      if len(hist) > THROW_SMOOTH_FRAMES:
        hist.pop(0)
      ax = sum(h[0] for h in hist) / len(hist)
      ay = sum(h[1] for h in hist) / len(hist)
      item.throw_vel = (ax, ay)"""
assert old in s, "held item block"
s = s.replace(old, new, 1)

old = """    self.grabbed[i] = None
    self.rope_len[i] = None"""
new = """    self.grabbed[i] = None
    self.rope_len[i] = None

  def _release_item(self, i, item):
    # <STRANGE>#290 cap final speed; huge lerp spikes get clamped, normal throws pass through
    vx, vy = item.throw_vel
    mag = (vx * vx + vy * vy) ** 0.5
    if mag > THROW_MAX_SPEED:
      vx, vy = vx / mag * THROW_MAX_SPEED, vy / mag * THROW_MAX_SPEED
    self.throw_hist[i].clear()
    self.held[i] = None
    item.release((vx, vy))"""
assert old in s, "_release"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['shared/const.py','game/entities/player.py']]; print('syntax ok')"