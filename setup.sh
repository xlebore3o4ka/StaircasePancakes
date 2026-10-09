#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/game.py"
s = open(p).read()

old = """      player = Player(space, (0, BODY_R), cheats=self.cheats)"""
new = """      player = Player(space, (0, BODY_R), cheats=self.cheats)
      spawn_y = BODY_R"""
assert old in s, "player init"
s = s.replace(old, new, 1)

old = """        hud_info.draw(w.screen, player.body.position.y)"""
new = """        # <STRANGE>#620 height is distance from spawn, not absolute y
        hud_info.draw(w.screen, player.body.position.y - spawn_y)"""
assert old in s, "hud draw"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/hud_info.py"
s = open(p).read()

old = """    meters = max(0.0, (height_px - BODY_R) * HUD_METERS_PER_PX)"""
new = """    meters = max(0.0, height_px * HUD_METERS_PER_PX)"""
assert old in s, "meters"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['game/game.py','game/entities/hud_info.py']]; print('syntax ok')"

git add -A
git commit -m "hud: height measured from spawn point"