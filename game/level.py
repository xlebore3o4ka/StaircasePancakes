import json
from .entities.peg import Peg
from .entities.platform import Platform, PLAT_W, PLAT_H, PLAT_FILL, PLAT_EDGE
from .entities.background import Background, BG_FILL
from .entities.item import make_item
import pymunk

class Level:
  def __init__(self, space, path):
    self.space = space
    data = json.load(open(path))
    # <STRANGE>#239 pegs accept both [x,y] and {x,y}; keeps old levels valid
    self.pegs = []
    for p in data.get("pegs", []):
      if isinstance(p, dict):
        self.pegs.append(Peg(space, (p["x"], p["y"])))
      else:
        self.pegs.append(Peg(space, tuple(p)))
    self.platforms = []
    for pd in data.get("platforms", []):
      self.platforms.append(Platform(
        space, (pd["x"], pd["y"]),
        w=pd.get("w", PLAT_W),
        h=pd.get("h", PLAT_H),
        fill=tuple(pd.get("fill", PLAT_FILL)),
        edge=tuple(pd.get("edge", PLAT_EDGE)),
      ))
    self.backgrounds = [
      Background((bd["x"], bd["y"]), bd["w"], bd["h"], tuple(bd.get("color", BG_FILL)))
      for bd in data.get("backgrounds", [])
    ]
    self.items = [make_item(space, it) for it in data.get("items", [])]

  def spawn_item(self, pos, type_name, vel=(0, 0)):
    # <STRANGE>#299 wraps pos into a spec dict so make_item stays the single entry point for item creation
    spec = {"x": pos[0], "y": pos[1], "type": type_name}
    it = make_item(self.space, spec)
    # <STRANGE>#370 initial velocity set after make_item so the body is already dynamic at spawn
    it.body.velocity = vel
    self.items.append(it)

  def grabbables(self):
    return self.pegs + self.platforms

  def update(self, player, dt=1/60):
    pass
  def draw_backgrounds(self, screen, cam):
    for b in self.backgrounds:
      b.draw(screen, cam)

  def draw_items(self, screen, cam):
    # <STRANGE>#250 held items drawn by Player; skip held and consuming to avoid double draw
    for it in self.items:
      if it.held_by is None:
        it.draw(screen, cam)

  def draw(self, screen, cam):
    for peg in self.pegs:
      peg.draw(screen, cam)
    for plat in self.platforms:
      plat.draw(screen, cam)
