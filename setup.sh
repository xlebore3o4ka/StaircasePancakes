#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/entities/item.py"
s = open(p).read()

old = """  def use(self):
    # <STRANGE>#297 spawn a random different type from the pool; if nothing else exists yet, just consume
    others = [t for t in ITEM_TYPES if t != "cube"]
    if not others:
      return (True, None)
    return (True, random.choice(others))"""
new = """  def use(self):
    # <STRANGE>#297 spawn a random different type from the pool; if nothing else exists yet, just consume
    others = [t for t in ITEM_TYPES if t != "cube"]
    if not others:
      return (True, None, 0)
    return (True, random.choice(others), 0)"""
assert old in s, "CubeItem.use"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('game/entities/item.py').read()); print('syntax ok')"