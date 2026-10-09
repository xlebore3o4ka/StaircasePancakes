#!/bin/sh
set -e

python - <<'PYEOF'
p = "shared/const.py"
s = open(p).read()

old = "THROW_SMOOTH_FRAMES = 4\n"
new = """THROW_SMOOTH_FRAMES = 4

HUD_INFO_ALPHA = 160
HUD_INFO_MARGIN = 16
HUD_INFO_LINE_GAP = 4
HUD_INFO_FONT = 24
# <NOTE>#609 1 meter = player diameter = 2 * BODY_R px
HUD_METERS_PER_PX = 1.0 / (2 * BODY_R)
"""
assert old in s, "THROW_SMOOTH_FRAMES"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

cat > game/entities/hud_info.py <<'EOF'
import pygame
from shared.const import (
  BODY_R, HUD_INFO_ALPHA, HUD_INFO_MARGIN, HUD_INFO_LINE_GAP, HUD_INFO_FONT,
  HUD_METERS_PER_PX,
)


class HudInfo:
  # <STRANGE>#605 top-left readout: elapsed time and height above ground
  def __init__(self):
    self.t = 0.0
    self.font = pygame.font.SysFont(None, HUD_INFO_FONT)
    self._cache_key = None
    self._cache = None

  def update(self, dt):
    self.t += dt

  def _fmt_time(self):
    total = int(self.t)
    h, rem = divmod(total, 3600)
    m, sec = divmod(rem, 60)
    if h > 0:
      return f"{h}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"

  def _render(self, text):
    if self._cache_key == text:
      return self._cache
    surf = self.font.render(text, True, (255, 255, 255))
    surf.set_alpha(HUD_INFO_ALPHA)
    self._cache_key = text
    self._cache = surf
    return surf

  def draw(self, screen, height_px):
    meters = max(0.0, (height_px - BODY_R) * HUD_METERS_PER_PX)
    lines = [self._fmt_time(), f"{meters:.1f} m"]
    x = HUD_INFO_MARGIN
    y = HUD_INFO_MARGIN
    for line in lines:
      surf = self._render(line)
      screen.blit(surf, (x, y))
      y += surf.get_height() + HUD_INFO_LINE_GAP
EOF

python - <<'PYEOF'
p = "game/game.py"
s = open(p).read()

old = "from .entities.floor import FloorFill\n"
new = "from .entities.floor import FloorFill\nfrom .entities.hud_info import HudInfo\n"
assert old in s, "game imports"
s = s.replace(old, new, 1)

old = "      floor_fill = FloorFill()\n"
new = "      floor_fill = FloorFill()\n      hud_info = HudInfo()\n"
assert old in s, "game init"
s = s.replace(old, new, 1)

old = """        player.draw_hud(w.screen, cam)
        w.flip()"""
new = """        player.draw_hud(w.screen, cam)
        hud_info.update(dt)
        hud_info.draw(w.screen, player.body.position.y)
        w.flip()"""
assert old in s, "game draw"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['shared/const.py','game/entities/hud_info.py','game/game.py']]; print('syntax ok')"

git add -A
git commit -m "hud: top-left timer and height readout"