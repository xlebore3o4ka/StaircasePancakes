import pygame
import pymunk
from shared.const import (
  PEG_R, BUTTON_FILL, BUTTON_EDGE, LAYER_PEG, CIRCLE_LINE_W,
  BUTTON_GRAB_DIM, BUTTON_PRESS_HELD_DIM, BUTTON_PRESS_RELEASE_DIM,
  BUTTON_PRESS_FADE,
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
    # <STRANGE>#1103 visual state; grabbed is set by Player while a hand holds, press_held by Q/E
    self.grabbed = False
    self.press_held = False
    self.press_dim = 0.0
    self._was_press_held = False
    self.body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
    self.body.position = pos
    shape = pymunk.Circle(self.body, self.r)
    shape.filter = pymunk.ShapeFilter(group=1, categories=0b1000000)
    space.add(self.body, shape)

  def grab_points(self):
    return [(self.body.position, pymunk.Vec2d(0, 0))]

  def update(self, dt):
    # <STRANGE>#1119 while Q/E held: dim = HELD_DIM; on release: jump to RELEASE_DIM then fade linearly to 0
    if self.press_held:
      self.press_dim = BUTTON_PRESS_HELD_DIM
    elif self._was_press_held:
      self.press_dim = BUTTON_PRESS_RELEASE_DIM
    elif self.press_dim > 0:
      self.press_dim = max(0.0, self.press_dim - dt * BUTTON_PRESS_RELEASE_DIM / BUTTON_PRESS_FADE)
    self._was_press_held = self.press_held

  def _dim(self):
    d = BUTTON_GRAB_DIM if self.grabbed else 0.0
    d += self.press_dim
    return min(1.0, d)

  def tint(self, col):
    # <STRANGE>#1113 darken channel-wise; edge (white) turns grey, fill turns darker blue
    d = self._dim()
    if d <= 0:
      return col
    return tuple(max(0, int(c * (1.0 - d))) for c in col[:3])

  def draw(self, screen, cam):
    sc = cam.scale
    x, y = cam.to_screen(self.body.position.x, self.body.position.y)
    ix, iy = int(x), int(y)
    r = max(1, int(self.r * sc))
    fill = self.tint(BUTTON_FILL)
    edge = self.tint(BUTTON_EDGE)
    inner_base = tuple(min(255, int(c / 0.8)) for c in BUTTON_FILL)
    inner = self.tint(inner_base)
    pygame.draw.circle(screen, fill, (ix, iy), r)
    # <STRANGE>#1082 inner ring: outline only, radius 1/2.2 of the outer circle
    inner_r = max(1, int(r / 2.2))
    pygame.draw.circle(screen, inner, (ix, iy), inner_r, CIRCLE_LINE_W)
    pygame.draw.circle(screen, edge, (ix, iy), r, CIRCLE_LINE_W)
