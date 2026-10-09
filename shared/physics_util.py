import pymunk


def stop_incoming(body):
  """Zero the velocity component that points INTO a floor/platform surface.

  Physics bias (solver push-out) shows up as extra velocity pointing OUT of the
  surface after a deep hit; because we only clamp the incoming direction, a bias
  push never lands and the bounce never appears. Motion *away* from the surface
  and tangential sliding are both preserved, so no sticking."""
  def cb(arb, data):
    a, b = arb.shapes
    if a.body is body:
      other = b
      n = -arb.contact_point_set.normal
    elif b.body is body:
      other = a
      n = arb.contact_point_set.normal
    else:
      return True
    if not (other.filter.categories & 0b10):
      return True
    v = data[0]
    proj = v.x * n.x + v.y * n.y
    if proj < 0:
      data[0] = pymunk.Vec2d(v.x - n.x * proj, v.y - n.y * proj)
    return True
  box = [body.velocity]
  body.each_arbiter(cb, box)
  body.velocity = box[0]
