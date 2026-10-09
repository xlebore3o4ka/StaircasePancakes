#!/bin/sh
set -e

python - <<'PYEOF'
p = "shared/const.py"
s = open(p).read()

old = 'SOUND_NAMES = ["jump", "hit", "soda"]\n'
new = 'SOUND_NAMES = ["jump", "hit", "soda", "pickup_cube", "pickup_soda", "pickup_rebar"]\n'
assert old in s, "SOUND_NAMES"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/item.py"
s = open(p).read()

# атрибут pickup_sound у Item
old = """class Item:
  layer = LAYER_ITEM
"""
new = """class Item:
  layer = LAYER_ITEM
  # <STRANGE>#702 sfx name played on pickup; each subclass overrides
  pickup_sound = None
"""
assert old in s, "Item class"
s = s.replace(old, new, 1)

old = """class CubeItem(Item):
  def __init__(self, space, pos, contents=None):"""
new = """class CubeItem(Item):
  pickup_sound = "pickup_cube"

  def __init__(self, space, pos, contents=None):"""
assert old in s, "CubeItem"
s = s.replace(old, new, 1)

old = """class SodaItem(Item):
  center_anim = True"""
new = """class SodaItem(Item):
  center_anim = True
  pickup_sound = "pickup_soda\""""
assert old in s, "SodaItem"
s = s.replace(old, new, 1)

old = """class RebarItem(Item):
  # <STRANGE>#513 hold offset toward the near end"""
new = """class RebarItem(Item):
  pickup_sound = "pickup_rebar"
  # <STRANGE>#513 hold offset toward the near end"""
assert old in s, "RebarItem"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

old = """          if item_hit is not None:
            self.held[i] = item_hit
            item_hit.hold(i)"""
new = """          if item_hit is not None:
            self.held[i] = item_hit
            item_hit.hold(i)
            # <STRANGE>#703 per-type pickup sfx, name from item class
            if self.sound is not None and item_hit.pickup_sound:
              self.sound.play(item_hit.pickup_sound)"""
assert old in s, "item grab"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['shared/const.py','game/entities/item.py','game/entities/player.py']]; print('syntax ok')"

git add -A
git commit -m "sound: per-item pickup sfx driven by item.pickup_sound"