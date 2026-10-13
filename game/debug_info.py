import pygame


class DebugInfo:
  # <STRANGE>#1171 top-right readout of player pos/vel, active only with --debuginfo
  def __init__(self):
    self.font = pygame.font.SysFont(None, 24)
    self._cache_key = None
    self._cache = None

  def _render(self, text):
    if self._cache_key == text:
      return self._cache
    surf = self.font.render(text, True, (255, 255, 255))
    surf.set_alpha(180)
    self._cache_key = text
    self._cache = surf
    return surf

  def draw(self, screen, body):
    p = body.position
    v = body.velocity
    lines = [
      f"pos {p.x:.1f} {p.y:.1f}",
      f"vel {v.x:.0f} {v.y:.0f}",
    ]
    x = screen.get_width() - 12
    y = 12
    for line in lines:
      surf = self._render(line)
      screen.blit(surf, (x - surf.get_width(), y))
      y += surf.get_height() + 2
