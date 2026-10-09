#!/bin/sh
set -e

python - <<'PYEOF'
p = "shared/const.py"
s = open(p).read()

old = 'SOUND_NAMES = ["jump", "hit", "soda", "pickup_cube", "pickup_soda", "pickup_rebar", "open_cube"]\n'
new = 'SOUND_NAMES = ["jump", "hit", "soda", "pickup_cube", "pickup_soda", "pickup_rebar", "open_cube", "rebar_throw", "rebar_stick"]\n'
assert old in s, "SOUND_NAMES"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/item.py"
s = open(p).read()

# attach sound ref to rebar via Level already (all items get it). Just fire on throw.
old = """    self.shape.filter = pymunk.ShapeFilter(categories=0b1000, mask=0b10)
    self.flying = True
    # <STRANGE>#530 release from hand: Level.drawables filters held_by; forgetting this hides the flying rebar
    self.held_by = None
    return "release\""""
new = """    self.shape.filter = pymunk.ShapeFilter(categories=0b1000, mask=0b10)
    self.flying = True
    # <STRANGE>#530 release from hand: Level.drawables filters held_by; forgetting this hides the flying rebar
    self.held_by = None
    # <STRANGE>#748 throw sfx; fires on Q/E release
    if self.sound is not None:
      self.sound.play("rebar_throw")
    return "release\""""
assert old in s, "on_use release"
s = s.replace(old, new, 1)

# stick sfx
old = """  def stick(self):
    # <STRANGE>#520 freeze in place; mask=0 stops all collisions
    self.flying = False
    self.stuck = True
    self.body.body_type = pymunk.Body.STATIC
    self.body.velocity = (0, 0)
    self.shape.filter = pymunk.ShapeFilter(categories=0b1000, mask=0)"""
new = """  def stick(self):
    # <STRANGE>#520 freeze in place; mask=0 stops all collisions
    self.flying = False
    self.stuck = True
    self.body.body_type = pymunk.Body.STATIC
    self.body.velocity = (0, 0)
    self.shape.filter = pymunk.ShapeFilter(categories=0b1000, mask=0)
    # <STRANGE>#749 sticking sfx on first contact; per-item ref from Level
    if self.sound is not None:
      self.sound.play("rebar_stick")"""
assert old in s, "stick"
s = s.replace(old, new, 1)

# ensure sound field on Item base
if "self.sound = None" not in s:
  old = "    # <STRANGE>#376 linear damping bleeds off energy so items settle instead of drifting; does not affect held (kinematic) state\n    self.body.linear_damping = CUBE_LINEAR_DAMPING\n    space.add(self.body, shape)"
  new = """    # <STRANGE>#376 linear damping bleeds off energy so items settle instead of drifting; does not affect held (kinematic) state
    self.body.linear_damping = CUBE_LINEAR_DAMPING
    space.add(self.body, shape)
    # <STRANGE>#713 sound manager ref, attached by Level after creation
    self.sound = None"""
  assert old in s, "item init"
  s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['shared/const.py','game/entities/item.py']]; print('syntax ok')"

git add -A
git commit -m "sound: rebar throw and stick sfx"