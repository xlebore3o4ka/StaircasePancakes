#!/bin/sh
set -e

cat > shared/physics_util.py <<'EOF'
def has_ground_contact(body):
  """True if body touches a floor/platform shape with an upward-facing normal."""
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
EOF

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

# import
old = "from shared.smooth import smooth, per_sec\n"
new = "from shared.smooth import smooth, per_sec\nfrom shared.physics_util import has_ground_contact\n"
if old in s and "has_ground_contact" not in s:
  s = s.replace(old, new, 1)

# post_step: minimal vertical clamp
old = """  def _use(self, i):"""
new = """  def post_step(self, dt):
    # <STRANGE>#652 on ground, not jumping this frame, vy up -> solver bias; clamp to zero
    if self.jumped_this_frame:
      return
    if self.body.velocity.y > 0 and has_ground_contact(self.body):
      self.body.velocity = (self.body.velocity.x, 0.0)

  def _use(self, i):"""
if "def post_step" not in s:
  assert old in s, "player _use anchor"
  s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/item.py"
s = open(p).read()

# import
old = ")\n\n\ndef _corners"
new = ")\nfrom shared.physics_util import has_ground_contact\n\n\ndef _corners"
if "has_ground_contact" not in s and old in s:
  s = s.replace(old, new, 1)

# post_step: vertical clamp on ground
old = """  def radius(self):"""
new = """  def post_step(self):
    # <STRANGE>#653 ignore kinematic items; strip upward vy at ground contact as solver bias
    if self.body.body_type != pymunk.Body.DYNAMIC:
      return
    if self.body.velocity.y > 0 and has_ground_contact(self.body):
      self.body.velocity = (self.body.velocity.x, 0.0)

  def radius(self):"""
if "def post_step" not in s:
  assert old in s, "item radius anchor"
  s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/level.py"
s = open(p).read()

# re-add it.post_step() call
old = """    for it in self.items:
      if getattr(it, "flying", False):
        # <STRANGE>#527 rebar mask is 0b10 while flying, so shape_query returns only floor/platform touches
        hits = self.space.shape_query(it.shape)
        if hits:
          it.stick()
          continue"""
new = """    for it in self.items:
      if getattr(it, "flying", False):
        # <STRANGE>#527 rebar mask is 0b10 while flying, so shape_query returns only floor/platform touches
        hits = self.space.shape_query(it.shape)
        if hits:
          it.stick()
          continue
      # <STRANGE>#654 per-item bias clamp after physics
      it.post_step()"""
if "it.post_step()" not in s:
  assert old in s, "level post_step anchor"
  s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['shared/physics_util.py','game/entities/player.py','game/entities/item.py','game/level.py']]; print('syntax ok')"

git add -A
git commit -m "physics: restore minimal vertical bias clamp (ground only, skip when jumping)"