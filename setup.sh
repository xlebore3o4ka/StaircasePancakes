#!/bin/sh
set -e

python - <<'PYEOF'
p = "shared/const.py"
s = open(p).read()

old = "REBAR_RECOIL_AIR = 1.5\n"
new = "REBAR_RECOIL_AIR = 1.3\n"
assert old in s, "REBAR_RECOIL_AIR"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('shared/const.py').read()); print('syntax ok')"