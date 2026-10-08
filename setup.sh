#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

old = """    # <TODO>#385 diagnostic: log any upward spike post-integration; pre_vy alone misses solver-generated impulses
    if body.velocity.y > JUMP_V * 1.1 and not any(g is not None for g in self.grabbed) and not self.jump:
      print(f"SPIKE pre={pre_vy:.0f} post={body.velocity.y:.0f} vx={body.velocity.x:.0f} pos=({body.position.x:.1f},{body.position.y:.1f}) grounded={grounded} move={self.move}")"""
new = """    # <TODO>#385 diagnostic: any positive velocity jump > 300 in one step is anomalous; skip deliberate jump / reel
    if (body.velocity.y - pre_vy > 300
        and not self.jump
        and not any(g is not None for g in self.grabbed)):
      print(f"BUMP pre={pre_vy:.0f} post={body.velocity.y:.0f} dvy={body.velocity.y - pre_vy:.0f} vx={body.velocity.x:.0f} pos=({body.position.x:.1f},{body.position.y:.1f}) grounded={grounded} move={self.move}")"""
assert old in s, "SPIKE diag"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('game/entities/player.py').read()); print('syntax ok')"