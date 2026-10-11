import json
import os
import random
import tarfile
import tempfile
import pymunk
from shared.version import read as _read_version, parse as _parse_version
from .entities.peg import Peg
from .entities.platform import Platform, PLAT_W, PLAT_H, PLAT_FILL, PLAT_EDGE
from .entities.background import Background, BG_FILL
from .entities.item import make_item
from shared.const import LINE_W
from shared.const import LINE_W
from .entities.trigger import Trigger
from .debug_view import DebugArrows
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
    # <STRANGE>#1017 lazy debug arrow helper (only used with --debugview)
    self._arrows = DebugArrows()
    # <STRANGE>#1041 active smooth-move animations; each entry drives one object over time
    self.movers = []
    json_path = self._resolve_path(path)
    # <STRANGE>#1027 scripts resolve relative to the json's directory; works for both json and tar layouts
    self.base_dir = os.path.dirname(json_path)
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
        if "id" in p:
          peg.id = p["id"]
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
      if "id" in pd:
        plat.id = pd["id"]
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
      if "id" in bd:
        bg.id = bd["id"]
      self.backgrounds.append(bg)
    self.items = []
    for it_spec in data.get("items", []):
      item = make_item(space, it_spec)
      if "layer" in it_spec:
        item.layer = int(it_spec["layer"])
      if "id" in it_spec:
        item.id = it_spec["id"]
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
      if chosen_entry.get("id"):
        sp_item.id = chosen_entry["id"]
      if self.sound is not None:
        sp_item.sound = self.sound
      self.items.append(sp_item)
    # <STRANGE>#1015 invisible trigger zones; scripts run while player is inside
    self.triggers = []
    for td in data.get("triggers", []):
      self.triggers.append(Trigger(
        td["x"], td["y"], td.get("w", 80), td.get("h", 80),
        trigger_id=td.get("id"), script=td.get("script")))


    # <STRANGE>#892 bag is a single top-level [x, y]; skipped with cheats (pockets already on)
    bag_data = data.get("bag")
    if bag_data and not cheats:
      # <STRANGE>#1016 bag is a dict now: {"x", "y", optional "id"}
      bag = make_item(space, {"x": bag_data["x"], "y": bag_data["y"], "type": "bag"})
      if bag_data.get("id"):
        bag.id = bag_data["id"]
      if self.sound is not None:
        bag.sound = self.sound
      self.items.append(bag)

    # <STRANGE>#1034 on_load runs only after every object exists, so scripts can query the whole level
    # <STRANGE>#1036 id -> object index; duplicate ids keep the first, warn on the rest
    self.by_id = {}
    for o in self.debug_objects():
      oid = getattr(o, "id", None)
      if not oid:
        continue
      if oid in self.by_id:
        print(f"level: duplicate id {oid!r}, ignoring later definition")
        continue
      self.by_id[oid] = o
    for t in self.triggers:
      t.load(self.base_dir, self)

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
    if "id" in spec:
      it.id = spec["id"]
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


  def debug_objects(self):
    # <STRANGE>#1017 every id-bearing object in the level; order doesn't matter for arrow drawing
    return self.pegs + self.platforms + self.backgrounds + self.items + self.triggers

  def move_to(self, target, x=None, y=None, dur=0.5, ease="out"):
    # <STRANGE>#1042 start a smooth move; cancels existing movers on the same object
    # <STRANGE>#1047 accept either a string id or the object itself
    obj = self.by_id.get(target) if isinstance(target, str) else target
    if obj is None:
      return False
    self.movers = [m for m in self.movers if m["obj"] is not obj]
    entry = {"obj": obj, "t": 0.0, "dur": max(0.01, dur), "ease": ease, "axis": {}}
    if x is not None:
      entry["axis"]["x"] = (self._current(obj, "x"), x)
    if y is not None:
      entry["axis"]["y"] = (self._current(obj, "y"), y)
    if not entry["axis"]:
      return True
    # <STRANGE>#1056 kinematic during the move so Chipmunk carries attached bodies (standing player, joints) along
    body = getattr(obj, "body", None)
    if body is not None and body.body_type == pymunk.Body.STATIC:
      body.body_type = pymunk.Body.KINEMATIC
      body.velocity = (0, 0)
    self.movers.append(entry)
    return True

  def cancel_move(self, target):
    obj = self.by_id.get(target) if isinstance(target, str) else target
    if obj is None:
      return
    self.movers = [m for m in self.movers if m["obj"] is not obj]
    body = getattr(obj, "body", None)
    if body is not None and body.body_type == pymunk.Body.KINEMATIC:
      body.velocity = (0, 0)
      body.body_type = pymunk.Body.STATIC

  @staticmethod
  def _current(obj, axis):
    if hasattr(obj, "body"):
      return getattr(obj.body.position, axis)
    return getattr(obj, axis)

  def _snap(self, obj, x=None, y=None):
    # <STRANGE>#1057 teleport, reindex, wake anything attached; only used for the final snap after a kinematic move
    if hasattr(obj, "body"):
      p = obj.body.position
      obj.body.position = (x if x is not None else p.x,
                           y if y is not None else p.y)
      self.space.reindex_shapes_for_body(obj.body)
    else:
      if x is not None:
        obj.x = x
      if y is not None:
        obj.y = y

  @staticmethod
  def _ease(name, k):
    if k <= 0.0:
      return 0.0
    if k >= 1.0:
      return 1.0
    if name == "in":
      return k * k
    if name == "out":
      return 1.0 - (1.0 - k) * (1.0 - k)
    if name == "inout":
      return k * k * (3 - 2 * k)
    return k

  def update_movers(self, dt):
    if not self.movers:
      return
    keep = []
    for m in self.movers:
      m["t"] += dt
      k = min(1.0, m["t"] / m["dur"])
      e = self._ease(m["ease"], k)
      nx = None
      ny = None
      if "x" in m["axis"]:
        a, b = m["axis"]["x"]
        nx = a + (b - a) * e
      if "y" in m["axis"]:
        a, b = m["axis"]["y"]
        ny = a + (b - a) * e
      body = getattr(m["obj"], "body", None)
      if body is not None and body.body_type == pymunk.Body.KINEMATIC:
        # <STRANGE>#1058 set velocity so Chipmunk integrates position this step and drags contacts/joints with it
        cur_x = body.position.x
        cur_y = body.position.y
        vx = ((nx - cur_x) / dt) if (nx is not None and dt > 0) else 0.0
        vy = ((ny - cur_y) / dt) if (ny is not None and dt > 0) else 0.0
        body.velocity = (vx, vy)
        if m["t"] >= m["dur"]:
          body.velocity = (0, 0)
          self._snap(m["obj"], nx, ny)
          body.body_type = pymunk.Body.STATIC
      else:
        self._snap(m["obj"], nx, ny)
      if m["t"] < m["dur"]:
        keep.append(m)
    self.movers = keep

  def update_triggers(self, dt, player_pos):
    for t in self.triggers:
      t.update(dt, player_pos[0], player_pos[1])

  def unload(self):
    # <STRANGE>#1028 on_unload for every script, called once when the level goes away
    for t in self.triggers:
      t.unload()

  def draw_debug(self, screen, cam, player_pos):
    # <STRANGE>#1015 debug overlay: spawners + triggers + id arrows, only under --debugview
    self.draw_spawners(screen, cam, player_pos)
    for t in self.triggers:
      t.draw_debug(screen, cam)
    self._arrows.draw(screen, cam, self.debug_objects())

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
