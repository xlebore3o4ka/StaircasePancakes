import pymunk
from shared.const import GRAVITY

def make_space():
  space = pymunk.Space()
  space.gravity = (0, -GRAVITY)
  # <STRANGE>#380 tolerance for penetration; higher slop trades a hair of visual contact for no bias-velocity spikes
  space.collision_slop = 1.0
  # <STRANGE>#381 more iterations so rigid rope joints don't shove the body through the floor in one pass
  space.iterations = 20
  # <STRANGE>#8 static floor segment at y=0 stops player; real death check comes later
  # <STRANGE>#277 thick floor (r=8) shifted down so top surface stays at y=0; stops fast items tunneling through
  floor = pymunk.Segment(space.static_body, (-10000, -8), (10000, -8), 8)
  # <STRANGE>#125 floor tagged 0b10; body uses categories 0b01 for collision, _is_grounded query hits 0b10
  floor.filter = pymunk.ShapeFilter(categories=0b10)
  # <STRANGE>#267 friction/elasticity combine by multiplication with the other shape; floor defaults to 0 so items never grip or bounce
  floor.friction = 1.0
  # <STRANGE>#374 low floor elasticity so falling items don't pogo; combined with item e=0.08 -> ~0.024 effective
  floor.elasticity = 0.3
  space.add(floor)
  return space