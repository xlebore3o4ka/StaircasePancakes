#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/game.py"
s = open(p).read()

old = """        for _ in range(substeps):
          space.step(dt / substeps)
          # <STRANGE>#525 rebar sticking is checked after physics so arbiter list is fresh
          level.post_step(player)"""
new = """        for _ in range(substeps):
          space.step(dt / substeps)
          # <STRANGE>#525 rebar sticking is checked after physics so arbiter list is fresh
          level.post_step(player)
          # <STRANGE>#657 player bias clamp runs after every substep
          player.post_step(dt)"""
assert old in s, "game step loop"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('game/game.py').read()); print('syntax ok')"

git add -A
git commit -m "game: actually call player.post_step after each substep"