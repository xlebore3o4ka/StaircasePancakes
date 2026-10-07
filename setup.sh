#!/bin/sh
set -e

python - <<'EOF'
p = "game/entities/player.py"
s = open(p).read()

old = """    # <STRANGE>#193 scancode not key: e.key depends on layout (K_a != Cyrillic "a"), scancode is physical position
    elif e.type == pygame.KEYDOWN:
      if e.scancode == pygame.SCANCODE_A:
        self.move[0] = True
      elif e.scancode == pygame.SCANCODE_D:
        self.move[1] = True
      elif e.scancode == pygame.SCANCODE_SPACE:
        self.jump = True
        self.jump_queued = True
    elif e.type == pygame.KEYUP:
      if e.scancode == pygame.SCANCODE_A:
        self.move[0] = False
      elif e.scancode == pygame.SCANCODE_D:
        self.move[1] = False
      elif e.scancode == pygame.SCANCODE_SPACE:
        self.jump = False
        # <STRANGE>#182 queue must clear on release; otherwise pressing in air and releasing still fires on landing
        self.jump_queued = False"""
new = """    # <STRANGE>#193 scancode not key: e.key depends on layout (K_a != Cyrillic "a"), scancode is physical position
    # <STRANGE>#196 pygame-ce exposes no SCANCODE_* constants; raw SDL scancodes: A=4, D=7, SPACE=44
    elif e.type == pygame.KEYDOWN:
      if e.scancode == 4:
        self.move[0] = True
      elif e.scancode == 7:
        self.move[1] = True
      elif e.scancode == 44:
        self.jump = True
        self.jump_queued = True
    elif e.type == pygame.KEYUP:
      if e.scancode == 4:
        self.move[0] = False
      elif e.scancode == 7:
        self.move[1] = False
      elif e.scancode == 44:
        self.jump = False
        # <STRANGE>#182 queue must clear on release; otherwise pressing in air and releasing still fires on landing
        self.jump_queued = False"""
assert old in s, "handle_event"
s = s.replace(old, new, 1)

open(p, "w").write(s)
EOF

python -c "import ast; ast.parse(open('game/entities/player.py').read()); print('syntax ok')"