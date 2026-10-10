import pygame
import pymunk
from shared.const import (
  PEG_R, PEG_FILL, PEG_EDGE, PEG_EDGE_GRABBED, PEG_EDGE_W, LAYER_PEG,
  PEG_FILL_FROM_ITEM,
)

class Peg:
  layer = LAYER_PEG

  def __init__(self, space, pos, from_item=False):
    self.grab_count = 0
    # <STRANGE>#807 true when the peg was created by planting a portable peg; edge stays orange
    self.from_item = from_item
    self.body = pymunk.Body(body_type=pymunk.Body.STATIC)
    self.body.position = pos
    shape = pymunk.Circle(self.body, PEG_R)
    # <STRANGE>#71 group=1 excludes peg from colliding with player parts; only grabs (constraints) interact
    # <STRANGE>#249 peg category 0b100000 excluded from item mask; group=1 still blocks player collision
    shape.filter = pymunk.ShapeFilter(group=1, categories=0b100000)
    space.add(self.body, shape)
    self.pos = pymunk.Vec2d(*pos)

  def grab_points(self):
    return [(self.pos, pymunk.Vec2d(0, 0))]

  def draw(self, screen, cam):
    sc = cam.scale
    x, y = cam.to_screen(*self.pos)
    ix, iy = int(x), int(y)
    fill = PEG_FILL_FROM_ITEM if self.from_item else PEG_FILL
    pygame.draw.circle(screen, fill, (ix, iy), int(PEG_R * sc))
    # <STRANGE>#87 gray edge lerps with grab_count; two hands on same peg -> fully gray
    t = min(self.grab_count, 2) / 2
    edge = tuple(int(a + (b - a) * t) for a, b in zip(PEG_EDGE, PEG_EDGE_GRABBED))
    pygame.draw.circle(screen, edge, (ix, iy), int(PEG_R * sc), max(1, int(PEG_EDGE_W * sc)))
