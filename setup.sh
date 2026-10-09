#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

# state
old = "    self.grab_lock = [False, False]\n"
new = """    self.grab_lock = [False, False]
    # <STRANGE>#646 cooldown seconds per hand; blocks NEW grabs even while button is held
    self.grab_cooldown = [0.0, 0.0]
"""
assert old in s, "grab_lock init"
s = s.replace(old, new, 1)

# in _use, "release" path sets cooldown
old = """    r = item.on_use(self, i)
    if r == "release":
      self.held[i] = None
      self.grab_lock[i] = True
      return"""
new = """    r = item.on_use(self, i)
    if r == "release":
      self.held[i] = None
      self.grab_lock[i] = True
      # <STRANGE>#647 rebar shoots out of hand; block re-grab for a moment so it clears the arm radius
      self.grab_cooldown[i] = 0.5
      return"""
assert old in s, "_use release"
s = s.replace(old, new, 1)

# tick cooldown in update (find place near shake_t decrement)
old = """    for i in range(2):
      if self.shake_t[i] > 0:
        self.shake_t[i] -= dt
        if self.shake_t[i] < 0:
          self.shake_t[i] = 0.0"""
new = """    for i in range(2):
      if self.shake_t[i] > 0:
        self.shake_t[i] -= dt
        if self.shake_t[i] < 0:
          self.shake_t[i] = 0.0
      if self.grab_cooldown[i] > 0:
        self.grab_cooldown[i] = max(0.0, self.grab_cooldown[i] - dt)"""
assert old in s, "shake tick"
s = s.replace(old, new, 1)

# gate grab checks on cooldown
old = """        if self.held[i] is None and self.grabbed[i] is None and not self.grab_lock[i] and self.stamina[i] > STAMINA_GRAB_MIN:
          item_hit = None"""
new = """        if (self.held[i] is None and self.grabbed[i] is None and not self.grab_lock[i]
            and self.grab_cooldown[i] <= 0 and self.stamina[i] > STAMINA_GRAB_MIN):
          item_hit = None"""
assert old in s, "item grab gate"
s = s.replace(old, new, 1)

old = """        if (not self.items_only and self.held[i] is None and self.grabbed[i] is None
            and not self.grab_lock[i] and self.stamina[i] > STAMINA_GRAB_MIN):
          for obj in pegs:"""
new = """        if (not self.items_only and self.held[i] is None and self.grabbed[i] is None
            and not self.grab_lock[i] and self.grab_cooldown[i] <= 0
            and self.stamina[i] > STAMINA_GRAB_MIN):
          for obj in pegs:"""
assert old in s, "peg grab gate"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('game/entities/player.py').read()); print('syntax ok')"

git add -A
git commit -m "player: 0.5s grab cooldown after rebar release"