import math
import random
from shared.smooth import smooth


class Camera:
  def __init__(self, x, y, w, h, scale):
    self.x = x
    self.y = y
    self.w = w
    self.h = h
    self.scale = scale
    self.lerp_t = 0.1
    # <STRANGE>#1195 shake state: offset is recomputed each update, applied in to_screen only
    self.shake_t = 0.0
    self.shake_dur = 0.0
    self.shake_amp = 0.0
    self.shake_freq = 0.0
    self._ox = 0.0
    self._oy = 0.0

  def follow(self, target, dt=1/60):
    k = smooth(self.lerp_t, dt)
    self.x += (target[0] - self.x) * k
    self.y += (target[1] - self.y) * k

  def shake(self, dur, amp, freq=0.0):
    # <STRANGE>#1195 newest shake wins; scripts and damage both go through here
    self.shake_t = dur
    self.shake_dur = max(0.001, dur)
    self.shake_amp = amp
    self.shake_freq = freq

  def update(self, dt):
    if self.shake_t <= 0:
      self._ox = 0.0
      self._oy = 0.0
      return
    self.shake_t = max(0.0, self.shake_t - dt)
    k = self.shake_t / self.shake_dur
    if self.shake_freq > 0:
      phase = (self.shake_dur - self.shake_t) * self.shake_freq * 2 * math.pi
      self._ox = math.sin(phase) * self.shake_amp * k
      self._oy = math.sin(phase + 1.3) * self.shake_amp * k
    else:
      self._ox = random.uniform(-1.0, 1.0) * self.shake_amp * k
      self._oy = random.uniform(-1.0, 1.0) * self.shake_amp * k

  # <STRANGE>#188 to_screen returns real screen pixels; every draw radius must be multiplied by cam.scale separately
  def to_screen(self, wx, wy):
    return ((wx - self.x + self.w / 2) * self.scale + self._ox,
            (self.h / 2 - (wy - self.y)) * self.scale + self._oy)

  def from_screen(self, sx, sy):
    return (sx / self.scale - self.w / 2 + self.x,
            self.h / 2 - sy / self.scale + self.y)
