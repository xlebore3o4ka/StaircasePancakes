import pygame
from shared.const import BG_FILL, LAYER_BG

class Background:
  layer = LAYER_BG

  def __init__(self, pos, w, h, color=BG_FILL, points=None):
    self.x, self.y = pos
    self.w = w
    self.h = h
    self.color = color
    # <STRANGE>#771 polygon mode: points are offsets from the (x, y) centre, given in world units; None = plain rect
    self.points = points

  def _world_points(self):
    return [(self.x + px, self.y + py) for px, py in self.points]

  def _bbox(self):
    xs = [p[0] for p in self.points]
    ys = [p[1] for p in self.points]
    return (self.x + min(xs), self.x + max(xs),
            self.y + min(ys), self.y + max(ys))

  def contains(self, wx, wy):
    # <STRANGE>#798 point-in-background test; rect vs polygon
    if self.points is None:
      l, r, b, t = (self.x - self.w / 2, self.x + self.w / 2,
                    self.y - self.h / 2, self.y + self.h / 2)
      return l <= wx <= r and b <= wy <= t
    # <STRANGE>#798 even-odd ray cast; enough for convex and concave simple polygons
    pts = self._world_points()
    inside = False
    n = len(pts)
    j = n - 1
    for i in range(n):
      xi, yi = pts[i]
      xj, yj = pts[j]
      if (yi > wy) != (yj > wy):
        xint = (xj - xi) * (wy - yi) / (yj - yi) + xi
        if wx < xint:
          inside = not inside
      j = i
    return inside

  def draw(self, screen, cam):
    # <SLOW>#198 cull: skip draw when fully off-screen
    sw, sh = screen.get_size()
    if self.points is None:
      x0, y0 = cam.to_screen(self.x - self.w / 2, self.y + self.h / 2)
      x1, y1 = cam.to_screen(self.x + self.w / 2, self.y - self.h / 2)
      r = pygame.Rect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))
      if r.right < 0 or r.left > sw or r.bottom < 0 or r.top > sh:
        return
      pygame.draw.rect(screen, self.color, r)
      return
    l, r, b, t = self._bbox()
    sx0, sy0 = cam.to_screen(l, t)
    sx1, sy1 = cam.to_screen(r, b)
    lo_x, hi_x = (sx0, sx1) if sx0 < sx1 else (sx1, sx0)
    lo_y, hi_y = (sy0, sy1) if sy0 < sy1 else (sy1, sy0)
    if hi_x < 0 or lo_x > sw or hi_y < 0 or lo_y > sh:
      return
    pts = [cam.to_screen(wx, wy) for wx, wy in self._world_points()]
    pygame.draw.polygon(screen, self.color, pts)
