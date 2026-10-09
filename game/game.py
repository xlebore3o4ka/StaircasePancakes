import pygame
from .core.window import Window
from .core.physics import make_space
from .entities.player import Player, BODY_R
from .core.camera import Camera
from .level import Level
from .entities.floor import FloorFill
from .entities.hud_info import HudInfo

LOGICAL_W = 1920
LOGICAL_H = 1080

class Game:
  def __init__(self, cheats=False, map_path="levels/test.json", spawninfo=False):
    self.cheats = cheats
    self.map_path = map_path
    self.spawninfo = spawninfo

  def run(self):
    with Window() as w:
      space = make_space()
      # <STRANGE>#158 spawn at world origin on the floor; cam starts synced so it doesn't fly in
      player = Player(space, (0, BODY_R), cheats=self.cheats)
      spawn_y = BODY_R
      # <STRANGE>#189 camera viewport is always LOGICAL_W x LOGICAL_H; scale only affects rendering, not world size
      cam = Camera(0, BODY_R, LOGICAL_W, LOGICAL_H, w.scale)
      level = Level(space, self.map_path)
      floor_fill = FloorFill()
      hud_info = HudInfo()
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
        player.update(cam, level.grabbables(), level.items, dt)
        # <STRANGE>#300 drain spawn queue after player update so items appear next frame with no mid-frame physics surprises
        if player.spawn_queue:
          for pos, spec, vel in player.spawn_queue:
            level.spawn_item(pos, spec, vel)
          player.spawn_queue.clear()
        for _ in range(substeps):
          player.record_pre_step()
          space.step(dt / substeps)
          # <STRANGE>#525 rebar sticking is checked after physics so arbiter list is fresh
          level.post_step(player)
          # <STRANGE>#657 player bias clamp runs after every substep
          player.post_step(dt)
        cam.follow(player.body.position, dt)
        w.screen.fill((89, 95, 102))
        # <NOTE>#445 single sorted pass: backgrounds -> floor -> platforms/pegs -> items -> player
        drawables = level.drawables() + [floor_fill, player]
        drawables.sort(key=lambda o: o.layer)
        for d in drawables:
          d.draw(w.screen, cam)
        if self.spawninfo:
          level.draw_spawners(w.screen, cam, player.body.position)
        player.draw_hud(w.screen, cam)
        hud_info.update(dt)
        # <STRANGE>#620 height is distance from spawn, not absolute y
        hud_info.draw(w.screen, player.body.position.y - spawn_y)
        w.flip()
