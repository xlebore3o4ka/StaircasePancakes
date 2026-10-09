#!/bin/sh
set -e

python - <<'PYEOF'
p = "shared/const.py"
s = open(p).read()

old = 'SOUND_NAMES = ["hit", "soda", "pickup_cube", "pickup_soda", "pickup_rebar", "open_cube", "rebar_throw", "rebar_stick", "peg_grab"]\n'
new = 'SOUND_NAMES = ["hit", "soda", "pickup_cube", "pickup_soda", "pickup_rebar", "open_cube", "rebar_throw", "rebar_stick", "peg_grab", "step"]\n'
assert old in s, "SOUND_NAMES"
s = s.replace(old, new, 1)

old = "HIT_COOLDOWN = 0.08\n"
new = "HIT_COOLDOWN = 0.08\nSTEP_INTERVAL = 0.32\n"
assert old in s, "HIT_COOLDOWN"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

# import STEP_INTERVAL
if "STEP_INTERVAL" not in s:
  old = ", HIT_VOL_MIN, HIT_VOL_MAX, HIT_COOLDOWN\n"
  new = ", HIT_VOL_MIN, HIT_VOL_MAX, HIT_COOLDOWN, STEP_INTERVAL\n"
  if old in s:
    s = s.replace(old, new, 1)

# init
if "self._step_cd" not in s:
  old = "    self._hit_cd = 0.0\n"
  new = "    self._hit_cd = 0.0\n    # <STRANGE>#756 footstep sfx cooldown; fires on ground while walking\n    self._step_cd = 0.0\n"
  assert old in s, "hit_cd init"
  s = s.replace(old, new, 1)

# tick + trigger, put it near hud cooldowns area
old = """    # <STRANGE>#391 HUD decay per frame: flash fades linearly on use
    for i in range(2):
      if self.hud_flash[i] > 0:
        self.hud_flash[i] = max(0.0, self.hud_flash[i] - dt / HUD_FLASH_DURATION)"""
new = """    # <STRANGE>#756 footsteps: on ground, one move key pressed, interval elapsed
    if self._step_cd > 0:
      self._step_cd -= dt
    walking = grounded and (self.move[0] or self.move[1])
    if walking and self._step_cd <= 0:
      if self.sound is not None:
        self.sound.play("step")
      self._step_cd = STEP_INTERVAL
    elif not walking:
      self._step_cd = 0.0

    # <STRANGE>#391 HUD decay per frame: flash fades linearly on use
    for i in range(2):
      if self.hud_flash[i] > 0:
        self.hud_flash[i] = max(0.0, self.hud_flash[i] - dt / HUD_FLASH_DURATION)"""
assert old in s, "hud decay"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['shared/const.py','game/entities/player.py']]; print('syntax ok')"

git add -A
git commit -m "sound: footstep sfx while walking on ground"