#!/bin/sh
set -e

python - <<'EOF'
p = "game/entities/player.py"
s = open(p).read()

old = "from shared.const import BODY_R, ARM_R, ARM_DX, JUMP_V\n"
new = "from shared.const import BODY_R, ARM_R, ARM_DX, JUMP_V, PEG_R\n"
assert old in s, "player shared import"
s = s.replace(old, new, 1)

old = "    from shared.const import PEG_R\n    GRAB_DIST = PEG_R + ARM_R + 20"
new = "    GRAB_DIST = PEG_R + ARM_R + 20"
assert old in s, "inner import"
s = s.replace(old, new, 1)

open(p, "w").write(s)
EOF

python -c "import ast; ast.parse(open('game/entities/player.py').read()); print('player syntax ok')"