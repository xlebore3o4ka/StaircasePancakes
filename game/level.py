import json
import os
import random
import tarfile
import tempfile
from shared.version import read as _read_version, parse as _parse_version
from .entities.peg import Peg
from .entities.platform import Platform, PLAT_W, PLAT_H, PLAT_FILL, PLAT_EDGE
from .entities.background import Background, BG_FILL
from .entities.item import make_item
import pymunk

class Level:
  def _resolve_path(self, path):
    # <STRANGE>#1010 .tar levels unpack into a tempdir; TemporaryDirectory cleans up on GC
    if not path.endswith(".tar"):
      return path
    self._tmpdir = tempfile.TemporaryDirectory(prefix="staircase_")
    # <STRANGE>#1011 filter='data' blocks path traversal, absolute paths and symlinks
    with tarfile.open(path, "r") as tf:
      tf.extractall(self._tmpdir.name, filter="data")
    inner = os.path.join(self._tmpdir.name, "level.json")
    if not os.path.exists(inner):
      raise RuntimeError(f"{path}: no level.json inside archive")
    return inner

  def __init__(self, space, path, sound=None, cheats=False):
    self.space = space
    self.sound = sound
    # <STRANGE>#973 one-shot world events to broadcast; drained each frame by game.py
    self.net_events = []
    # <STRANGE>#1010 tempdir for tar-unpacked levels; kept alive for the level's lifetime
    self._tmpdir = None
    json_path = self._resolve_path(path)
    data = json.load(open(json_path))
    # <STRANGE>#999 level may declare a minimum game version; hard-fail if we're older
    required = data.get("version")
    if required is not None:
      cur = _read_version()
      if _parse_version(cur) < _parse_version(required):
        raise RuntimeError(
          f"level {path} requires version >= {required}, current {cur}")
    # <STRANGE>#560 seed drives any random spawning; missing field means a fresh random seed each run
    self.seed = data.get("seed")
    if self.seed is None:
      self.seed = random.randrange(2**31)
    random.seed(self.seed)
    # <STRANGE>#239 pegs accept both [x,y] and {x,y}; keeps old levels valid
    # <STRANGE>#699 layer from JSON overrides class default; editor writes it, game must read it back
    self.pegs = []
    for p in data.get("pegs", []):
      if isinstance(p, dict):
        peg = Peg(space, (p["x"], p["y"]))
        if "layer" in p:
          peg.layer = int(p["layer"])
        self.pegs.append(peg)
      else:
        self.pegs.append(Peg(space, tuple(p)))
    self.platforms = []
    for pd in data.get("platforms", []):
      points = None
      # <STRANGE>#841 same polygon convention as backgrounds: centre-relative points, minimum 3
      if pd.get("polygon") and isinstance(pd.get("points"), list) and len(pd["points"]) >= 3:
        points = [(float(p[0]), float(p[1])) for p in pd["points"]]
      plat = Platform(
        space, (pd["x"], pd["y"]),
        w=pd.get("w", PLAT_W),
        h=pd.get("h", PLAT_H),
        fill=tuple(pd.get("fill", PLAT_FILL)),
        edge=tuple(pd.get("edge", PLAT_EDGE)),
        points=points,
      )
      if "layer" in pd:
        plat.layer = int(pd["layer"])
      self.platforms.append(plat)
    self.backgrounds = []
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
      self.backgrounds.append(bg)
    self.items = []
    for it_spec in data.get("items", []):
      item = make_item(space, it_spec)
      if "layer" in it_spec:
        item.layer = int(it_spec["layer"])
      if self.sound is not None:
        item.sound = self.sound
      self.items.append(item)
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
      sp_item = make_item(space, spec)
      if self.sound is not None:
        sp_item.sound = self.sound
      self.items.append(sp_item)
    # <STRANGE>#892 bag is a single top-level [x, y]; skipped with cheats (pockets already on)
    bag_data = data.get("bag")
    if bag_data and not cheats:
      if isinstance(bag_data[0], (int, float)):
        bx, by = bag_data[0], bag_data[1]
      else:
        bx, by = bag_data[0][0], bag_data[0][1]
      bag = make_item(space, {"x": bx, "y": by, "type": "bag"})
      if self.sound is not None:
        bag.sound = self.sound
      self.items.append(bag)

  def spawn_item(self, pos, spec, vel=(0, 0)):
    # <STRANGE>#575 spec is a full dict (type + extras); fill in x/y and pass through
    full = dict(spec)
    full["x"] = pos[0]
    full["y"] = pos[1]
    # <STRANGE>#790 "peg_static" is not a carryable item: create a real static Peg here instead
    if full.get("type") == "peg_static":
      peg = Peg(self.space, (full["x"], full["y"]), from_item=True)
      if "layer" in spec:
        peg.layer = int(spec["layer"])
      self.pegs.append(peg)
      # <STRANGE>#973 broadcast to peers unless this spawn came from the network
      if not spec.get("_from_net"):
        self.net_events.append({"t": "place_peg", "x": full["x"], "y": full["y"]})
      # <STRANGE>#795 return so Player can attach a hand immediately
      return peg
    it = make_item(self.space, full)
    if "layer" in spec:
      it.layer = int(spec["layer"])
    if self.sound is not None:
      it.sound = self.sound
    # <STRANGE>#370 initial velocity set after make_item so the body is already dynamic at spawn
    it.body.velocity = vel
    self.items.append(it)
    # <STRANGE>#964 return so the caller can tag the freshly spawned item
    return it

  def grabbables(self):
    # <STRANGE>#523 stuck rebars join the peg list so the player's existing grab loop handles them
    stuck = [it for it in self.items if getattr(it, "stuck", False)]
    return self.pegs + self.platforms + stuck

  def post_step(self, player, cam=None):
    # <STRANGE>#524 runs after space.step; shape_query on each flying rebar finds overlaps with floor/platform
    for it in self.items:
      if getattr(it, "flying", False):
        # <STRANGE>#527 rebar mask is 0b10 while flying, so shape_query returns only floor/platform touches
        hits = self.space.shape_query(it.shape)
        if hits:
          it.stick(cam)
          # <STRANGE>#973 broadcast stuck rebar with its net_id so peers can drop the lingering ghost
          self.net_events.append({
            "t": "place_rebar",
            "x": it.body.position.x, "y": it.body.position.y,
            "angle": it.body.angle, "id": it.net_id,
          })
          continue
      # <STRANGE>#654 per-item bias clamp after physics; cam passed for sfx visibility check
      it.post_step(cam)


  def draw_spawners(self, screen, cam, player_pos):
    # <STRANGE>#563 debug only: draws marker at each spawner; shows entries when player is nearby
    import pygame
    sw, sh = screen.get_size()
    for sp in self.spawners:
      sx, sy = cam.to_screen(sp["x"], sp["y"])
      if sx < -200 or sx > sw + 200 or sy < -200 or sy > sh + 200:
        continue
      pygame.draw.circle(screen, (80, 200, 255), (int(sx), int(sy)), 10, LINE_W)
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
