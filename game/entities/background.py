import pygame
from shared.const import BG_FILL, LAYER_BG

class Background:
  layer = LAYER_BG

  def __init__(self, pos, w, h, color=BG_FILL):
    self.x, self.y = pos
    self.w, self.h = w, h
    self.color = color

  def draw(self, screen, cam):
    x0, y0 = cam.to_screen(self.x - self.w / 2, self.y + self.h / 2)
    x1, y1 = cam.to_screen(self.x + self.w / 2, self.y - self.h / 2)
    r = pygame.Rect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))
    # <SLOW>#198 cull: skip draw when fully off-screen; free win on large levels
    sw, sh = screen.get_size()
    if r.right < 0 or r.left > sw or r.bottom < 0 or r.top > sh:
      return
    pygame.draw.rect(screen, self.color, r)
