import pymunk
from shared.const import GRAVITY

def make_space():
  space = pymunk.Space()
  space.gravity = (0, -GRAVITY)
  # <STRANGE>#8 static floor segment at y=0 stops player; real death check comes later
  floor = pymunk.Segment(space.static_body, (-10000, 0), (10000, 0), 1)
  # <STRANGE>#125 floor tagged 0b10; body uses categories 0b01 for collision, _is_grounded query hits 0b10
  floor.filter = pymunk.ShapeFilter(categories=0b10)
  space.add(floor)
  return space