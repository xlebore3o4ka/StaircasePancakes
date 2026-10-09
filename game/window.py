import pygame

class Window:
  def __enter__(self):
    # <PROBLEM>#3 set_mode((0,0), FULLSCREEN) unstable on Wayland/some Linux; fallback to display.Info() if it breaks
    pygame.init()
    self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    # <STRANGE>#5 self.screen is created only in __enter__ — access before with raises AttributeError, intentional
    return self

  def __exit__(self, *exc):
    pygame.quit()

  def flip(self):
    pygame.display.flip()