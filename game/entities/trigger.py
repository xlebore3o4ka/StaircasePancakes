import pygame
from shared.const import LINE_W

TRIGGER_EDGE = (120, 220, 255)
TRIGGER_FILL = (120, 220, 255, 60)


class Trigger:
  # <STRANGE>#1015 invisible in-game zone; drawn only under --debugview. No physics, no role yet.
  def __init__(self, x, y, w, h, trigger_id=None, script=None):
    self.x, self.y = x, y
    self.w, self.h = w, h
    self.id = trigger_id
    self.script = script

  def contains(self, wx, wy):
    return (self.x - self.w / 2 <= wx <= self.x + self.w / 2 and
            self.y - self.h / 2 <= wy <= self.y + self.h / 2)

  def draw_debug(self, screen, cam):
    x0, y0 = cam.to_screen(self.x - self.w / 2, self.y + self.h / 2)
    x1, y1 = cam.to_screen(self.x + self.w / 2, self.y - self.h / 2)
    r = pygame.Rect(int(min(x0, x1)), int(min(y0, y1)),
                    int(abs(x1 - x0)), int(abs(y1 - y0)))
    surf = pygame.Surface(r.size, pygame.SRCALPHA)
    surf.fill(TRIGGER_FILL)
    screen.blit(surf, r.topleft)
    pygame.draw.rect(screen, TRIGGER_EDGE, r, LINE_W)
    if self.id:
      font = pygame.font.SysFont(None, 22)
      label = font.render(self.id, True, TRIGGER_EDGE)
      screen.blit(label, (r.x + 4, r.y + 4))
