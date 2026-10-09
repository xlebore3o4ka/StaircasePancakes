#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/level.py"
s = open(p).read()

old = """    self.pegs = []
    for p in data.get("pegs", []):
      if isinstance(p, dict):
        self.pegs.append(Peg(space, (p["x"], p["y"])))
      else:
        self.pegs.append(Peg(space, tuple(p)))
    self.platforms = []
    for pd in data.get("platforms", []):
      self.platforms.append(Platform(
        space, (pd["x"], pd["y"]),
        w=pd.get("w", PLAT_W),
        h=pd.get("h", PLAT_H),
        fill=tuple(pd.get("fill", PLAT_FILL)),
        edge=tuple(pd.get("edge", PLAT_EDGE)),
      ))
    self.backgrounds = [
      Background((bd["x"], bd["y"]), bd["w"], bd["h"], tuple(bd.get("color", BG_FILL)))
      for bd in data.get("backgrounds", [])
    ]
    self.items = [make_item(space, it) for it in data.get("items", [])]"""
new = """    # <STRANGE>#699 layer from JSON overrides class default; editor writes it, game must read it back
    self.pegs = []
    for p in data.get("pegs", []):
      if isinstance(p, dict):
        peg = Peg(space, (p["x"], p["y"]))
        if "layer" in p:
          peg.layer = int(p["layer"])
        self.pegs.append(peg)
      else:
        self.pegs.append(Peg(space, tuple(p)))
    self.platforms = []
    for pd in data.get("platforms", []):
      plat = Platform(
        space, (pd["x"], pd["y"]),
        w=pd.get("w", PLAT_W),
        h=pd.get("h", PLAT_H),
        fill=tuple(pd.get("fill", PLAT_FILL)),
        edge=tuple(pd.get("edge", PLAT_EDGE)),
      )
      if "layer" in pd:
        plat.layer = int(pd["layer"])
      self.platforms.append(plat)
    self.backgrounds = []
    for bd in data.get("backgrounds", []):
      bg = Background((bd["x"], bd["y"]), bd["w"], bd["h"], tuple(bd.get("color", BG_FILL)))
      if "layer" in bd:
        bg.layer = int(bd["layer"])
      self.backgrounds.append(bg)
    self.items = []
    for it_spec in data.get("items", []):
      item = make_item(space, it_spec)
      if "layer" in it_spec:
        item.layer = int(it_spec["layer"])
      self.items.append(item)"""
assert old in s, "level init"
s = s.replace(old, new, 1)

# то же при спавне из коробки — пробросить layer, если он есть в spec
old = """    it = make_item(self.space, full)
    # <STRANGE>#370 initial velocity set after make_item so the body is already dynamic at spawn
    it.body.velocity = vel
    self.items.append(it)"""
new = """    it = make_item(self.space, full)
    if "layer" in spec:
      it.layer = int(spec["layer"])
    # <STRANGE>#370 initial velocity set after make_item so the body is already dynamic at spawn
    it.body.velocity = vel
    self.items.append(it)"""
assert old in s, "spawn_item"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('game/level.py').read()); print('syntax ok')"

git add -A
git commit -m "level: read layer overrides from JSON instead of ignoring them"