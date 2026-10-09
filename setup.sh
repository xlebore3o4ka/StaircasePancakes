#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/core/sound.py"
s = open(p).read()

old = """  def play(self, name):
    bank = self.banks.get(name)
    if not bank:
      return
    random.choice(bank).play()"""
new = """  def play(self, name, volume=1.0):
    bank = self.banks.get(name)
    if not bank:
      return
    snd = random.choice(bank)
    snd.set_volume(SOUND_VOLUME * max(0.0, min(1.0, volume)))
    snd.play()"""
assert old in s, "play"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "shared/const.py"
s = open(p).read()

old = 'SOUND_NAMES = ["jump"]\n'
new = """SOUND_NAMES = ["jump", "hit"]
# <NOTE>#693 impact tuning: below MIN no sound, above MAX full volume
HIT_VOL_MIN = 250
HIT_VOL_MAX = 1800
HIT_COOLDOWN = 0.08
"""
assert old in s, "SOUND_NAMES"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

old = "from shared.const import "
idx = s.find(old)
assert idx != -1, "const import"
end = s.find("\n", idx)
line = s[idx:end]
add = ", HIT_VOL_MIN, HIT_VOL_MAX, HIT_COOLDOWN"
if "HIT_VOL_MIN" not in line:
  s = s[:end] + add + s[end:]

# snapshot full velocity for impact detection
old = """  def record_pre_step(self):
    # <STRANGE>#678 store vy before step; post_step compares
    self._pre_vy = self.body.velocity.y"""
new = """  def record_pre_step(self):
    # <STRANGE>#678 store pre-step velocity; post_step compares vy for bias and full v for impact volume
    self._pre_vy = self.body.velocity.y
    self._pre_v = pymunk.Vec2d(self.body.velocity.x, self.body.velocity.y)"""
assert old in s, "record_pre_step"
s = s.replace(old, new, 1)

# init fields
old = "    self._pre_vy = 0.0\n"
new = "    self._pre_vy = 0.0\n    self._pre_v = pymunk.Vec2d(0, 0)\n    self._hit_cd = 0.0\n"
assert old in s, "init"
s = s.replace(old, new, 1)

# play impact in post_step
old = """    v = self.body.velocity.y
    if v > 0 and (v - self._pre_vy) > 300:
      self.body.velocity = (self.body.velocity.x, 0.0)
"""
new = """    v = self.body.velocity.y
    if v > 0 and (v - self._pre_vy) > 300:
      self.body.velocity = (self.body.velocity.x, 0.0)
    # <STRANGE>#694 impact sfx: any new contact with floor/platform while moving into it fast
    if self.sound is not None and self._hit_cd <= 0:
      max_proj = 0.0
      def cb(arb, _):
        nonlocal max_proj
        if not arb.is_first_contact:
          return True
        a, b = arb.shapes
        if a.body is self.body:
          other = b
          n = -arb.contact_point_set.normal
        elif b.body is self.body:
          other = a
          n = arb.contact_point_set.normal
        else:
          return True
        if not (other.filter.categories & 0b10):
          return True
        p = -(self._pre_v.x * n.x + self._pre_v.y * n.y)
        if p > max_proj:
          max_proj = p
        return True
      self.body.each_arbiter(cb, None)
      if max_proj >= HIT_VOL_MIN:
        vol = (max_proj - HIT_VOL_MIN) / max(1, HIT_VOL_MAX - HIT_VOL_MIN)
        vol = min(1.0, max(0.15, vol))
        self.sound.play("hit", volume=vol)
        self._hit_cd = HIT_COOLDOWN
    if self._hit_cd > 0:
      self._hit_cd -= dt
"""
assert old in s, "post_step impact"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['shared/const.py','game/core/sound.py','game/entities/player.py']]; print('syntax ok')"

git add -A
git commit -m "sound: volume-scaled hit sfx on wall/floor impacts"