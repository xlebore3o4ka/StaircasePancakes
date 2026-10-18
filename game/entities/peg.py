import pygame
import pymunk
from shared.const import (
  PEG_R, PEG_FILL, PEG_EDGE, PEG_EDGE_GRABBED, CIRCLE_LINE_W, LAYER_PEG,
  PEG_FILL_FROM_ITEM,
)

class Peg:
  layer = LAYER_PEG

  def __init__(self, space, pos, from_item=False):
    self.grab_count = 0
    self.id = None
    # <STRANGE>#807 true when the peg was created by planting a portable peg; edge stays orange
    self.from_item = from_item
    # <STRANGE>#1062 kinematic from start (see platform)
    self.body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
    self.body.position = pos
    shape = pymunk.Circle(self.body, PEG_R)
    # <STRANGE>#71 group=1 excludes peg from colliding with player parts; only grabs (constraints) interact
    # <STRANGE>#249 peg category 0b100000 excluded from item mask; group=1 still blocks player collision
    shape.filter = pymunk.ShapeFilter(group=1, categories=0b100000)
    space.add(self.body, shape)

  def grab_points(self):
    return [(self.body.position, pymunk.Vec2d(0, 0))]

  def draw(self, screen, cam):
    sc = cam.scale
    x, y = cam.to_screen(self.body.position.x, self.body.position.y)
    ix, iy = int(x), int(y)
    fill = PEG_FILL_FROM_ITEM if self.from_item else PEG_FILL
    pygame.draw.circle(screen, fill, (ix, iy), int(PEG_R * sc))
    # <STRANGE>#1079 inner dot: 40% darker, no outline, 1/2.2 of the peg radius
    inner = tuple(int(c * 0.8) for c in fill)
    pygame.draw.circle(screen, inner, (ix, iy), int(PEG_R * sc / 2.2))
    # <STRANGE>#87 gray edge lerps with grab_count; two hands on same peg -> fully gray
    t = min(self.grab_count, 2) / 2
    edge = tuple(int(a + (b - a) * t) for a, b in zip(PEG_EDGE, PEG_EDGE_GRABBED))
    pygame.draw.circle(screen, edge, (ix, iy), int(PEG_R * sc), CIRCLE_LINE_W)
