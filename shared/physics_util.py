import pymunk


def has_ground_contact(body):
  """True if body touches a floor/platform shape with an upward normal."""
  result = [False]
  def cb(arb, data):
    a, b = arb.shapes
    if a.body is body:
      other = b
      ny = -arb.contact_point_set.normal.y
    elif b.body is body:
      other = a
      ny = arb.contact_point_set.normal.y
    else:
      return True
    if not (other.filter.categories & 0b10):
      return True
    if ny > 0.5:
      result[0] = True
      return False
    return True
  body.each_arbiter(cb, None)
  return result[0]
