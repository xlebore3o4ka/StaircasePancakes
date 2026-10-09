#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/level.py"
s = open(p).read()

# Level accepts sound manager
old = "class Level:\n  def __init__(self, space, path):\n    self.space = space"
new = "class Level:\n  def __init__(self, space, path, sound=None):\n    self.space = space\n    self.sound = sound"
assert old in s, "Level init"
s = s.replace(old, new, 1)

# attach sound to every item created during load
old = """    self.items = []
    for it_spec in data.get("items", []):
      item = make_item(space, it_spec)
      if "layer" in it_spec:
        item.layer = int(it_spec["layer"])
      self.items.append(item)"""
new = """    self.items = []
    for it_spec in data.get("items", []):
      item = make_item(space, it_spec)
      if "layer" in it_spec:
        item.layer = int(it_spec["layer"])
      if self.sound is not None:
        item.sound = self.sound
      self.items.append(item)"""
assert old in s, "items loop"
s = s.replace(old, new, 1)

# spawn_item also attaches
old = """    it = make_item(self.space, full)
    if "layer" in spec:
      it.layer = int(spec["layer"])"""
new = """    it = make_item(self.space, full)
    if "layer" in spec:
      it.layer = int(spec["layer"])
    if self.sound is not None:
      it.sound = self.sound"""
assert old in s, "spawn_item"
s = s.replace(old, new, 1)

# spawner items also
old = """      self.items.append(make_item(space, spec))"""
new = """      sp_item = make_item(space, spec)
      if self.sound is not None:
        sp_item.sound = self.sound
      self.items.append(sp_item)"""
if old in s:
  s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/game.py"
s = open(p).read()

old = '      level = Level(space, self.map_path)'
new = '      level = Level(space, self.map_path, sound=sound)'
assert old in s, "level init"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['game/entities/item.py','game/level.py','game/game.py']]; print('syntax ok')"

git add -A
git commit -m "sound: item impacts play hit sfx at 50% volume"