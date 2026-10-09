#!/bin/sh
set -e

# переименовать обратно landing -> jump
for f in sounds/landing-*.wav; do
  [ -e "$f" ] || continue
  base=$(basename "$f")
  newname="${base/landing-/jump-}"
  mv "$f" "sounds/$newname"
done

python - <<'PYEOF'
p = "shared/const.py"
s = open(p).read()

old = 'SOUND_NAMES = ["landing"]\n'
new = 'SOUND_NAMES = ["jump"]\n'
assert old in s, "SOUND_NAMES"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

# вернуть jump sfx в момент коммита прыжка
old = """      self.jumped_this_frame = True"""
new = """      self.jumped_this_frame = True
      if self.sound is not None:
        self.sound.play("jump")"""
assert old in s, "jump commit"
s = s.replace(old, new, 1)

# убрать landing hook
old = """    # <STRANGE>#688 landing sfx: airborne last frame, on ground now, not just jumped this frame
    if grounded and not self.was_grounded and not self.jumped_this_frame:
      if self.sound is not None:
        self.sound.play("landing")
    self.was_grounded = grounded

"""
if old in s:
  s = s.replace(old, "", 1)

# убрать was_grounded init
old = "    # <STRANGE>#688 track airborne -> grounded transition to fire landing sfx once\n    self.was_grounded = True\n"
if old in s:
  s = s.replace(old, "", 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['shared/const.py','game/entities/player.py']]; print('syntax ok')"

git add -A
git commit -m "sound: revert to jump sfx, drop landing variant"