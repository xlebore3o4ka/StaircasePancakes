#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

old = """    if grounded:
      if body.velocity.y > JUMP_V * 1.05:
        body.velocity = (body.velocity.x, 0.0)
      elif abs(body.velocity.y) < 30:
        body.velocity = (body.velocity.x, 0.0)"""
new = """    if grounded:
      # <STRANGE>#549 clamp any upward spike above jump speed regardless of held keys; jump itself is exactly JUMP_V so unaffected
      if body.velocity.y > JUMP_V * 1.05:
        body.velocity = (body.velocity.x, 0.0)
      elif abs(body.velocity.y) < 30:
        body.velocity = (body.velocity.x, 0.0)"""
assert old in s, "clamp"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('game/entities/player.py').read()); print('syntax ok')"