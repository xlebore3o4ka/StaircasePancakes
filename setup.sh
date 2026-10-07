#!/bin/sh
set -e

python - <<'PYEOF'
p = "shared/const.py"
s = open(p).read()

old = "ARM_HOLD_ALPHA = 130\n"
new = """ARM_HOLD_ALPHA = 130
ARM_HOLD_SCALE = 0.5
"""
assert old in s, "ARM_HOLD_ALPHA"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python - <<'PYEOF'
p = "game/entities/player.py"
s = open(p).read()

old = "from shared.const import BODY_R, ARM_R, ARM_DX, JUMP_V, PEG_R, ITEM_OFFSET, ITEM_USE_SHAKE_TIME, ITEM_USE_SHAKE_AMP, ARM_HOLD_ALPHA\n"
new = "from shared.const import BODY_R, ARM_R, ARM_DX, JUMP_V, PEG_R, ITEM_OFFSET, ITEM_USE_SHAKE_TIME, ITEM_USE_SHAKE_AMP, ARM_HOLD_ALPHA, ARM_HOLD_SCALE\n"
assert old in s, "player imports"
s = s.replace(old, new, 1)

old = """      r = int(self.arm_r[i] * sc)
      # <STRANGE>#93 stamina tints arm from white (full) to red (empty); R stays 223, G/B lerp
      # <STRANGE>#99 stamina can go negative from jump cost before drain clamp runs; clamp t to [0,1]
      arm_color = (223, int(223 * s_t), int(223 * s_t))
      if self.held[i] is not None:
        # <STRANGE>#271 arm goes translucent with item in hand so the item reads through it
        size = r * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*arm_color, ARM_HOLD_ALPHA), (r, r), r)
        screen.blit(surf, (int(ax) - r, int(ay) - r))
      else:
        pygame.draw.circle(screen, arm_color, (int(ax), int(ay)), r)"""
new = """      # <STRANGE>#93 stamina tints arm from white (full) to red (empty); R stays 223, G/B lerp
      # <STRANGE>#99 stamina can go negative from jump cost before drain clamp runs; clamp t to [0,1]
      arm_color = (223, int(223 * s_t), int(223 * s_t))
      if self.held[i] is not None:
        # <STRANGE>#274 arm shrinks to half and goes translucent while holding; no ring drawn so item reads clearly
        r = int(self.arm_r[i] * ARM_HOLD_SCALE * sc)
        size = r * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*arm_color, ARM_HOLD_ALPHA), (r, r), r)
        screen.blit(surf, (int(ax) - r, int(ay) - r))
      else:
        r = int(self.arm_r[i] * sc)
        pygame.draw.circle(screen, arm_color, (int(ax), int(ay)), r)"""
assert old in s, "arm draw"
s = s.replace(old, new, 1)

old = """      # <STRANGE>#77 grab_lock means released after jump; draw as if not pressed even though button is held
      # <STRANGE>#98 stamina gate only blocks NEW press visuals; ongoing grab keeps its filled marker until release
      pressed_vis = self.grabbed[i] is not None or (self.pressed[i] and not self.grab_lock[i] and self.stamina[i] > STAMINA_GRAB_MIN)
      if pressed_vis:"""
new = """      # <STRANGE>#77 grab_lock means released after jump; draw as if not pressed even though button is held
      # <STRANGE>#98 stamina gate only blocks NEW press visuals; ongoing grab keeps its filled marker until release
      # <STRANGE>#275 no marker while holding an item; the held cube itself is the visual indicator
      pressed_vis = self.held[i] is None and (self.grabbed[i] is not None or (self.pressed[i] and not self.grab_lock[i] and self.stamina[i] > STAMINA_GRAB_MIN))
      if pressed_vis:"""
assert old in s, "pressed_vis"
s = s.replace(old, new, 1)

open(p, "w").write(s)
PYEOF

python -c "import ast; [ast.parse(open(f).read()) for f in ['shared/const.py','game/entities/player.py']]; print('syntax ok')"