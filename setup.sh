#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

old = "    if v > 0 and (v - self._pre_vy) > 100:"
new = "    if v > 0 and (v - self._pre_vy) > 300:"
assert old in s, "threshold"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('game/entities/player.py').read()); print('syntax ok')"

git add -A
git commit -m "player: raise bias clamp threshold to 300, leaves pendulum intact"