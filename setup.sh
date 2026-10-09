#!/bin/sh
set -e

python - <<'PYEOF'
p = "shared/physics_util.py"
s = open(p).read()

new_content = '''import pymunk


def has_ground_contact(body):
  """True if body touches a floor/platform shape with an upward normal."""
  result = [False]
  def cb(arb, data):
    a, b = arb.shapes
    if a.body is body:
      other = b
      ny = -arb.contact_point_set.normal.y
    elif b.body is body:
      other = a
      ny = arb.contact_point_set.normal.y
    else:
      return True
    if not (other.filter.categories & 0b10):
      return True
    if ny > 0.5:
      result[0] = True
      return False
    return True
  body.each_arbiter(cb, None)
  return result[0]
'''

open(p, "w").write(new_content)
PYEOF

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

old = "from shared.physics_util import kill_bias\n"
new = "from shared.physics_util import has_ground_contact\n"
assert old in s, "player imports"
s = s.replace(old, new, 1)

old = """  def post_step(self, dt):
    # <STRANGE>#583 runs after space.step: solver bias impulses are applied by then
    # <STRANGE>#623 penetration-threshold based, so wall brushes and rolling contacts are untouched
    kill_bias(self.body)
"""
new = """  def post_step(self, dt):
    # <STRANGE>#583 runs after space.step: solver bias impulses are applied by then
    # <STRANGE>#628 only vertical bias from a floor/platform contact; wall contacts skipped to avoid sticking
    if has_ground_contact(self.body) and not self.jumped_this_frame:
      if self.body.velocity.y > 0:
        self.body.velocity = (self.body.velocity.x, 0.0)
"""
assert old in s, "player post_step"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/item.py"
s = open(p).read()

old = "from shared.physics_util import kill_bias\n"
new = "from shared.physics_util import has_ground_contact\n"
assert old in s, "item imports"
s = s.replace(old, new, 1)

old = """  def post_step(self):
    # <STRANGE>#596 ignore kinematic items (held, stuck) — their velocity is set by gameplay, not physics
    if self.body.body_type != pymunk.Body.DYNAMIC:
      return
    # <STRANGE>#614 strip solver bias from items; threshold-based, so bouncing stays alive
    kill_bias(self.body)
"""
new = """  def post_step(self):
    # <STRANGE>#596 ignore kinematic items (held, stuck) — their velocity is set by gameplay, not physics
    if self.body.body_type != pymunk.Body.DYNAMIC:
      return
    # <STRANGE>#597 upward vy at ground contact is solver bias or leftover bounce; clamp flat
    if self.body.velocity.y > 0 and has_ground_contact(self.body):
      self.body.velocity = (self.body.velocity.x, 0.0)
"""
assert old in s, "item post_step"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['shared/physics_util.py','game/entities/player.py','game/entities/item.py']]; print('syntax ok')"

git add -A
git commit -m "physics: revert to vertical-only bias clamp; wall sticking fixed"