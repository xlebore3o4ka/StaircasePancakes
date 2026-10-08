import pygame
from .core.window import Window
from .core.physics import make_space
from .entities.player import Player, BODY_R
from .core.camera import Camera
from .level import Level
from .entities.floor import FloorFill

LOGICAL_W = 1920
LOGICAL_H = 1080

class Game:
  def __init__(self, cheats=False):
    self.cheats = cheats

  def run(self):
    with Window() as w:
      space = make_space()
      # <STRANGE>#158 spawn at world origin on the floor; cam starts synced so it doesn't fly in
      player = Player(space, (0, BODY_R), cheats=self.cheats)
      # <STRANGE>#189 camera viewport is always LOGICAL_W x LOGICAL_H; scale only affects rendering, not world size
      cam = Camera(0, BODY_R, LOGICAL_W, LOGICAL_H, w.scale)
      level = Level(space, "levels/test.json")
      floor_fill = FloorFill()
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
        # <NOTE>#445 single sorted pass: backgrounds -> floor -> platforms/pegs -> items -> player
        drawables = level.drawables() + [floor_fill, player]
        drawables.sort(key=lambda o: o.layer)
        for d in drawables:
          d.draw(w.screen, cam)
        player.draw_hud(w.screen, cam)
        w.flip()
