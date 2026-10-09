#!/bin/sh
set -e

python - <<'PYEOF'
p = "shared/physics_util.py"
s = open(p).read()

old = "SLOP = 1.0\n"
new = """SLOP = 1.0
# <STRANGE>#626 deep penetration is a stuck body; solver bias is the only way out, don't strip it
ESCAPE_PEN = 8.0
"""
assert old in s, "SLOP"
s = s.replace(old, new, 1)

old = """    if max_pen <= SLOP:
      return True"""
new = """    if max_pen <= SLOP:
      return True
    if max_pen > ESCAPE_PEN:
      return True"""
assert old in s, "max_pen check"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('shared/physics_util.py').read()); print('syntax ok')"

git add -A
git commit -m "physics: skip kill_bias when penetration is deep (stuck escape)"