import pygame
import pymunk
from shared.const import BODY_R, PLAT_FILL, PLAT_EDGE, PLAT_EDGE_W, LAYER_PLATFORM

PLAT_W = 5 * BODY_R
PLAT_H = 2 * BODY_R

class Platform:
  layer = LAYER_PLATFORM

  def __init__(self, space, pos, w=PLAT_W, h=PLAT_H, fill=PLAT_FILL, edge=PLAT_EDGE, points=None):
    self.grab_count = 0
    self.w = w
    self.h = h
    self.fill = fill
    self.edge = edge
    # <STRANGE>#841 polygon mode: centre-relative points; if set, w/h are ignored for both physics and draw
    self.points = points
    self.body = pymunk.Body(body_type=pymunk.Body.STATIC)
    self.body.position = pos
    if points is None:
      # <STRANGE>#456 physics shape inset by INSET on each side; editor snap makes platforms share exact edges, solver can't pick a side at the seam
      inset = 0.5
      shape = pymunk.Poly.create_box(self.body, (max(0.1, self.w - inset * 2), max(0.1, self.h - inset * 2)))
    else:
      # <STRANGE>#841 small radius on the poly so corners aren't razor-sharp for the player
      verts = [pymunk.Vec2d(px, py) for px, py in points]
      shape = pymunk.Poly(self.body, verts, radius=0.5)
    shape.filter = pymunk.ShapeFilter(categories=0b10)
    shape.friction = 1.0
    shape.elasticity = 0.0
    space.add(self.body, shape)

  def grab_points(self):
    if self.points is None:
      tl = pymunk.Vec2d(-self.w / 2, self.h / 2)
      tr = pymunk.Vec2d(self.w / 2, self.h / 2)
      return [(self.body.local_to_world(tl), tl), (self.body.local_to_world(tr), tr)]
    out = []
    for px, py in self.points:
      local = pymunk.Vec2d(px, py)
      out.append((self.body.local_to_world(local), local))
    return out

  def draw(self, screen, cam):
    sc = cam.scale
    p = self.body.position
    if self.points is None:
      x0, y0 = cam.to_screen(p.x - self.w / 2, p.y + self.h / 2)
      x1, y1 = cam.to_screen(p.x + self.w / 2, p.y - self.h / 2)
      rect = pygame.Rect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))
      pygame.draw.rect(screen, self.fill, rect)
      pygame.draw.rect(screen, self.edge, rect, max(1, int(PLAT_EDGE_W * sc)))
      return
    pts = [cam.to_screen(p.x + px, p.y + py) for px, py in self.points]
    pygame.draw.polygon(screen, self.fill, pts)
    pygame.draw.polygon(screen, self.edge, pts, max(1, int(PLAT_EDGE_W * sc)))
