import pygame
import pymunk

PEG_R = 16
PEG_FILL = (220, 60, 60)
PEG_EDGE = (255, 255, 255)
PEG_EDGE_GRABBED = (70, 70, 70)
PEG_EDGE_W = 4

class Peg:
  def __init__(self, space, pos):
    self.grab_count = 0
    self.body = pymunk.Body(body_type=pymunk.Body.STATIC)
    self.body.position = pos
    shape = pymunk.Circle(self.body, PEG_R)
    # <STRANGE>#71 group=1 excludes peg from colliding with player parts; only grabs (constraints) interact
    shape.filter = pymunk.ShapeFilter(group=1)
    space.add(self.body, shape)
    self.pos = pymunk.Vec2d(*pos)

  def grab_points(self):
    return [(self.pos, pymunk.Vec2d(0, 0))]

  def draw(self, screen, cam):
    sc = cam.scale
    x, y = cam.to_screen(*self.pos)
    pygame.draw.circle(screen, PEG_FILL, (int(x), int(y)), int(PEG_R * sc))
    # <STRANGE>#87 gray edge lerps with grab_count; two hands on same peg -> fully gray
    t = min(self.grab_count, 2) / 2
    edge = tuple(int(a + (b - a) * t) for a, b in zip(PEG_EDGE, PEG_EDGE_GRABBED))
    pygame.draw.circle(screen, edge, (int(x), int(y)), int(PEG_R * sc), max(1, int(PEG_EDGE_W * sc)))
