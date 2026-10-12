import pygame
import pymunk
from shared.const import (
  PEG_R, BUTTON_FILL, BUTTON_EDGE, LAYER_PEG, CIRCLE_LINE_W,
  BUTTON_PRESSED_FILL, BUTTON_PRESSED_EDGE, BUTTON_POP_DUR, BUTTON_POP_SCALE,
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
    # <STRANGE>#1103 visual state: greyed while Q/E held, brief pop after release
    self.hold_visual = False
    self.pop_t = 0.0
    self.body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
    self.body.position = pos
    shape = pymunk.Circle(self.body, self.r)
    shape.filter = pymunk.ShapeFilter(group=1, categories=0b1000000)
    space.add(self.body, shape)

  def grab_points(self):
    return [(self.body.position, pymunk.Vec2d(0, 0))]

  def update(self, dt):
    if self.pop_t > 0:
      self.pop_t = max(0.0, self.pop_t - dt)

  def draw_scale(self):
    # <STRANGE>#1108 triangle: 1 -> peak -> 1 across BUTTON_POP_DUR, linear both halves
    if self.pop_t <= 0:
      return 1.0
    k = 1.0 - self.pop_t / BUTTON_POP_DUR
    if k < 0.5:
      t = k * 2.0
    else:
      t = (1.0 - k) * 2.0
    return 1.0 + (BUTTON_POP_SCALE - 1.0) * t

  def draw(self, screen, cam):
    sc = cam.scale
    x, y = cam.to_screen(self.body.position.x, self.body.position.y)
    ix, iy = int(x), int(y)
    r = max(1, int(self.r * sc))
    fill = BUTTON_PRESSED_FILL if self.hold_visual else BUTTON_FILL
    edge = BUTTON_PRESSED_EDGE if self.hold_visual else BUTTON_EDGE
    pygame.draw.circle(screen, fill, (ix, iy), r)
    # <STRANGE>#1082 inner ring: outline only, radius 1/2.2 of the outer circle
    # <STRANGE>#1085 ring colour is lighter than the base (inverse of peg's 0.8 darkening)
    inner_edge = tuple(min(255, int(c / 0.8)) for c in fill)
    inner_r = max(1, int(r / 2.2))
    pygame.draw.circle(screen, inner_edge, (ix, iy), inner_r, CIRCLE_LINE_W)
    pygame.draw.circle(screen, edge, (ix, iy), r, CIRCLE_LINE_W)
