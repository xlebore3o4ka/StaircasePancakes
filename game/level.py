import random
from .entities.peg import Peg, PEG_R
from .entities.platform import Platform
from .entities.player import BODY_R

BATCH = 10
PEG_STEP = 220
PEG_WANDER = 250
PLAT_OFFSET = 250

class Level:
  def __init__(self, space, sw):
    self.space = space
    self.pegs = []
    self.platforms = []
    self.cx = sw / 2
    self.cy = BODY_R + PEG_R + BODY_R
    self._spawn_batch()

  def _spawn_batch(self):
    for _ in range(BATCH):
      self.pegs.append(Peg(self.space, (self.cx, self.cy)))
      # <STRANGE>#130 wander applies to x only; step fixed so vertical spacing is predictable
      self.cx += random.uniform(-PEG_WANDER, PEG_WANDER)
      self.cy += PEG_STEP
    self.platforms.append(Platform(self.space, (self.cx + PLAT_OFFSET, self.cy)))
    # <STRANGE>#131 advance cy past platform y so next batch's first peg doesn't spawn inside the platform
    self.cy += PEG_STEP

  def grabbables(self):
    return self.pegs + self.platforms

  def update(self, player):
    # <STRANGE>#132 trigger fires when player reaches top platform; new platform spawns far above so no re-fire
    if player.body.position.y >= self.platforms[-1].body.position.y:
      self._spawn_batch()

  def draw(self, screen, cam):
    for peg in self.pegs:
      peg.draw(screen, cam)
    for plat in self.platforms:
      plat.draw(screen, cam)
