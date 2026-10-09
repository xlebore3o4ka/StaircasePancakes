#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/core/physics.py"
s = open(p).read()

old = "  floor.elasticity = 0.3"
new = "  floor.elasticity = 0.0"
assert old in s, "floor elasticity"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/platform.py"
s = open(p).read()

old = "    shape.elasticity = 0.3"
new = "    shape.elasticity = 0.0"
assert old in s, "platform elasticity"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "shared/const.py"
s = open(p).read()

old = "CUBE_ELASTICITY = 0.08\n"
new = "CUBE_ELASTICITY = 0.0\n"
assert old in s, "cube elasticity"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; print('ok')"

git add -A
git commit -m "debug: elasticity 0 everywhere to isolate bounce source"