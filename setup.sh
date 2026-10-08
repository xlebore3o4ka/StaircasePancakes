#!/bin/sh
set -e

python - <<'PYEOF'
p = "shared/const.py"
s = open(p).read()
old = "SODA_STAMINA = 90\n"
new = "SODA_STAMINA = 90\nSPAWN_BOUNCE_V = 300\n"
assert old in s, "SODA_STAMINA"
s = s.replace(old, new, 1)
open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

old = "from shared.const import BODY_R, ARM_R, ARM_DX, JUMP_V, PEG_R, ITEM_OFFSET, ITEM_USE_SHAKE_TIME, ITEM_USE_SHAKE_AMP, ARM_HOLD_ALPHA, ARM_HOLD_SCALE, THROW_MAX_SPEED, THROW_SMOOTH_FRAMES\n"
new = "from shared.const import BODY_R, ARM_R, ARM_DX, JUMP_V, PEG_R, ITEM_OFFSET, ITEM_USE_SHAKE_TIME, ITEM_USE_SHAKE_AMP, ARM_HOLD_ALPHA, ARM_HOLD_SCALE, THROW_MAX_SPEED, THROW_SMOOTH_FRAMES, SPAWN_BOUNCE_V\n"
assert old in s, "imports"
s = s.replace(old, new, 1)

old = """    consumed, spawn_type, stamina_gain = item.use()
    if consumed:
      # <STRANGE>#344 pos captured BEFORE destroy; reading body after removal crashes or returns garbage
      pos = item.body.position
      item.destroy()
      self.held[i] = None
      # <STRANGE>#362 lock this hand until mouse is released; otherwise the freshly spawned item lands in the arm and gets grabbed next frame
      self.grab_lock[i] = True
      if stamina_gain:
        for j in range(2):
          self.stamina[j] = min(STAMINA_MAX, self.stamina[j] + stamina_gain)
      if spawn_type is not None:
        self.spawn_queue.append((pos, spawn_type))
    else:
      self.shake_t[i] = ITEM_USE_SHAKE_TIME"""
new = """    consumed, spawn_type, stamina_gain = item.use()
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
      self.shake_t[i] = ITEM_USE_SHAKE_TIME"""
assert old in s, "_use"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/level.py"
s = open(p).read()

old = """  def spawn_item(self, pos, type_name):
    # <STRANGE>#299 wraps pos into a spec dict so make_item stays the single entry point for item creation
    spec = {"x": pos[0], "y": pos[1], "type": type_name}
    self.items.append(make_item(self.space, spec))"""
new = """  def spawn_item(self, pos, type_name, vel=(0, 0)):
    # <STRANGE>#299 wraps pos into a spec dict so make_item stays the single entry point for item creation
    spec = {"x": pos[0], "y": pos[1], "type": type_name}
    it = make_item(self.space, spec)
    # <STRANGE>#370 initial velocity set after make_item so the body is already dynamic at spawn
    it.body.velocity = vel
    self.items.append(it)"""
assert old in s, "spawn_item"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/game.py"
s = open(p).read()

old = """        if player.spawn_queue:
          for pos, type_name in player.spawn_queue:
            level.spawn_item(pos, type_name)
          player.spawn_queue.clear()"""
new = """        if player.spawn_queue:
          for pos, type_name, vel in player.spawn_queue:
            level.spawn_item(pos, type_name, vel)
          player.spawn_queue.clear()"""
assert old in s, "spawn queue drain"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['shared/const.py','game/entities/player.py','game/level.py','game/game.py']]; print('syntax ok')"