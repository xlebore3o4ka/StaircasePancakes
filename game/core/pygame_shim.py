import pygame

_installed = False


def _is_worldctx(obj):
  return hasattr(obj, "_r") and hasattr(obj, "cam") and hasattr(obj, "polygon")


def install():
  global _installed
  if _installed:
    return
  _installed = True

  pd = pygame.draw
  orig_rect = pd.rect
  orig_circle = pd.circle
  orig_polygon = pd.polygon
  orig_line = pd.line

  def rect(surface, color, rect, width=0, *args, **kw):
    if _is_worldctx(surface):
      x, y, w, h = rect
      alpha = color[3] if len(color) == 4 else 255
      rgb = color[:3] if len(color) == 4 else color
      if width and width > 0:
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        surface.polygon(pts, rgb, alpha, width)
      else:
        surface.rect(x, y, w, h, rgb, alpha)
      return
    return orig_rect(surface, color, rect, width, *args, **kw)

  def circle(surface, color, center, radius, width=0, *args, **kw):
    if _is_worldctx(surface):
      cx, cy = center
      alpha = color[3] if len(color) == 4 else 255
      rgb = color[:3] if len(color) == 4 else color
      if width and width > 0:
        surface.ring(cx, cy, radius, width, rgb, alpha)
      else:
        surface.circle(cx, cy, radius, rgb, alpha)
      return
    return orig_circle(surface, color, center, radius, width, *args, **kw)

  def polygon(surface, color, points, width=0, *args, **kw):
    if _is_worldctx(surface):
      alpha = color[3] if len(color) == 4 else 255
      rgb = color[:3] if len(color) == 4 else color
      surface.polygon(points, rgb, alpha, width)
      return
    return orig_polygon(surface, color, points, width, *args, **kw)

  def line(surface, color, start, end, width=1, *args, **kw):
    if _is_worldctx(surface):
      alpha = color[3] if len(color) == 4 else 255
      rgb = color[:3] if len(color) == 4 else color
      surface.line(start[0], start[1], end[0], end[1], width, rgb, alpha)
      return
    return orig_line(surface, color, start, end, width, *args, **kw)

  pd.rect = rect
  pd.circle = circle
  pd.polygon = polygon
  pd.line = line
