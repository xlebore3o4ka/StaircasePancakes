#!/bin/sh
set -e

python - <<'PYEOF'
p = "shared/const.py"
s = open(p).read()

old = """PUFF_R_MIN = 4
PUFF_R_MAX = 10
PUFF_SPEED_MIN = 60
PUFF_SPEED_MAX = 220"""
new = """PUFF_R_MIN = 6
PUFF_R_MAX = 14
PUFF_SPEED_MIN = 30
PUFF_SPEED_MAX = 130"""
assert old in s, "puff consts"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('shared/const.py').read()); print('syntax ok')"

git add -A
git commit -m "fx: bigger and slower puff particles"