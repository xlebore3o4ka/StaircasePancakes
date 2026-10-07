import pygame
from .core.window import Window
from .core.physics import make_space
from .entities.player import Player
from .core.camera import Camera
from .level import Level

class Game:
  def run(self):
    with Window() as w:
      space = make_space()
      sw, sh = w.screen.get_size()
      cam = Camera(sw / 2, sh / 2, sw, sh)
      player = Player(space, (sw / 2, sh / 2))
      level = Level(space, sw)
      clock = pygame.time.Clock()
      running = True
      while running:
        for e in pygame.event.get():
          if e.type == pygame.QUIT:
            running = False
          elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            running = False
          player.handle_event(e)
        level.update(player)
        player.update(cam, level.grabbables())
        space.step(1 / 60)
        cam.follow(player.body.position)
        w.screen.fill((89, 95, 102))
        # <STRANGE>#26 floor fill spans whole width using cam.to_screen of two world points; width from world doesn't matter since y is constant
        fx0, fy0 = cam.to_screen(cam.x - cam.w, 0)
        fx1, fy1 = cam.to_screen(cam.x + cam.w, 0)
        pygame.draw.rect(w.screen, (19, 20, 26), (fx0, fy0, fx1 - fx0, w.screen.get_height() - fy0))
        level.draw(w.screen, cam)
        player.draw(w.screen, cam)
        w.flip()
        clock.tick(60)
