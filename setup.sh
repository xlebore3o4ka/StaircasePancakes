#!/bin/sh
set -e

python - <<'PYEOF'
p = "shared/const.py"
s = open(p).read()

old = 'SOUND_NAMES = ["jump", "hit"]\n'
new = 'SOUND_NAMES = ["jump", "hit", "soda"]\n'
assert old in s, "SOUND_NAMES"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

old = """      if item.center_anim:
        # <STRANGE>#414 defer stamina to fx completion; item must be alive for draw_at during the anim
        self.consume_fx.append(SodaConsumeFx(self, item, angle, stamina_gain))"""
new = """      if item.center_anim:
        # <STRANGE>#414 defer stamina to fx completion; item must be alive for draw_at during the anim
        self.consume_fx.append(SodaConsumeFx(self, item, angle, stamina_gain))
        # <STRANGE>#697 soda sfx plays as the drink animation starts
        if self.sound is not None:
          self.sound.play("soda")"""
assert old in s, "soda use"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['shared/const.py','game/entities/player.py']]; print('syntax ok')"

git add -A
git commit -m "sound: soda drink sfx on consume"