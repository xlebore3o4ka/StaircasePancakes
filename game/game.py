import pygame
from .core.window import Window
from .core.physics import make_space
from .entities.player import Player, BODY_R
from .core.camera import Camera
from .level import Level

LOGICAL_W = 1920
LOGICAL_H = 1080

class Game:
  def run(self):
    with Window() as w:
      space = make_space()
      # <STRANGE>#158 spawn at world origin on the floor; cam starts synced so it doesn't fly in
      player = Player(space, (0, BODY_R))
      # <STRANGE>#189 camera viewport is always LOGICAL_W x LOGICAL_H; scale only affects rendering, not world size
      cam = Camera(0, BODY_R, LOGICAL_W, LOGICAL_H, w.scale)
      level = Level(space, "levels/test.json")
      clock = pygame.time.Clock()
      running = True
      while running:
        # <STRANGE>#341 dt clamped to 1/30 so a lag spike doesn't explode pymunk with one huge step
        dt = min(clock.tick() / 1000.0, 1 / 30)
        if dt <= 0:
          dt = 1 / 60
        # <STRANGE>#377 sub-step long frames: 1/30 broken into two 1/60 steps reduces penetration and phantom bounces
        substeps = 2 if dt > 1/45 else 1
        for e in pygame.event.get():
          if e.type == pygame.QUIT:
            running = False
          elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            running = False
          player.handle_event(e)
        level.update(player, dt)
        player.update(cam, level.grabbables(), level.items, dt)
        # <STRANGE>#300 drain spawn queue after player update so items appear next frame with no mid-frame physics surprises
        if player.spawn_queue:
          for pos, type_name, vel in player.spawn_queue:
            level.spawn_item(pos, type_name, vel)
          player.spawn_queue.clear()
        for _ in range(substeps):
          space.step(dt / substeps)
        cam.follow(player.body.position, dt)
        w.screen.fill((89, 95, 102))
        level.draw_backgrounds(w.screen, cam)
        # <STRANGE>#26 floor fill spans whole width using cam.to_screen of two world points; width from world doesn't matter since y is constant
        fx0, fy0 = cam.to_screen(cam.x - cam.w, 0)
        fx1, fy1 = cam.to_screen(cam.x + cam.w, 0)
        pygame.draw.rect(w.screen, (19, 20, 26), (fx0, fy0, fx1 - fx0, w.screen.get_height() - fy0))
        level.draw(w.screen, cam)
        level.draw_items(w.screen, cam)
        player.draw(w.screen, cam)
        player.draw_hud(w.screen, cam)
        w.flip()
