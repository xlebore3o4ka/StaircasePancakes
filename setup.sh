#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/entities/background.py"
s = open(p).read()

old = """class Background:
  layer = LAYER_BG

  def __init__(self, pos, w, h, color=BG_FILL):
    self.x, self.y = pos
    self.w, self.h = w, h
    self.color = color

  def draw(self, screen, cam):
    x0, y0 = cam.to_screen(self.x - self.w / 2, self.y + self.h / 2)
    x1, y1 = cam.to_screen(self.x + self.w / 2, self.y - self.h / 2)
    r = pygame.Rect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))
    # <SLOW>#198 cull: skip draw when fully off-screen; free win on large levels
    sw, sh = screen.get_size()
    if r.right < 0 or r.left > sw or r.bottom < 0 or r.top > sh:
      return
    pygame.draw.rect(screen, self.color, r)"""
new = """class Background:
  layer = LAYER_BG

  def __init__(self, pos, w, h, color=BG_FILL, points=None):
    self.x, self.y = pos
    self.w = w
    self.h = h
    self.color = color
    # <STRANGE>#771 polygon mode: points are offsets from the (x, y) centre, given in world units; None = plain rect
    self.points = points

  def _world_points(self):
    return [(self.x + px, self.y + py) for px, py in self.points]

  def _bbox(self):
    xs = [p[0] for p in self.points]
    ys = [p[1] for p in self.points]
    return (self.x + min(xs), self.x + max(xs),
            self.y + min(ys), self.y + max(ys))

  def draw(self, screen, cam):
    # <SLOW>#198 cull: skip draw when fully off-screen
    sw, sh = screen.get_size()
    if self.points is None:
      x0, y0 = cam.to_screen(self.x - self.w / 2, self.y + self.h / 2)
      x1, y1 = cam.to_screen(self.x + self.w / 2, self.y - self.h / 2)
      r = pygame.Rect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))
      if r.right < 0 or r.left > sw or r.bottom < 0 or r.top > sh:
        return
      pygame.draw.rect(screen, self.color, r)
      return
    l, r, b, t = self._bbox()
    sx0, sy0 = cam.to_screen(l, t)
    sx1, sy1 = cam.to_screen(r, b)
    lo_x, hi_x = (sx0, sx1) if sx0 < sx1 else (sx1, sx0)
    lo_y, hi_y = (sy0, sy1) if sy0 < sy1 else (sy1, sy0)
    if hi_x < 0 or lo_x > sw or hi_y < 0 or lo_y > sh:
      return
    pts = [cam.to_screen(wx, wy) for wx, wy in self._world_points()]
    pygame.draw.polygon(screen, self.color, pts)"""
assert old in s, "Background"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/level.py"
s = open(p).read()

old = """    self.backgrounds = []
    for bd in data.get("backgrounds", []):
      bg = Background((bd["x"], bd["y"]), bd["w"], bd["h"], tuple(bd.get("color", BG_FILL)))
      if "layer" in bd:
        bg.layer = int(bd["layer"])
      self.backgrounds.append(bg)"""
new = """    self.backgrounds = []
    for bd in data.get("backgrounds", []):
      points = None
      # <STRANGE>#771 polygon mode: points relative to centre; at least 3 required, fewer is ignored
      if bd.get("polygon") and isinstance(bd.get("points"), list) and len(bd["points"]) >= 3:
        points = [(float(p[0]), float(p[1])) for p in bd["points"]]
      bg = Background(
        (bd["x"], bd["y"]),
        bd.get("w", 0), bd.get("h", 0),
        tuple(bd.get("color", BG_FILL)),
        points=points,
      )
      if "layer" in bd:
        bg.layer = int(bd["layer"])
      self.backgrounds.append(bg)"""
assert old in s, "backgrounds load"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['game/entities/background.py','game/level.py']]; print('syntax ok')"

git add -A
git commit -m "background: optional polygon mode with center-relative points"