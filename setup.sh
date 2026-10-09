#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

# 1. world item shake: replace plain draw with shaken draw_at
old = """      if self.held[i] is not None:
        self.held[i].draw(screen, cam)
      arm_color = (223, int(223 * s_t), int(223 * s_t))"""
new = """      if self.held[i] is not None:
        it = self.held[i]
        # <STRANGE>#672 held item shakes along with the arm when stamina is low; shake is screen px, convert to world for draw_at
        if s_t < 0.5:
          shx = random.uniform(-shake, shake) / sc
          shy = random.uniform(-shake, shake) / sc
          it.draw_at(screen, cam, (it.body.position.x + shx, it.body.position.y + shy), it.body.angle, 255, 1.0)
        else:
          it.draw(screen, cam)
      arm_color = (223, int(223 * s_t), int(223 * s_t))"""
assert old in s, "world item draw"
s = s.replace(old, new, 1)

# 2. HUD circle + label + held item shake together
old = """      hx = cx + (-offset if i == 0 else offset)
      hy = cy
      s_t = max(0.0, min(1.0, self.stamina[i] / STAMINA_MAX))
      arm_color = (223, int(223 * s_t), int(223 * s_t))"""
new = """      hx = cx + (-offset if i == 0 else offset)
      hy = cy
      s_t = max(0.0, min(1.0, self.stamina[i] / STAMINA_MAX))
      # <STRANGE>#673 HUD slot shakes as one unit when stamina is low; same amplitude as the world arm
      if s_t < 0.5:
        hud_shake = SHAKE_MAX * (1 - s_t * 2) * sc
        hx += random.uniform(-hud_shake, hud_shake)
        hy += random.uniform(-hud_shake, hud_shake)
      arm_color = (223, int(223 * s_t), int(223 * s_t))"""
assert old in s, "HUD shake"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('game/entities/player.py').read()); print('syntax ok')"

git add -A
git commit -m "player: low-stamina shake applies to held item and HUD slot too"