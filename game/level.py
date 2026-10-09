import json
import random
from .entities.peg import Peg
from .entities.platform import Platform, PLAT_W, PLAT_H, PLAT_FILL, PLAT_EDGE
from .entities.background import Background, BG_FILL
from .entities.item import make_item
import pymunk

class Level:
  def __init__(self, space, path):
    self.space = space
    data = json.load(open(path))
    # <STRANGE>#560 seed drives any random spawning; missing field means a fresh random seed each run
    self.seed = data.get("seed")
    if self.seed is None:
      self.seed = random.randrange(2**31)
    random.seed(self.seed)
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
    # <STRANGE>#562 itemSpawners roll once at load; weighted by count, "nothing" means no item
    self.spawners = []
    for sp in data.get("itemSpawners", []):
      entries = sp.get("items", [])
      total = sum(e.get("count", 0) for e in entries)
      if total <= 0:
        continue
      r = random.uniform(0, total)
      acc = 0.0
      chosen_entry = None
      for e in entries:
        acc += e.get("count", 0)
        if r <= acc:
          chosen_entry = e
          break
      self.spawners.append({"x": sp["x"], "y": sp["y"], "entries": entries})
      if chosen_entry is None:
        continue
      chosen = chosen_entry.get("type")
      if chosen is None or chosen == "nothing":
        continue
      # <STRANGE>#568 carry over any extra fields from the chosen entry (e.g. cube contents)
      spec = {"x": sp["x"], "y": sp["y"], "type": chosen}
      for k, v in chosen_entry.items():
        if k not in ("type", "count"):
          spec[k] = v
      self.items.append(make_item(space, spec))

  def spawn_item(self, pos, spec, vel=(0, 0)):
    # <STRANGE>#575 spec is a full dict (type + extras); fill in x/y and pass through
    full = dict(spec)
    full["x"] = pos[0]
    full["y"] = pos[1]
    it = make_item(self.space, full)
    # <STRANGE>#370 initial velocity set after make_item so the body is already dynamic at spawn
    it.body.velocity = vel
    self.items.append(it)

  def grabbables(self):
    # <STRANGE>#523 stuck rebars join the peg list so the player's existing grab loop handles them
    stuck = [it for it in self.items if getattr(it, "stuck", False)]
    return self.pegs + self.platforms + stuck

  def record_pre_step(self):
    # <STRANGE>#634 snapshot every dynamic item's velocity before the physics step
    for it in self.items:
      rec = getattr(it, "record_pre_step", None)
      if rec is not None:
        rec()

  def post_step(self, player):
    # <STRANGE>#524 runs after space.step; shape_query on each flying rebar finds overlaps with floor/platform
    for it in self.items:
      if getattr(it, "flying", False):
        # <STRANGE>#527 rebar mask is 0b10 while flying, so shape_query returns only floor/platform touches
        hits = self.space.shape_query(it.shape)
        if hits:
          it.stick()
          continue
      # <STRANGE>#599 per-item bias clamp after physics, same idea as Player.post_step
      it.post_step()

  def draw_spawners(self, screen, cam, player_pos):
    # <STRANGE>#563 debug only: draws marker at each spawner; shows entries when player is nearby
    import pygame
    sw, sh = screen.get_size()
    for sp in self.spawners:
      sx, sy = cam.to_screen(sp["x"], sp["y"])
      if sx < -200 or sx > sw + 200 or sy < -200 or sy > sh + 200:
        continue
      pygame.draw.circle(screen, (80, 200, 255), (int(sx), int(sy)), 10, 2)
      dx = sp["x"] - player_pos[0]
      dy = sp["y"] - player_pos[1]
      if dx * dx + dy * dy < 300 * 300:
        y = int(sy) - 20
        for e in sp["entries"]:
          lbl = f"{e.get('type','?')} x{e.get('count',0)}"
          surf = pygame.font.SysFont(None, 20).render(lbl, True, (255, 255, 255))
          screen.blit(surf, (int(sx) + 15, y))
          y -= 18

  def drawables(self):
    # <NOTE>#444 single source for the render list; held items are drawn by Player, not here
    free_items = [it for it in self.items if it.held_by is None]
    return self.backgrounds + self.platforms + self.pegs + free_items
