import colorsys
import math
import pygame


ALPHA = 200
EDGE_MARGIN = 60
TRI_SIZE = 16
FONT_SIZE = 20


def _center(obj):
  # <STRANGE>#1017 objects expose center differently: body-based vs raw x/y
  if hasattr(obj, "body"):
    p = obj.body.position
    return p.x, p.y
  return obj.x, obj.y


def _bbox(obj):
  # <STRANGE>#1017 world-space (l, r, b, t); polygon objects derive bbox from their points
  points = getattr(obj, "points", None)
  cx, cy = _center(obj)
  if points:
    xs = [cx + px for px, _ in points]
    ys = [cy + py for _, py in points]
    return min(xs), max(xs), min(ys), max(ys)
  r = getattr(obj, "r", None)
  if r is not None:
    return cx - r, cx + r, cy - r, cy + r
  w = getattr(obj, "w", 0)
  h = getattr(obj, "h", 0)
  return cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2


class DebugArrows:
  # <STRANGE>#1017 draws one arrow + id label per identified object; only visible while --debugview is on
  def __init__(self):
    self._colors = {}
    self._font = None

  def _color(self, oid):
    if oid not in self._colors:
      h = (hash(str(oid)) & 0xFFFFFFFF) % 360
      r, g, b = colorsys.hsv_to_rgb(h / 360.0, 0.9, 1.0)
      self._colors[oid] = (int(r * 255), int(g * 255), int(b * 255))
    return self._colors[oid]

  def draw(self, screen, cam, objects):
    sw, sh = screen.get_size()
    if self._font is None:
      self._font = pygame.font.SysFont(None, FONT_SIZE)
    surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
    any_drawn = False
    m = EDGE_MARGIN
    for obj in objects:
      oid = getattr(obj, "id", None)
      if not oid:
        continue
      l, r, b, t = _bbox(obj)
      x0, y0 = cam.to_screen(l, t)
      x1, y1 = cam.to_screen(r, b)
      sx0 = min(x0, x1); sx1 = max(x0, x1)
      sy0 = min(y0, y1); sy1 = max(y0, y1)
      # <STRANGE>#1017 cull: skip when the object bbox doesn't touch the screen at all
      if sx1 < 0 or sx0 > sw or sy1 < 0 or sy0 > sh:
        continue
      cx_screen = (sx0 + sx1) / 2
      cy_screen = (sy0 + sy1) / 2
      # <STRANGE>#1017 clamp arrow into screen margin so huge objects still show a marker
      ax = max(m, min(sw - m, cx_screen))
      ay = max(m, min(sh - m, cy_screen))
      dx = cx_screen - ax
      dy = cy_screen - ay
      d = math.hypot(dx, dy)
      color = self._color(oid)
      rgba = (*color, ALPHA)
      ang = 0.0 if d < 1 else math.atan2(dy, dx)
      tip = (ax + TRI_SIZE * math.cos(ang), ay + TRI_SIZE * math.sin(ang))
      p1 = (ax + TRI_SIZE * math.cos(ang + 2.6), ay + TRI_SIZE * math.sin(ang + 2.6))
      p2 = (ax + TRI_SIZE * math.cos(ang - 2.6), ay + TRI_SIZE * math.sin(ang - 2.6))
      pygame.draw.polygon(surf, rgba, [tip, p1, p2])
      label = self._font.render(str(oid), True, color)
      label.set_alpha(ALPHA)
      lx = ax + 18
      ly = ay - label.get_height() // 2
      # <STRANGE>#1017 keep label on screen; flip to the left / clamp vertically if needed
      if lx + label.get_width() > sw - 4:
        lx = ax - 18 - label.get_width()
      if ly < 4:
        ly = 4
      if ly + label.get_height() > sh - 4:
        ly = sh - 4 - label.get_height()
      surf.blit(label, (lx, ly))
      any_drawn = True
    if any_drawn:
      screen.blit(surf, (0, 0))
