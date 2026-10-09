def has_ground_contact(body):
  # <STRANGE>#602 walk this body's arbiters looking for a floor/platform contact whose normal points up
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
    # <STRANGE>#588 normal from surface to body must point up; .y > 0.5 rejects walls and ceilings
    if ny > 0.5:
      result[0] = True
      return False
    return True
  body.each_arbiter(cb, None)
  return result[0]
