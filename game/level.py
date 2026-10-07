import json
from .entities.peg import Peg
from .entities.platform import Platform, PLAT_W, PLAT_H, PLAT_FILL, PLAT_EDGE

class Level:
  def __init__(self, space, path):
    self.space = space
    data = json.load(open(path))
    self.pegs = [Peg(space, tuple(p)) for p in data.get("pegs", [])]
    self.platforms = []
    for pd in data.get("platforms", []):
      self.platforms.append(Platform(
        space, (pd["x"], pd["y"]),
        w=pd.get("w", PLAT_W),
        h=pd.get("h", PLAT_H),
        fill=tuple(pd.get("fill", PLAT_FILL)),
        edge=tuple(pd.get("edge", PLAT_EDGE)),
      ))

  def grabbables(self):
    return self.pegs + self.platforms

  def update(self, player):
    pass

  def draw(self, screen, cam):
    for peg in self.pegs:
      peg.draw(screen, cam)
    for plat in self.platforms:
      plat.draw(screen, cam)
