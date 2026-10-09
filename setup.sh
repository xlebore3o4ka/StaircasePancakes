#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/entities/item.py"
s = open(p).read()

old = """  def stick(self):
    # <STRANGE>#520 freeze in place; mask=0 stops all collisions
    self.flying = False
    self.stuck = True
    self.body.body_type = pymunk.Body.STATIC
    self.body.velocity = (0, 0)
    self.shape.filter = pymunk.ShapeFilter(categories=0b1000, mask=0)
    # <STRANGE>#749 sticking sfx on first contact; per-item ref from Level
    if self.sound is not None:
      self.sound.play("rebar_stick")"""
new = """  def stick(self, cam=None):
    # <STRANGE>#520 freeze in place; mask=0 stops all collisions
    self.flying = False
    self.stuck = True
    self.body.body_type = pymunk.Body.STATIC
    self.body.velocity = (0, 0)
    self.shape.filter = pymunk.ShapeFilter(categories=0b1000, mask=0)
    # <STRANGE>#749 sticking sfx, but only if the rebar is on screen when it lands
    if self.sound is not None and cam is not None and _on_screen(self, cam):
      self.sound.play("rebar_stick")"""
assert old in s, "stick"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/level.py"
s = open(p).read()

old = """      if getattr(it, "flying", False):
        # <STRANGE>#527 rebar mask is 0b10 while flying, so shape_query returns only floor/platform touches
        hits = self.space.shape_query(it.shape)
        if hits:
          it.stick()
          continue"""
new = """      if getattr(it, "flying", False):
        # <STRANGE>#527 rebar mask is 0b10 while flying, so shape_query returns only floor/platform touches
        hits = self.space.shape_query(it.shape)
        if hits:
          it.stick(cam)
          continue"""
assert old in s, "stick call"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['game/entities/item.py','game/level.py']]; print('syntax ok')"

git add -A
git commit -m "sound: rebar_stick only when on screen"