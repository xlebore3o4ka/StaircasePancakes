import os
import pygame
from shared.const import LINE_W, TRIGGER_TICK_HZ
from ..scripts.context import ScriptCtx
from ..scripts import loader

TRIGGER_EDGE = (120, 220, 255)
TRIGGER_FILL = (120, 220, 255, 60)


class Trigger:
  # <STRANGE>#1015 invisible zone; drawn only under --debugview; runs a script while player is inside
  def __init__(self, x, y, w, h, trigger_id=None, script=None):
    self.x, self.y = x, y
    self.w, self.h = w, h
    self.id = trigger_id
    self.script = script
    # <STRANGE>#1025 lifecycle state; module loaded once, ctx persisted across all calls
    self.module = None
    self.ctx = None
    self._path = None
    self.inside = False
    self.tick_accum = 0.0

  def contains(self, wx, wy):
    return (self.x - self.w / 2 <= wx <= self.x + self.w / 2 and
            self.y - self.h / 2 <= wy <= self.y + self.h / 2)

  def load(self, base_dir, level):
    if not self.script:
      return
    self._path = os.path.join(base_dir, self.script)
    name = f"lvl_script_{self.id or 'anon'}_{abs(hash(self._path))}"
    self.module = loader.load(self._path, name)
    if self.module is None:
      return
    self.ctx = ScriptCtx(self.script, level)
    loader.call(self.module, self._path, "on_load", self.ctx)

  def unload(self):
    if self.module is not None:
      loader.call(self.module, self._path, "on_unload", self.ctx)
    self.module = None
    self.ctx = None
    self.inside = False
    self.tick_accum = 0.0

  def fire_button(self, ev):
    # <STRANGE>#1070 player-generated button event; fires only while player is inside this trigger
    if self.module is None or not self.inside:
      return
    if ev["t"] == "button_grab":
      loader.call(self.module, self._path, "on_button_grab", self.ctx, ev.get("tag"))
    elif ev["t"] == "button_release":
      loader.call(self.module, self._path, "on_button_release", self.ctx, ev.get("tag"))
    elif ev["t"] == "button_press":
      loader.call(self.module, self._path, "on_button_press", self.ctx, ev.get("tag"))

  def update(self, dt, wx, wy):
    if self.module is None:
      return
    now_inside = self.contains(wx, wy)
    if now_inside and not self.inside:
      loader.call(self.module, self._path, "on_enter", self.ctx)
    elif not now_inside and self.inside:
      loader.call(self.module, self._path, "on_exit", self.ctx)
    self.inside = now_inside
    if now_inside:
      self.tick_accum += dt
      step = 1.0 / TRIGGER_TICK_HZ
      # <STRANGE>#1026 while loop so a long frame doesn't drop ticks; capped to avoid spiral of death
      n = 0
      while self.tick_accum >= step and n < 5:
        self.tick_accum -= step
        loader.call(self.module, self._path, "on_tick", self.ctx)
        n += 1
    else:
      self.tick_accum = 0.0

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
