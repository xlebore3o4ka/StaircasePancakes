import math
import pygame
from shared.const import SODA_CX_DURATION, SODA_CX_SPINS, SODA_CX_ALPHA, SODA_CX_SCALE


class SodaConsumeFx:
  # <STRANGE>#409 visual-only fx for soda; defers stamina gain until the animation completes
  def __init__(self, player, item, angle, stamina_gain):
    self.player = player
    self.item = item
    self.start_angle = angle
    self.stamina_gain = stamina_gain
    # <STRANGE>#410 offset saved at spawn; fx follows player by adding current body pos to the shrinking offset
    self.start_offset = (
      item.body.position.x - player.body.position.x,
      item.body.position.y - player.body.position.y,
    )
    self.t = 0.0
    self.dead = False
    self.applied = False

  def update(self, dt):
    if self.dead:
      return
    self.t += dt
    if self.t >= SODA_CX_DURATION:
      self.t = SODA_CX_DURATION
      self.dead = True
      if not self.applied:
        self.applied = True
        if self.stamina_gain:
          # <STRANGE>#419 STAMINA_MAX lives in player module; import inside to avoid circular import at module level
          from .player import STAMINA_MAX
          for j in range(2):
            self.player.stamina[j] = min(STAMINA_MAX, self.player.stamina[j] + self.stamina_gain)

  def draw(self, screen, cam):
    k = self.t / SODA_CX_DURATION
    eased = 1.0 - (1.0 - k) * (1.0 - k)
    ox = self.start_offset[0] * (1.0 - eased)
    oy = self.start_offset[1] * (1.0 - eased)
    pos = (self.player.body.position.x + ox, self.player.body.position.y + oy)
    # <STRANGE>#411 spin is linear, not eased, so one full 360 reads clearly over the flight
    angle = self.start_angle + math.tau * SODA_CX_SPINS * k
    # <STRANGE>#421 scale shrinks from 1 to SODA_CX_SCALE over the flight so the soda visually disappears into the body
    scale = 1.0 + (SODA_CX_SCALE - 1.0) * eased
    alpha = int(SODA_CX_ALPHA * (1.0 - k))
    if alpha <= 0:
      return
    self.item.draw_at(screen, cam, pos, angle, alpha, scale)
