import math
import random
import pygame
import pymunk
from shared.const import ARM_R, ITEM_GRAB_DIST, CUBE_FILL, CUBE_EDGE, CUBE_EDGE_W, CUBE_FRICTION, CUBE_ELASTICITY, ITEM_TYPES, SODA_W, SODA_H, SODA_BLUE, SODA_WHITE, SODA_STAMINA

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
    shape.filter = pymunk.ShapeFilter(categories=0b1000, mask=0b10 | 0b1000)
    # <STRANGE>#263 high friction stops sliding forever; elasticity gives a small bounce on impact
    shape.friction = CUBE_FRICTION
    shape.elasticity = CUBE_ELASTICITY
    self.shape = shape
    space.add(self.body, shape)

  def destroy(self):
    # <STRANGE>#295 destroy only removes physics; caller is responsible for clearing held_by on player side
    self.space.remove(self.body, self.shape)

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
    # <STRANGE>#296 returns (consumed, spawn_type); spawn_type None means just vanish
    return (False, None)

  def draw(self, screen, cam):
    pass

  def _rotated_corners(self, cam, lx0, ly0, lx1, ly1):
    # <STRANGE>#304 shared helper: local rect corners -> world -> screen, used by any rotating item render
    p = self.body.position
    a = self.body.angle
    c, sn = math.cos(a), math.sin(a)
    out = []
    for lx, ly in ((lx0, ly0), (lx1, ly0), (lx1, ly1), (lx0, ly1)):
      wx = p.x + lx * c - ly * sn
      wy = p.y + lx * sn + ly * c
      out.append(cam.to_screen(wx, wy))
    return out


class CubeItem(Item):
  def __init__(self, space, pos):
    # <STRANGE>#292 cube size is fixed; no JSON override, so editor friend can't accidentally mismatch
    super().__init__(space, pos, 30, 30)

  def use(self):
    # <STRANGE>#297 spawn a random different type from the pool; if nothing else exists yet, just consume
    others = [t for t in ITEM_TYPES if t != "cube"]
    if not others:
      return (True, None, 0)
    return (True, random.choice(others), 0)

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



class SodaItem(Item):
  def __init__(self, space, pos):
    super().__init__(space, pos, SODA_W, SODA_H)

  def use(self):
    return (True, None, SODA_STAMINA)

  def draw(self, screen, cam):
    hw, hh = self.w / 2, self.h / 2
    # <STRANGE>#305 three bands stacked: top blue, middle white, bottom blue
    top = self._rotated_corners(cam, -hw, hh * 0.5, hw, hh)
    mid = self._rotated_corners(cam, -hw, -hh * 0.5, hw, hh * 0.5)
    bot = self._rotated_corners(cam, -hw, -hh, hw, -hh * 0.5)
    pygame.draw.polygon(screen, SODA_BLUE, top)
    pygame.draw.polygon(screen, SODA_WHITE, mid)
    pygame.draw.polygon(screen, SODA_BLUE, bot)

def make_item(space, spec):
  t = spec.get("type", "cube")
  pos = (spec["x"], spec["y"])
  if t == "soda":
    return SodaItem(space, pos)
  return CubeItem(space, pos)
