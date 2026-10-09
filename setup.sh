#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

old = """    r = item.on_use(self, i)
    if r == "release":
      self.held[i] = None
      self.grab_lock[i] = True
      # <STRANGE>#647 rebar shoots out of hand; block re-grab for a moment so it clears the arm radius
      self.grab_cooldown[i] = 0.5
      return"""
new = """    r = item.on_use(self, i)
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
      return"""
assert old in s, "release path"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('game/entities/player.py').read()); print('syntax ok')"

git add -A
git commit -m "player: rebar shot releases the other hand's grab too"