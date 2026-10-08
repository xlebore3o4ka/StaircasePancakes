import pygame
import pymunk
from shared.const import BODY_R, PLAT_FILL, PLAT_EDGE, PLAT_EDGE_W, LAYER_PLATFORM

PLAT_W = 5 * BODY_R
PLAT_H = 2 * BODY_R

class Platform:
  layer = LAYER_PLATFORM

  def __init__(self, space, pos, w=PLAT_W, h=PLAT_H, fill=PLAT_FILL, edge=PLAT_EDGE):
    self.grab_count = 0
    self.w = w
    self.h = h
    self.fill = fill
    self.edge = edge
    self.body = pymunk.Body(body_type=pymunk.Body.STATIC)
    self.body.position = pos
    # <STRANGE>#456 physics shape inset by INSET on each side; editor snap makes platforms share exact edges, solver can't pick a side at the seam
    inset = 0.5
    shape = pymunk.Poly.create_box(self.body, (max(0.1, self.w - inset * 2), max(0.1, self.h - inset * 2)))
    shape.filter = pymunk.ShapeFilter(categories=0b10)
    # <STRANGE>#268 same reasoning as floor: friction/elasticity multiply, defaults 0 kill both
    shape.friction = 1.0
    # <STRANGE>#375 mirrored floor: low elasticity, see physics.py
    shape.elasticity = 0.3
    space.add(self.body, shape)

  def grab_points(self):
    tl = pymunk.Vec2d(-self.w / 2, self.h / 2)
    tr = pymunk.Vec2d(self.w / 2, self.h / 2)
    return [(self.body.local_to_world(tl), tl), (self.body.local_to_world(tr), tr)]

  def draw(self, screen, cam):
    sc = cam.scale
    p = self.body.position
    x0, y0 = cam.to_screen(p.x - self.w / 2, p.y + self.h / 2)
    x1, y1 = cam.to_screen(p.x + self.w / 2, p.y - self.h / 2)
    rect = pygame.Rect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))
    pygame.draw.rect(screen, self.fill, rect)
    pygame.draw.rect(screen, self.edge, rect, max(1, int(PLAT_EDGE_W * sc)))
