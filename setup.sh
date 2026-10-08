#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/entities/item.py"
s = open(p).read()

# добавим метод post_step в Item
old = """  def destroy(self):
    # <STRANGE>#295 destroy only removes physics; caller clears held_by on player side
    self.space.remove(self.body, self.shape)"""
new = """  def destroy(self):
    # <STRANGE>#295 destroy only removes physics; caller clears held_by on player side
    self.space.remove(self.body, self.shape)

  def post_step(self):
    # <STRANGE>#596 ignore kinematic items (held, stuck) — their vy is set by gameplay, not physics
    if self.body.body_type != pymunk.Body.DYNAMIC:
      return
    # <STRANGE>#597 any upward vy at ground contact is solver bias or bounce; clamp flat
    if self.body.velocity.y > 0 and self._has_ground_contact():
      self.body.velocity = (self.body.velocity.x, 0.0)

  def _has_ground_contact(self):
    # <STRANGE>#598 mirrors Player._has_ground_contact; category check 0b10 keeps it floor/platform only
    result = [False]
    def cb(arb, data):
      a, b = arb.shapes
      if a.body is self.body:
        other = b
        ny = -arb.contact_point_set.normal.y
      elif b.body is self.body:
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
    self.body.each_arbiter(cb, None)
    return result[0]"""
assert old in s, "destroy"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/level.py"
s = open(p).read()

old = """  def post_step(self, player):
    # <STRANGE>#524 runs after space.step; shape_query on each flying rebar finds overlaps with floor/platform
    for it in self.items:
      if not getattr(it, "flying", False):
        continue
      # <STRANGE>#527 rebar mask is 0b10 while flying, so shape_query returns only floor/platform touches
      hits = self.space.shape_query(it.shape)
      if hits:
        it.stick()"""
new = """  def post_step(self, player):
    # <STRANGE>#524 runs after space.step; shape_query on each flying rebar finds overlaps with floor/platform
    for it in self.items:
      if getattr(it, "flying", False):
        # <STRANGE>#527 rebar mask is 0b10 while flying, so shape_query returns only floor/platform touches
        hits = self.space.shape_query(it.shape)
        if hits:
          it.stick()
          continue
      # <STRANGE>#599 per-item bias clamp after physics, same idea as Player.post_step
      it.post_step()"""
assert old in s, "post_step"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['game/entities/item.py','game/level.py']]; print('syntax ok')"