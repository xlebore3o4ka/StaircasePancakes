#!/bin/sh
set -e

python - <<'PYEOF'
p = "shared/const.py"
s = open(p).read()

old = 'SOUND_NAMES = ["jump", "hit", "soda", "pickup_cube", "pickup_soda", "pickup_rebar", "open_cube", "rebar_throw", "rebar_stick"]\n'
new = 'SOUND_NAMES = ["hit", "soda", "pickup_cube", "pickup_soda", "pickup_rebar", "open_cube", "rebar_throw", "rebar_stick", "peg_grab"]\n'
assert old in s, "SOUND_NAMES"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

# remove jump sfx
old = """      self.jumped_this_frame = True
      if self.sound is not None:
        self.sound.play("jump")"""
new = """      self.jumped_this_frame = True"""
assert old in s, "jump sfx"
s = s.replace(old, new, 1)

# add peg_grab sfx in the grab branch
old = """            if hit:
              world_pt, anchor = hit
              self.grabbed[i] = (obj, anchor, world_pt)
              obj.grab_count += 1"""
new = """            if hit:
              world_pt, anchor = hit
              self.grabbed[i] = (obj, anchor, world_pt)
              obj.grab_count += 1
              # <STRANGE>#752 peg grab sfx, fires on the frame the hand latches
              if self.sound is not None:
                self.sound.play("peg_grab")"""
assert old in s, "peg grab"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['shared/const.py','game/entities/player.py']]; print('syntax ok')"

git add -A
git commit -m "sound: drop jump sfx, add peg_grab"