#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/entities/hud_info.py"
s = open(p).read()

old = """  def _fmt_time(self):
    total = int(self.t)
    h, rem = divmod(total, 3600)
    m, sec = divmod(rem, 60)
    if h > 0:
      return f"{h}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}\""""
new = """  def _fmt_time(self):
    # <STRANGE>#610 always hh:mm:ss.MM; centiseconds used as MM since pygame doesn't give sub-frame timing
    total = self.t
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    sec = int(total % 60)
    cs = int((total * 100) % 100)
    return f"{h:02d}:{m:02d}:{sec:02d}.{cs:02d}\""""
assert old in s, "_fmt_time"
s = s.replace(old, new, 1)

old = """    meters = max(0.0, (height_px - BODY_R) * HUD_METERS_PER_PX)
    lines = [self._fmt_time(), f"{meters:.1f} m"]"""
new = """    meters = max(0.0, (height_px - BODY_R) * HUD_METERS_PER_PX)
    lines = [self._fmt_time(), f"{int(meters)} m"]"""
assert old in s, "lines"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('game/entities/hud_info.py').read()); print('syntax ok')"

git add -A
git commit -m "hud: centisecond timer, integer meters"