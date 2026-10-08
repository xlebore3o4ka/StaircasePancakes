#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

old = """      # <STRANGE>#349 while held, angle lerps to 0 (upright); smooth() keeps this fps-independent
      k = smooth(0.25, dt)
      if abs(item.body.angle) > 1e-3:
        item.body.angle += (0 - item.body.angle) * k
      else:
        item.body.angle = 0.0"""
new = """      # <STRANGE>#349 while held, angle lerps to 0 (upright); smooth() keeps this fps-independent
      # <STRANGE>#449 wrap delta to [-pi, pi]: raw angle may be 12+ rad after spinning, lerp would unwind all turns
      k = smooth(0.25, dt)
      a = item.body.angle
      if abs(a) > 1e-3:
        da = (-a + math.pi) % (2 * math.pi) - math.pi
        item.body.angle = a + da * k
      else:
        item.body.angle = 0.0"""
assert old in s, "held angle"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('game/entities/player.py').read()); print('syntax ok')"
