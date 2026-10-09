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
    # <STRANGE>#610 always hh:mm:ss.MM; centiseconds used as MM since pygame doesn't give sub-frame timing
    total = self.t
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    sec = int(total % 60)
    cs = int((total * 100) % 100)
    if h > 0:
      return f"{h:02d}:{m:02d}:{sec:02d}.{cs:02d}"
    return f"{m:02d}:{sec:02d}.{cs:02d}"

  def _render(self, text):
    if self._cache_key == text:
      return self._cache
    surf = self.font.render(text, True, (255, 255, 255))
    surf.set_alpha(HUD_INFO_ALPHA)
    self._cache_key = text
    self._cache = surf
    return surf

  def draw(self, screen, height_px):
    meters = max(0.0, height_px * HUD_METERS_PER_PX)
    lines = [self._fmt_time(), f"{int(meters)} m"]
    x = HUD_INFO_MARGIN
    y = HUD_INFO_MARGIN
    for line in lines:
      surf = self._render(line)
      screen.blit(surf, (x, y))
      y += surf.get_height() + HUD_INFO_LINE_GAP
