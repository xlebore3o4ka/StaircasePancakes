#!/bin/sh
set -e

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

old = """              cur = self.body.position.get_distance(world_pt)
              # <STRANGE>#438 min = ARM_DX always; if grabbed while arm is inside body, joint pushes body out so arm renders outside
              max_len = max(cur, ARM_DX)
              self.joints[i] = pymunk.SlideJoint(self.body, obj.body, (0, 0), anchor, ARM_DX, max_len)
              self.joints[i].max_force = REEL_MAX_FORCE
              self.rope_len[i] = max_len
              self.space.add(self.joints[i])"""
new = """              cur = self.body.position.get_distance(world_pt)
              # <STRANGE>#617 rope not rod: min=0 so body can hug walls without the joint fighting collision; max caps distance
              max_len = max(cur, ARM_DX)
              self.joints[i] = pymunk.SlideJoint(self.body, obj.body, (0, 0), anchor, 0, max_len)
              self.joints[i].max_force = REEL_MAX_FORCE
              self.rope_len[i] = max_len
              self.space.add(self.joints[i])"""
assert old in s, "joint creation"
s = s.replace(old, new, 1)

old = """          if self.rope_len[i] > ARM_DX:
            self.rope_len[i] = max(ARM_DX, self.rope_len[i] - per_sec(REEL_SPEED, dt))
            # <STRANGE>#439 keep min = ARM_DX on every reel tick; max reels in, min never drops below the natural reach
            self.joints[i].min = ARM_DX
            self.joints[i].max = self.rope_len[i]"""
new = """          if self.rope_len[i] > ARM_DX:
            self.rope_len[i] = max(ARM_DX, self.rope_len[i] - per_sec(REEL_SPEED, dt))
            # <STRANGE>#618 min stays 0; only max reels in. Body can go closer than ARM_DX if physics pushes it
            self.joints[i].max = self.rope_len[i]"""
assert old in s, "reel"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; ast.parse(open('game/entities/player.py').read()); print('syntax ok')"

git add -A
git commit -m "player: rope-style slide joint (min=0, max=rope_len) stops wall jitter"