class Camera:
  def __init__(self, x, y, w, h, scale):
    self.x = x
    self.y = y
    self.w = w
    self.h = h
    self.scale = scale
    self.lerp_t = 0.1

  def follow(self, target):
    self.x += (target[0] - self.x) * self.lerp_t
    self.y += (target[1] - self.y) * self.lerp_t

  # <STRANGE>#188 to_screen returns real screen pixels; every draw radius must be multiplied by cam.scale separately
  def to_screen(self, wx, wy):
    return ((wx - self.x + self.w / 2) * self.scale,
            (self.h / 2 - (wy - self.y)) * self.scale)

  def from_screen(self, sx, sy):
    return (sx / self.scale - self.w / 2 + self.x,
            self.h / 2 - sy / self.scale + self.y)
