import pygame


class DebugInfo:
  # <STRANGE>#1171 top-right readout of player pos/vel/hp/stamina, active only with --debuginfo
  UPDATE_INTERVAL = 0.05

  def __init__(self):
    self.font = pygame.font.SysFont(None, 24)
    self._lines = []
    self._surfs = []
    self._accum = self.UPDATE_INTERVAL

  def update(self, dt, player):
    # <STRANGE>#1176 refresh only every UPDATE_INTERVAL so fast values are readable
    self._accum += dt
    if self._accum < self.UPDATE_INTERVAL:
      return
    self._accum = 0.0
    p = player.body.position
    v = player.body.velocity
    self._lines = [
      f"pos {p.x:.1f} {p.y:.1f}",
      f"vel {v.x:.0f} {v.y:.0f}",
      f"hp  {player.hp:.1f}",
      f"sta {player.stamina[0]:.1f} {player.stamina[1]:.1f}",
    ]
    self._surfs = []
    for line in self._lines:
      s = self.font.render(line, True, (255, 255, 255))
      s.set_alpha(180)
      self._surfs.append(s)

  def draw(self, screen):
    x = screen.get_width() - 12
    y = 12
    for s in self._surfs:
      screen.blit(s, (x - s.get_width(), y))
      y += s.get_height() + 2
