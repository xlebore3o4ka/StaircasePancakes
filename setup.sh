#!/bin/sh
set -e

python - <<'PYEOF'
p = "shared/const.py"
s = open(p).read()

old = 'SOUND_NAMES = ["jump", "hit", "soda", "pickup_cube", "pickup_soda", "pickup_rebar"]\n'
new = 'SOUND_NAMES = ["jump", "hit", "soda", "pickup_cube", "pickup_soda", "pickup_rebar", "open_cube"]\n'
assert old in s, "SOUND_NAMES"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/item.py"
s = open(p).read()

# Item base: use_sound None
old = """  # <STRANGE>#702 sfx name played on pickup; each subclass overrides
  pickup_sound = None
"""
new = """  # <STRANGE>#702 sfx name played on pickup; each subclass overrides
  pickup_sound = None
  # <STRANGE>#744 sfx name played when use() consumes this item; None = silent
  use_sound = None
"""
assert old in s, "Item class"
s = s.replace(old, new, 1)

old = """class CubeItem(Item):
  pickup_sound = "pickup_cube\""""
new = """class CubeItem(Item):
  pickup_sound = "pickup_cube"
  use_sound = "open_cube\""""
assert old in s, "CubeItem"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

old = """    consumed, spawn_spec, stamina_gain = item.use()
    if consumed:"""
new = """    consumed, spawn_spec, stamina_gain = item.use()
    if consumed:
      if self.sound is not None and item.use_sound:
        # <STRANGE>#744 fire before item.destroy in case subclass cleanup nulls state
        self.sound.play(item.use_sound)"""
assert old in s, "_use consume"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['shared/const.py','game/entities/item.py','game/entities/player.py']]; print('syntax ok')"

git add -A
git commit -m "sound: open_cube sfx on cube use"