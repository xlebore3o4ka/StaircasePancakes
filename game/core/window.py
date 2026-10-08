import pygame

DESIGN_H = 1080

class Window:
  def __enter__(self):
    # <PROBLEM>#3 set_mode FULLSCREEN unstable on Wayland/some Linux; fallback to display.Info() if it breaks
    pygame.init()
    # <STRANGE>#338 vsync=1 caps fps to monitor refresh; dt-based physics handles 60/144/165/240 equally
    self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN, vsync=1)
    # <STRANGE>#187 scale tied to screen height; ultrawide sees more horizontally — acceptable for now, letterbox later if unfair
    self.scale = self.screen.get_height() / DESIGN_H
    return self

  def __exit__(self, *exc):
    pygame.quit()

  def flip(self):
    pygame.display.flip()
