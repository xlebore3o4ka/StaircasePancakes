#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/entities/item.py"
s = open(p).read()

old = "from shared.physics_util import has_ground_contact\n"
new = "from shared.physics_util import kill_bias\n"
assert old in s, "item imports"
s = s.replace(old, new, 1)

old = """  def post_step(self):
    # <STRANGE>#596 ignore kinematic items (held, stuck) — their velocity is set by gameplay, not physics
    if self.body.body_type != pymunk.Body.DYNAMIC:
      return
    # <STRANGE>#614 strip velocity along any floor/platform normal; solver bias and residual bounce both die here
    kill_bias(self.body)
"""
new = """  def post_step(self):
    # <STRANGE>#596 ignore kinematic items (held, stuck) — their velocity is set by gameplay, not physics
    if self.body.body_type != pymunk.Body.DYNAMIC:
      return
    # <STRANGE>#614 strip solver bias from items; threshold-based, so bouncing stays alive
    kill_bias(self.body)
"""
if old in s:
  s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('game/entities/item.py').read()); print('syntax ok')"

git add -A
git commit -m "item: use kill_bias instead of removed has_ground_contact"