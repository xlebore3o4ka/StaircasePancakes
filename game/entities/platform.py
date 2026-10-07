import pygame
import pymunk
from .player import BODY_R

PLAT_W = 5 * BODY_R
PLAT_H = 2 * BODY_R
PLAT_FILL = (60, 60, 80)
PLAT_EDGE = (255, 255, 255)
PLAT_EDGE_W = 3

class Platform:
  def __init__(self, space, pos):
    self.grab_count = 0
    self.w = PLAT_W
    self.h = PLAT_H
    self.body = pymunk.Body(body_type=pymunk.Body.STATIC)
    self.body.position = pos
    # <STRANGE>#113 default filter (group=0) so player body collides; arms are kinematic so they pass through anyway
    shape = pymunk.Poly.create_box(self.body, (self.w, self.h))
    shape.filter = pymunk.ShapeFilter(categories=0b10)
    space.add(self.body, shape)

  def grab_points(self):
    tl = pymunk.Vec2d(-self.w / 2, self.h / 2)
    tr = pymunk.Vec2d(self.w / 2, self.h / 2)
    return [(self.body.local_to_world(tl), tl), (self.body.local_to_world(tr), tr)]

  def draw(self, screen, cam):
    p = self.body.position
    x0, y0 = cam.to_screen(p.x - self.w / 2, p.y + self.h / 2)
    x1, y1 = cam.to_screen(p.x + self.w / 2, p.y - self.h / 2)
    rect = pygame.Rect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))
    pygame.draw.rect(screen, PLAT_FILL, rect)
    pygame.draw.rect(screen, PLAT_EDGE, rect, PLAT_EDGE_W)
