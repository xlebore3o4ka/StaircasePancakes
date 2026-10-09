#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/entities/hud_info.py"
s = open(p).read()

old = """    h = int(total // 3600)
    m = int((total % 3600) // 60)
    sec = int(total % 60)
    cs = int((total * 100) % 100)
    return f"{h:02d}:{m:02d}:{sec:02d}.{cs:02d}\""""
new = """    h = int(total // 3600)
    m = int((total % 3600) // 60)
    sec = int(total % 60)
    cs = int((total * 100) % 100)
    if h > 0:
      return f"{h:02d}:{m:02d}:{sec:02d}.{cs:02d}"
    return f"{m:02d}:{sec:02d}.{cs:02d}\""""
assert old in s, "fmt"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('game/entities/hud_info.py').read()); print('syntax ok')"

git add -A
git commit -m "hud: hide hours until one hour elapsed"