import pygame
import pymunk
from shared.const import (
  PEG_R, BUTTON_FILL, BUTTON_EDGE, LAYER_PEG, CIRCLE_LINE_W,
)


class Button:
  # <STRANGE>#1069 hand-only grab target; no joint, body stays under gravity. Region events on press/release
  layer = LAYER_PEG
  is_button = True

  def __init__(self, space, pos, button_id=None):
    self.grab_count = 0
    self.id = button_id
    # <STRANGE>#1082 fixed radius, same as a peg
    self.r = PEG_R
    self.body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
    self.body.position = pos
    shape = pymunk.Circle(self.body, self.r)
    shape.filter = pymunk.ShapeFilter(group=1, categories=0b1000000)
    space.add(self.body, shape)

  def grab_points(self):
    return [(self.body.position, pymunk.Vec2d(0, 0))]

  def draw(self, screen, cam):
    sc = cam.scale
    x, y = cam.to_screen(self.body.position.x, self.body.position.y)
    ix, iy = int(x), int(y)
    r = int(self.r * sc)
    pygame.draw.circle(screen, BUTTON_FILL, (ix, iy), r)
    # <STRANGE>#1082 inner dot, outlined only (no fill), radius 1/2.2 of the outer circle
    inner_r = max(1, int(r / 2.2))
    pygame.draw.circle(screen, BUTTON_EDGE, (ix, iy), inner_r, CIRCLE_LINE_W)
    pygame.draw.circle(screen, BUTTON_EDGE, (ix, iy), r, CIRCLE_LINE_W)
