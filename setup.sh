#!/bin/sh
set -e

cat > game/entities/puff.py <<'EOF'
import random
import pygame
from shared.const import PUFF_COUNT, PUFF_DURATION, PUFF_R_MIN, PUFF_R_MAX, PUFF_SPEED_MIN, PUFF_SPEED_MAX, PUFF_COLOR


class PuffBurst:
  # <STRANGE>#775 one-shot particle burst; player-owned, ticked every frame, removed when lifetime ends
  def __init__(self, pos):
    self.t = 0.0
    self.particles = []
    for _ in range(PUFF_COUNT):
      ang = random.uniform(0, 6.28318)
      spd = random.uniform(PUFF_SPEED_MIN, PUFF_SPEED_MAX)
      self.particles.append({
        "x": pos[0], "y": pos[1],
        "vx": spd * pygame.math.Vector2(1, 0).rotate_rad(ang).x,
        "vy": spd * pygame.math.Vector2(1, 0).rotate_rad(ang).y,
        "r": random.uniform(PUFF_R_MIN, PUFF_R_MAX),
      })

  def update(self, dt):
    self.t += dt
    if self.t >= PUFF_DURATION:
      return False
    for p in self.particles:
      p["x"] += p["vx"] * dt
      p["y"] += p["vy"] * dt
    return True

  def draw(self, screen, cam):
    k = self.t / PUFF_DURATION
    alpha = int(220 * (1.0 - k))
    if alpha <= 0:
      return
    for p in self.particles:
      r = p["r"] * (1.0 - k * 0.7)
      if r < 0.5:
        continue
      sx, sy = cam.to_screen(p["x"], p["y"])
      rr = max(1, int(r * cam.scale))
      surf = pygame.Surface((rr * 2, rr * 2), pygame.SRCALPHA)
      pygame.draw.circle(surf, (*PUFF_COLOR, alpha), (rr, rr), rr)
      screen.blit(surf, (int(sx) - rr, int(sy) - rr))
EOF

python - <<'PYEOF'
p = "shared/const.py"
s = open(p).read()

old = "STEP_INTERVAL = 0.32\n"
new = """STEP_INTERVAL = 0.32

PUFF_COUNT = 8
PUFF_DURATION = 0.5
PUFF_R_MIN = 4
PUFF_R_MAX = 10
PUFF_SPEED_MIN = 60
PUFF_SPEED_MAX = 220
PUFF_COLOR = (220, 220, 220)
"""
assert old in s, "STEP_INTERVAL"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

old = "from .consume_fx import SodaConsumeFx\n"
new = "from .consume_fx import SodaConsumeFx\nfrom .puff import PuffBurst\n"
if old in s and "PuffBurst" not in s:
  s = s.replace(old, new, 1)

if "self.puffs = []" not in s:
  old = "    self.consume_fx = []\n"
  new = "    self.consume_fx = []\n    # <STRANGE>#775 one-shot particle bursts, own list so they don't tie to consume logic\n    self.puffs = []\n"
  assert old in s, "consume_fx init"
  s = s.replace(old, new, 1)

# spawn puff on cube use
old = """    consumed, spawn_spec, stamina_gain = item.use()
    if consumed:
      if self.sound is not None and item.use_sound:
        # <STRANGE>#744 fire before item.destroy in case subclass cleanup nulls state
        self.sound.play(item.use_sound)"""
new = """    consumed, spawn_spec, stamina_gain = item.use()
    if consumed:
      if self.sound is not None and item.use_sound:
        # <STRANGE>#744 fire before item.destroy in case subclass cleanup nulls state
        self.sound.play(item.use_sound)
      # <STRANGE>#775 dust puff at the item position for cubes
      if getattr(item, "use_sound", None) == "open_cube":
        self.puffs.append(PuffBurst(item.body.position))"""
assert old in s, "use consume"
s = s.replace(old, new, 1)

# tick puffs in update
old = """    # <STRANGE>#415 fx tick: soda completion applies stamina; dead fx also destroy their item ref
    for fx in self.consume_fx:"""
new = """    # <STRANGE>#775 puff bursts tick
    self.puffs = [p for p in self.puffs if p.update(dt)]

    # <STRANGE>#415 fx tick: soda completion applies stamina; dead fx also destroy their item ref
    for fx in self.consume_fx:"""
assert old in s, "fx tick"
s = s.replace(old, new, 1)

# draw puffs (above body, below arms feels right — same loop as consume_fx)
old = """    # <STRANGE>#416 consume fx draws on top of the body so the fly-in reads clearly
    for fx in self.consume_fx:
      fx.draw(screen, cam)"""
new = """    # <STRANGE>#416 consume fx draws on top of the body so the fly-in reads clearly
    for fx in self.consume_fx:
      fx.draw(screen, cam)
    for p in self.puffs:
      p.draw(screen, cam)"""
assert old in s, "fx draw"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['shared/const.py','game/entities/puff.py','game/entities/player.py']]; print('syntax ok')"

git add -A
git commit -m "fx: dust puff burst on cube open"