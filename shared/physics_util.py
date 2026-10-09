import pymunk


SLOP = 1.0
# <STRANGE>#639 deeper penetration means a stuck body; the solver needs its bias to push it out
ESCAPE_PEN = 12.0


def snapshot_velocity(body):
  """Save body.velocity before space.step for later bias comparison."""
  return pymunk.Vec2d(body.velocity.x, body.velocity.y)


def undo_bias(body, pre_v):
  """Strip solver bias velocity.

  Bias is only ever generated on a contact that is NEW this step and that is
  penetrating deeper than collision_slop. Resting contacts, sliding contacts
  and shallow touches are all left alone, so no sticking and no lost motion."""
  def cb(arb, data):
    if not arb.is_first_contact:
      return True
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
    max_pen = 0.0
    for cp in arb.contact_point_set.points:
      d = -cp.distance
      if d > max_pen:
        max_pen = d
    # too shallow -> not bias; too deep -> leave to solver or the body gets stuck
    if max_pen <= SLOP or max_pen > ESCAPE_PEN:
      return True
    post_proj = data[0].x * n.x + data[0].y * n.y
    if post_proj <= 0:
      return True
    v = data[0]
    data[0] = pymunk.Vec2d(v.x - n.x * post_proj, v.y - n.y * post_proj)
    return True
  box = [pymunk.Vec2d(body.velocity.x, body.velocity.y)]
  body.each_arbiter(cb, box)
  body.velocity = box[0]
