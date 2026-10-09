#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/entities/item.py"
s = open(p).read()

old = """  def post_step(self):
    # <STRANGE>#596 ignore kinematic items (held, stuck) — their vy is set by gameplay, not physics
    if self.body.body_type != pymunk.Body.DYNAMIC:
      return
    # <STRANGE>#597 any upward vy at ground contact is solver bias or bounce; clamp flat
    if self.body.velocity.y > 0 and has_ground_contact(self.body):
      self.body.velocity = (self.body.velocity.x, 0.0)
"""
new = """  def post_step(self):
    # <STRANGE>#596 ignore kinematic items (held, stuck) — their velocity is set by gameplay, not physics
    if self.body.body_type != pymunk.Body.DYNAMIC:
      return
    # <STRANGE>#614 strip solver bias from items; threshold-based, so bouncing stays alive
    kill_bias(self.body)
"""
assert old in s, "post_step"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('game/entities/item.py').read()); print('syntax ok')"

git add -A
git commit -m "item: finish switch to kill_bias"