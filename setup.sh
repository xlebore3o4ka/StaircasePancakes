#!/bin/sh
set -e

cat > shared/physics_util.py <<'EOF'
import pymunk


def stop_incoming(body):
  """Zero the velocity component that points INTO a floor/platform surface.

  Physics bias (solver push-out) shows up as extra velocity pointing OUT of the
  surface after a deep hit; because we only clamp the incoming direction, a bias
  push never lands and the bounce never appears. Motion *away* from the surface
  and tangential sliding are both preserved, so no sticking."""
  def cb(arb, data):
    a, b = arb.shapes
    if a.body is body:
      other = b
      n = -arb.contact_point_set.normal
    elif b.body is body:
      other = a
      n = arb.contact_point_set.normal
    else:
      return True
    if not (other.filter.categories & 0b10):
      return True
    v = data[0]
    proj = v.x * n.x + v.y * n.y
    if proj < 0:
      data[0] = pymunk.Vec2d(v.x - n.x * proj, v.y - n.y * proj)
    return True
  box = [body.velocity]
  body.each_arbiter(cb, box)
  body.velocity = box[0]
EOF

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

old = "from shared.physics_util import has_ground_contact\n"
new = "from shared.physics_util import stop_incoming\n"
assert old in s, "player imports"
s = s.replace(old, new, 1)

old = """  def post_step(self, dt):
    # <STRANGE>#583 runs after space.step: solver bias impulses are applied by then
    # <STRANGE>#628 only vertical bias from a floor/platform contact; wall contacts skipped to avoid sticking
    if has_ground_contact(self.body) and not self.jumped_this_frame:
      if self.body.velocity.y > 0:
        self.body.velocity = (self.body.velocity.x, 0.0)
"""
new = """  def post_step(self, dt):
    # <STRANGE>#583 runs after space.step: solver bias impulses are applied by then
    # <STRANGE>#629 one-sided clamp: kill only the velocity component heading INTO a wall/floor
    if not self.jumped_this_frame:
      stop_incoming(self.body)
"""
assert old in s, "player post_step"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/item.py"
s = open(p).read()

old = "from shared.physics_util import has_ground_contact\n"
new = "from shared.physics_util import stop_incoming\n"
assert old in s, "item imports"
s = s.replace(old, new, 1)

old = """  def post_step(self):
    # <STRANGE>#596 ignore kinematic items (held, stuck) — their velocity is set by gameplay, not physics
    if self.body.body_type != pymunk.Body.DYNAMIC:
      return
    # <STRANGE>#597 upward vy at ground contact is solver bias or leftover bounce; clamp flat
    if self.body.velocity.y > 0 and has_ground_contact(self.body):
      self.body.velocity = (self.body.velocity.x, 0.0)
"""
new = """  def post_step(self):
    # <STRANGE>#596 ignore kinematic items (held, stuck) — their velocity is set by gameplay, not physics
    if self.body.body_type != pymunk.Body.DYNAMIC:
      return
    # <STRANGE>#630 one-sided clamp; solver bias dies, item's own motion along the surface stays
    stop_incoming(self.body)
"""
assert old in s, "item post_step"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['shared/physics_util.py','game/entities/player.py','game/entities/item.py']]; print('syntax ok')"

git add -A
git commit -m "physics: one-sided wall clamp, no stick and no bounce"