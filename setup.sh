#!/bin/sh
set -e

python - <<'PYEOF'
p = "shared/const.py"
s = open(p).read()

old = 'ITEM_TYPES = ["cube", "soda", "rebar"]\n'
new = 'ITEM_TYPES = ["cube", "soda", "rebar", "peg"]\n'
assert old in s, "ITEM_TYPES"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/item.py"
s = open(p).read()

# imports: PEG_R, PEG_FILL, PEG_EDGE, PEG_EDGE_W, LAYER_PEG
old = "  SODA_W, SODA_H, SODA_BLUE, SODA_WHITE, SODA_STAMINA, LAYER_ITEM,\n"
new = "  SODA_W, SODA_H, SODA_BLUE, SODA_WHITE, SODA_STAMINA, LAYER_ITEM,\n  PEG_R, PEG_FILL, PEG_EDGE, PEG_EDGE_W,\n"
assert old in s, "item imports"
s = s.replace(old, new, 1)

# class PortablePegItem
old = "def make_item(space, spec):"
new = '''class PortablePegItem(Item):
  # <STRANGE>#778 carryable peg: same look and size as a static Peg, but a plain item (no grapplable hooks)
  def __init__(self, space, pos):
    super().__init__(space, pos, PEG_R * 2, PEG_R * 2)

  def draw_at(self, screen, cam, pos, angle, alpha, scale):
    sc = cam.scale * scale
    x, y = cam.to_screen(pos[0], pos[1])
    r = max(1, int(PEG_R * sc))
    if alpha < 255:
      surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
      pygame.draw.circle(surf, (*PEG_FILL, alpha), (r, r), r)
      pygame.draw.circle(surf, (*PEG_EDGE, alpha), (r, r), r, max(1, int(PEG_EDGE_W * sc)))
      screen.blit(surf, (int(x) - r, int(y) - r))
    else:
      pygame.draw.circle(screen, PEG_FILL, (int(x), int(y)), r)
      pygame.draw.circle(screen, PEG_EDGE, (int(x), int(y)), r, max(1, int(PEG_EDGE_W * sc)))


def make_item(space, spec):'''
assert old in s, "make_item anchor"
s = s.replace(old, new, 1)

old = """  if t == "rebar":
    return RebarItem(space, pos)
  if t == "cube":"""
new = """  if t == "rebar":
    return RebarItem(space, pos)
  if t == "peg":
    return PortablePegItem(space, pos)
  if t == "cube":"""
assert old in s, "make_item body"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['shared/const.py','game/entities/item.py']]; print('syntax ok')"

git add -A
git commit -m "item: portable peg (carryable, no behavior yet)"