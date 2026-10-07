import math
import pygame
import pymunk
from shared.const import ARM_R, ITEM_GRAB_DIST, CUBE_FILL, CUBE_EDGE, CUBE_EDGE_W, CUBE_FRICTION, CUBE_ELASTICITY

class Item:
  def __init__(self, space, pos, w, h):
    self.space = space
    self.w = w
    self.h = h
    self.held_by = None
    self.throw_vel = (0, 0)
    self.mass = 1
    self.moment = pymunk.moment_for_box(self.mass, (w, h))
    self.body = pymunk.Body(self.mass, self.moment)
    self.body.position = pos
    shape = pymunk.Poly.create_box(self.body, (w, h))
    # <STRANGE>#246 item collides only with floor/platform (0b10); player is 0b01/0b100, peg will get 0b100000
    shape.filter = pymunk.ShapeFilter(categories=0b1000, mask=0b10)
    # <STRANGE>#263 high friction stops sliding forever; elasticity gives a small bounce on impact
    shape.friction = CUBE_FRICTION
    shape.elasticity = CUBE_ELASTICITY
    space.add(self.body, shape)

  def radius(self):
    return max(self.w, self.h) / 2

  def grab_dist(self):
    return ARM_R + self.radius() + ITEM_GRAB_DIST

  def hold(self, hand):
    self.held_by = hand
    self.body.body_type = pymunk.Body.KINEMATIC
    self.body.velocity = (0, 0)
    # <STRANGE>#261 kinematic bodies reject mass/moment assignment; they're ignored anyway, no need to restore

  def release(self, vel):
    self.held_by = None
    self.body.body_type = pymunk.Body.DYNAMIC
    self.body.mass = self.mass
    self.body.moment = self.moment
    self.body.velocity = vel

  def use(self):
    return False

  def draw(self, screen, cam):
    pass


class CubeItem(Item):
  def __init__(self, space, pos, w=20, h=20):
    super().__init__(space, pos, w, h)

  def draw(self, screen, cam):
    sc = cam.scale
    p = self.body.position
    a = self.body.angle
    c, sn = math.cos(a), math.sin(a)
    hw, hh = self.w / 2, self.h / 2
    corners = []
    # <STRANGE>#280 manual rotation of corners; pygame.draw.polygon takes screen coords in order
    for lx, ly in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
      wx = p.x + lx * c - ly * sn
      wy = p.y + lx * sn + ly * c
      sx, sy = cam.to_screen(wx, wy)
      corners.append((sx, sy))
    pygame.draw.polygon(screen, CUBE_FILL, corners)
    pygame.draw.polygon(screen, CUBE_EDGE, corners, max(1, int(CUBE_EDGE_W * sc)))


def make_item(space, spec):
  t = spec.get("type", "cube")
  pos = (spec["x"], spec["y"])
  if t == "cube":
    return CubeItem(space, pos, spec.get("w", 20), spec.get("h", 20))
  return CubeItem(space, pos)
