#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

old = """  def post_step(self, dt):
    # <STRANGE>#652 on ground, not jumping this frame, vy up -> solver bias; clamp to zero
    if self.jumped_this_frame:
      return
    if self.body.velocity.y > 0 and has_ground_contact(self.body):
      self.body.velocity = (self.body.velocity.x, 0.0)
"""
new = """  def post_step(self, dt):
    # <STRANGE>#656 bias pushes body out of contact in the same step, so has_ground_contact is already False
    # <STRANGE>#656 fallback: any vy above jump speed with nothing pulling is impossible -> clamp
    if self.jumped_this_frame:
      return
    if self.body.velocity.y > JUMP_V * 1.05:
      if not any(g is not None for g in self.grabbed):
        self.body.velocity = (self.body.velocity.x, 0.0)
        return
    if self.body.velocity.y > 0 and has_ground_contact(self.body):
      self.body.velocity = (self.body.velocity.x, 0.0)
"""
assert old in s, "post_step"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('game/entities/player.py').read()); print('syntax ok')"

git add -A
git commit -m "player: hard clamp on impossible upward speed when no peg is held"