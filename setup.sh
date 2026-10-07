#!/bin/sh
set -e

python - <<'EOF'
p = "game/entities/player.py"
s = open(p).read()

old = """        # <STRANGE>#135 below half stamina regen speeds up so recovery from a heavy grab isn't a death sentence
        mul = STAMINA_LOW_MUL if self.stamina[i] < STAMINA_LOW_THRESH else 1.0"""
new = """        # <STRANGE>#135 above half stamina regen is faster; tail-end of recovery is slower
        mul = STAMINA_LOW_MUL if self.stamina[i] > STAMINA_LOW_THRESH else 1.0"""
assert old in s, "mul line"
s = s.replace(old, new, 1)

open(p, "w").write(s)
EOF

python -c "import ast; ast.parse(open('game/entities/player.py').read()); print('syntax ok')"