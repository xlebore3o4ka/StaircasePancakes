import pymunk


SLOP = 1.0
# <STRANGE>#626 deep penetration is a stuck body; solver bias is the only way out, don't strip it
ESCAPE_PEN = 8.0


def kill_bias(body):
  """Strip solver bias from body.velocity.

  Bias is created only when a contact penetrates deeper than the space's
  collision_slop. Shallow (resting/brushing) contacts leave velocity alone."""
  v = body.velocity
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
    # <STRANGE>#622 deepest penetration in this contact set decides whether bias was applied
    max_pen = 0.0
    for cp in arb.contact_point_set.points:
      if cp.distance < 0 and -cp.distance > max_pen:
        max_pen = -cp.distance
    if max_pen <= SLOP:
      return True
    if max_pen > ESCAPE_PEN:
      return True
    # normal points from surface outward; only kill velocity pointing further out (bias)
    proj = data[0].x * n.x + data[0].y * n.y
    if proj <= 0:
      return True
    data[0] = pymunk.Vec2d(data[0].x - n.x * proj, data[0].y - n.y * proj)
    return True
  box = [v]
  body.each_arbiter(cb, box)
  body.velocity = box[0]
