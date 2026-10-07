class Camera:
  def __init__(self, x, y, w, h):
    self.x = x
    self.y = y
    self.w = w
    self.h = h
    self.lerp_t = 0.1

  def follow(self, target):
    self.x += (target[0] - self.x) * self.lerp_t
    self.y += (target[1] - self.y) * self.lerp_t

  def to_screen(self, wx, wy):
    return wx - self.x + self.w / 2, self.h / 2 - (wy - self.y)

  def from_screen(self, sx, sy):
    return sx - self.w / 2 + self.x, self.h / 2 - sy + self.y
