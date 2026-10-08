from shared.const import (
  BODY_R, CONSUME_FX_DURATION, CONSUME_FX_RISE, CONSUME_FX_OFFSET,
  CONSUME_FX_SCALE, CONSUME_FX_ALPHA,
)


class ConsumeFx:
  # <STRANGE>#325 holds a reference to the consumed item only for its draw_at; item physics is already gone
  def __init__(self, player_body, item, angle):
    self.player_body = player_body
    self.item = item
    self.angle = angle
    self.t = 0.0
    self.dead = False

  def update(self, dt):
    self.t += dt
    if self.t >= CONSUME_FX_DURATION:
      self.dead = True

  def draw(self, screen, cam):
    k = self.t / CONSUME_FX_DURATION
    # <STRANGE>#333 ease-out on rise: fast first, slows down; (1-(1-k)^2) gives that curve
    eased = 1.0 - (1.0 - k) * (1.0 - k)
    y_off = BODY_R + CONSUME_FX_OFFSET + CONSUME_FX_RISE * eased
    pos = (self.player_body.position.x, self.player_body.position.y + y_off)
    alpha = int(CONSUME_FX_ALPHA * (1.0 - k))
    if alpha <= 0:
      return
    self.item.draw_at(screen, cam, pos, self.angle, alpha, CONSUME_FX_SCALE)
