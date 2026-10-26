import json
import math
import os
import random
import tarfile
import tempfile
import pymunk
import pygame
from shared.version import read as _read_version, parse as _parse_version
from .entities.peg import Peg
from .entities.platform import Platform, PLAT_W, PLAT_H, PLAT_FILL, PLAT_EDGE
from .entities.background import Background, BG_FILL
from .entities.item import make_item
from shared.const import LINE_W, MAX_KINEMATIC_V
from .entities.trigger import Trigger
from .entities.light import SunLight, LampLight, SpotLight
from .entities.button import Button
from .debug_view import DebugArrows

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

  def __init__(self, space, path, sound=None, cheats=False, script_seed=None):
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
    # <STRANGE>#1314 screen overlays; owned by level, ticked each frame by game.py
    self.texts = []
    self.toasts = []
    self.flashes = []
    # <STRANGE>#1195 set by game.py; scripts use it for ctx.shake
    self.cam = None
    # <STRANGE>#1195 set by game.py; scripts use it for ctx.shake
    self.cam = None
    json_path = self._resolve_path(path)
    # <STRANGE>#1203 content hash: same JSON+scripts -> same hash regardless of tar mtimes
    from shared.level_hash import hash_level
    self.content_hash = hash_level(path)
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
    # <STRANGE>#1148 script_seed is separate: server-provided in multiplayer, falls back to level seed in single
    self.script_seed = script_seed if script_seed is not None else self.seed
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
        absorption=float(pd.get("absorption", 0.5)),
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
    # <STRANGE>#5001 notes array from editor: spawn NoteItem for each entry
    for nt_spec in data.get("notes", []):
      item = make_item(space, nt_spec)
      if "layer" in nt_spec:
        item.layer = int(nt_spec["layer"])
      if "id" in nt_spec:
        item.id = nt_spec["id"]
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
    # <STRANGE>#1407 lighting config and light sources
    self.lighting_config = None
    ld_data = data.get("lighting")
    if ld_data is not None:
      self.lighting_config = {
        "ambient": tuple(ld_data.get("ambient", (60, 60, 70))),
        "gain": float(ld_data.get("gain", 1.6)),
      }
    self.lights = []
    for ld in data.get("lights", []):
      t = ld.get("type", "lamp")
      pos = (ld.get("x", 0.0), ld.get("y", 0.0))
      col = tuple(ld.get("color", (255, 240, 200)))
      inten = float(ld.get("intensity", 1.0))
      if t == "sun":
        lt = SunLight(color=col, intensity=inten,
                      direction=tuple(ld.get("direction", (0.5, 1.0))),
                      shadow_length=float(ld.get("shadow_length", 1000.0)),
                      gradient_length=float(ld.get("gradient_length", 100.0)))
      elif t == "spot":
        lt = SpotLight(pos,
                       angle=float(ld.get("angle", 0.0)),
                       length=float(ld.get("length", 500)),
                       cone=float(ld.get("cone", math.radians(60))),
                       color=col, intensity=inten)
      else:
        lt = LampLight(pos,
                       radius=float(ld.get("radius", 300)),
                       color=col, intensity=inten)
      if "id" in ld:
        lt.id = ld["id"]
      self.lights.append(lt)
      if self.lighting_config is None and t == "sun":
        self.lighting_config = {"ambient": (40, 40, 50), "gain": 1.6}
    # <STRANGE>#1742 weak glow attached to player position; created only with lighting enabled
    if self.lighting_config is not None:
      self.player_light = LampLight((0, 0), radius=140,
                                    color=(140, 160, 210), intensity=1.02)
      self.player_light.id = "_player_glow"
      self.lights.append(self.player_light)
    else:
      self.player_light = None

    # <STRANGE>#1069 hand-only grab targets
    self.buttons = []
    for bd in data.get("buttons", []):
      btn = Button(space, (bd["x"], bd["y"]), button_id=bd.get("id"))
      if "layer" in bd:
        btn.layer = int(bd["layer"])
      self.buttons.append(btn)

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

    # <STRANGE>#1555 unique lantern; hidden spotlight attached to it, off until held
    lantern_data = data.get("lantern")
    if lantern_data:
      lantern = make_item(space, {"x": lantern_data["x"], "y": lantern_data["y"], "type": "lantern"})
      if lantern_data.get("id"):
        lantern.id = lantern_data["id"]
      if self.sound is not None:
        lantern.sound = self.sound
      self.items.append(lantern)
      spot = SpotLight(
        (lantern_data["x"], lantern_data["y"]),
        angle=-math.pi / 2, length=700, cone=math.radians(40),
        color=(255, 220, 140), intensity=0.0)
      spot.id = (lantern_data.get("id") or "lantern") + "_beam"
      self.lights.append(spot)
      lantern.light = spot

    # <STRANGE>#1556 each frame: held lantern points beam at cursor, others stay off
    # (method defined below, registered via closure-less attribute for game.py call)

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
    for lt in self.lights:
      if lt.id and lt.id not in self.by_id:
        self.by_id[lt.id] = lt
    for t in self.triggers:
      t.load(self.base_dir, self, self.script_seed)

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
    return self.pegs + self.platforms + self.buttons + stuck

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


  def occluders(self):
    # <STRANGE>#1670 shadow casters grouped per-platform: each item is {bbox, edges}
    # where edges = (ax, ay, bx, by, nx, ny, nc_dot) with outward normal and centroid dot
    # Cache by (id(self), len(self.platforms), positions hash) to avoid rebuild every frame.
    cache = getattr(self, "_occ_cache", None)
    key = (len(self.platforms), tuple((p.body.position.x, p.body.position.y) for p in self.platforms))
    if cache is not None and cache[0] == key:
        return cache[1]
    segs = []
    for p in self.platforms:
      cx, cy = p.body.position.x, p.body.position.y
      if p.points is None:
        hw, hh = p.w / 2, p.h / 2
        corners = [(cx - hw, cy - hh), (cx + hw, cy - hh),
                   (cx + hw, cy + hh), (cx - hw, cy + hh)]
      else:
        corners = [(cx + px, cy + py) for px, py in p.points]
      n = len(corners)
      gx = sum(c[0] for c in corners) / n
      gy = sum(c[1] for c in corners) / n
      min_x = min(c[0] for c in corners)
      min_y = min(c[1] for c in corners)
      max_x = max(c[0] for c in corners)
      max_y = max(c[1] for c in corners)
      edges = []
      for i in range(n):
        ax, ay = corners[i]
        bx, by = corners[(i + 1) % n]
        nx = by - ay
        ny = -(bx - ax)
        tcx = gx - ax
        tcy = gy - ay
        nc_dot = nx * tcx + ny * tcy
        edges.append((ax, ay, bx, by, nx, ny, nc_dot))
      segs.append({"bbox": (min_x, min_y, max_x, max_y), "edges": edges, "points": corners, "absorption": getattr(p, "absorption", 0.5)})
      
    self._occ_cache = (key, segs)
    return segs

  def debug_objects(self):
    # <STRANGE>#1017 every id-bearing object in the level; order doesn't matter for arrow drawing
    return self.pegs + self.platforms + self.backgrounds + self.items + self.triggers + self.buttons

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
    # <STRANGE>#1062 platforms and pegs are kinematic from the start; nothing to switch here
    self.movers.append(entry)
    return True

  def cancel_move(self, target):
    obj = self.by_id.get(target) if isinstance(target, str) else target
    if obj is None:
      return
    self.movers = [m for m in self.movers if m["obj"] is not obj]
    body = getattr(obj, "body", None)
    if body is not None:
      body.velocity = (0, 0)

  @staticmethod
  def _current(obj, axis):
    if hasattr(obj, "body"):
      return getattr(obj.body.position, axis)
    return getattr(obj, axis)

  def _snap(self, obj, x=None, y=None):
    # <STRANGE>#1057 final snap after a move; kinematic bodies reindex automatically
    if hasattr(obj, "body"):
      p = obj.body.position
      obj.body.position = (x if x is not None else p.x,
                           y if y is not None else p.y)
      if obj.body.body_type == pymunk.Body.STATIC:
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

  def update_light_movers(self, dt):
    # <STRANGE>#4004: ?????? ?????? ???????????????? ??????????
    if not hasattr(self, "_light_movers") or not self._light_movers:
      return
    keep = []
    for m in self._light_movers:
      m["t"] += dt
      k = min(1.0, m["t"] / m["dur"])
      m["obj"].intensity = m["start"] + (m["end"] - m["start"]) * k
      if m["t"] < m["dur"]:
        keep.append(m)
    self._light_movers = keep
    if self._light_movers:
      self._occ_cache = None

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
      if body is not None:
        # <STRANGE>#1058 set velocity so Chipmunk integrates position this step and drags contacts/joints with it
        cur_x = body.position.x
        cur_y = body.position.y
        vx = ((nx - cur_x) / dt) if (nx is not None and dt > 0) else 0.0
        vy = ((ny - cur_y) / dt) if (ny is not None and dt > 0) else 0.0
        # <STRANGE>#1153 cap so a fast tween doesn't tunnel through or slam bodies out with a huge bias impulse
        mag = (vx * vx + vy * vy) ** 0.5
        if mag > MAX_KINEMATIC_V:
          k = MAX_KINEMATIC_V / mag
          vx *= k
          vy *= k
        body.velocity = (vx, vy)
        if m["t"] >= m["dur"]:
          body.velocity = (0, 0)
          self._snap(m["obj"], nx, ny)
      else:
        self._snap(m["obj"], nx, ny)
      if m["t"] < m["dur"]:
        keep.append(m)
    self.movers = keep

  def shake(self, dur, amp, freq=0.0):
    # <STRANGE>#1195 forwarded to camera; no-op if the level has no camera yet
    if self.cam is not None:
      self.cam.shake(dur, amp, freq)

  def add_mover_light(self, light, target_intensity, dur=1.0):
    # <STRANGE>#4003: ?????????????? ?????????????????? ??????????????????????????
    if not hasattr(self, "_light_movers"):
      self._light_movers = []
    self._light_movers.append({
      "obj": light,
      "start": float(getattr(light, "intensity", 1.0)),
      "end": float(target_intensity),
      "t": 0.0,
      "dur": max(0.01, float(dur)),
    })

  def shake(self, dur, amp, freq=0.0):
    # <STRANGE>#1195 forwarded to camera; no-op if the level has no camera yet
    if self.cam is not None:
      self.cam.shake(dur, amp, freq)

  def add_mover_light(self, light, target_intensity, dur=1.0):
    # <STRANGE>#4003: ?????????????? ?????????????????? ??????????????????????????
    if not hasattr(self, "_light_movers"):
      self._light_movers = []
    self._light_movers.append({
      "obj": light,
      "start": float(getattr(light, "intensity", 1.0)),
      "end": float(target_intensity),
      "t": 0.0,
      "dur": max(0.01, float(dur)),
    })

  def update_lanterns(self, player, cam, dt):
    # <STRANGE>#1743 weak glow follows player, snapped to avoid per-frame rebuilds
    if self.player_light is not None:
      step = 2.0 / max(1e-6, cam.scale)
      px = player.body.position.x
      py = player.body.position.y
      self.player_light.pos = (
        round(px / step) * step,
        round(py / step) * step,
      )
    held_lantern = None
    hand_pos = None
    for i in range(2):
      it = player.held[i]
      if it is not None and getattr(it, "net_type", None) == "lantern":
        held_lantern = it
        hand_pos = (it.body.position.x, it.body.position.y)
        break
    mx_s, my_s = pygame.mouse.get_pos()
    mx, wy = cam.from_screen(mx_s, my_s)
    for it in self.items:
      if getattr(it, "net_type", None) != "lantern":
        continue
      lt = getattr(it, "light", None)
      if lt is None:
        continue
      # <STRANGE>#1744 toggle off: dark; held-on: follow hand aim cursor; free-on: freeze at item
      if not getattr(it, "is_on", False):
        lt.intensity = 0.0
        continue
      if it is held_lantern and hand_pos is not None:
        lt.pos = hand_pos
        dx = mx - hand_pos[0]
        dy = wy - hand_pos[1]
        if dx * dx + dy * dy > 1.0:
          lt.angle = math.atan2(dy, dx)
        lt.intensity = 0.95
      elif it.held_by is None:
        lt.pos = (it.body.position.x, it.body.position.y)
        lt.angle = it.body.angle
        lt.intensity = 0.95
      else:
        # pocketed or held by someone else: hidden
        lt.intensity = 0.0

  def update_buttons(self, dt, player=None):
    # <STRANGE>#1103 tick pop animations
    for b in self.buttons:
      b.update(dt)
    # <STRANGE>#1131 push-out only for the button this player's hand is currently grabbed on
    if player is None:
      return
    from shared.const import BODY_R, BUTTON_PUSH_FORCE
    held_buttons = [
      g[0] for g in player.grabbed
      if g is not None and getattr(g[0], "is_button", False)
    ]
    if not held_buttons:
      return
    px = player.body.position.x
    py = player.body.position.y
    for b in held_buttons:
      dx = px - b.body.position.x
      dy = py - b.body.position.y
      d2 = dx * dx + dy * dy
      R = BODY_R + b.r
      if 1e-6 < d2 < R * R:
        d = d2 ** 0.5
        pen = R - d
        nx, ny = dx / d, dy / d
        # <STRANGE>#1135 cap by outward velocity: once we're already moving out fast, stop pushing
        v_out = player.body.velocity.x * nx + player.body.velocity.y * ny
        if v_out > 200:
          continue
        f = BUTTON_PUSH_FORCE * pen * player.body.mass
        player.body.apply_force_at_local_point((nx * f, ny * f), (0, 0))

  def update_triggers(self, dt, player_pos, player_events=None):
    for t in self.triggers:
      t.update(dt, player_pos[0], player_pos[1])
    if player_events:
      for t in self.triggers:
        for ev in player_events:
          t.fire_button(ev)

  def add_text(self, msg, x, y, dur=2.0, size=32, color=(255, 255, 255)):
    # <STRANGE>#1315 world-space floating text overlay
    entry = {"msg": str(msg), "x": float(x), "y": float(y), "t": 0.0,
             "dur": max(0.01, float(dur)), "size": int(size),
             "color": tuple(color[:3])}
    self.texts.append(entry)
    return entry

  def add_toast(self, content, dur=2.0, color=(235, 225, 210), w=1200, h=40):
    # <STRANGE>#1316 bottom-center transient message; text, shape list, or draw callback
    dur = max(0.01, float(dur))
    if callable(content):
      kind = "draw"
      draw_fn = content
      shapes = None
    else:
      kind = "shapes"
      draw_fn = None
      if isinstance(content, str):
        shapes = [{"kind": "text", "msg": content, "size": 28, "color": tuple(color[:3])}]
      elif isinstance(content, (list, tuple)):
        shapes = list(content)
      else:
        shapes = [{"kind": "text", "msg": str(content), "size": 28, "color": tuple(color[:3])}]
    entry = {
      "t": 0.0,
      "dur": dur,
      "w": int(w),
      "h": int(h),
      "color": tuple(color[:3]),
      "kind": kind,
      "slot": None,
    }
    if kind == "draw":
      entry["draw"] = draw_fn
    else:
      entry["shapes"] = shapes
    self.toasts.append(entry)
    return entry

  def flash(self, dur, color=(255, 255, 255), alpha=120):
    # <STRANGE>#1317 full-screen flash overlay
    entry = {"t": 0.0, "dur": max(0.01, float(dur)),
             "color": tuple(color[:3]), "alpha": int(alpha)}
    self.flashes.append(entry)
    return entry

  def update_overlays(self, dt):
    # <STRANGE>#1318 tick overlay lifetimes; drop expired
    for lst in (self.texts, self.toasts, self.flashes):
      for e in lst:
        e["t"] += dt
      lst[:] = [e for e in lst if e["t"] < e["dur"]]

  def _draw_toast_shape(self, surf, sh, cx, cy, alpha):
    # <STRANGE>#1320 draw one primitive shape into a toast slot
    if not isinstance(sh, dict):
      return
    kind = sh.get("kind") or ("text" if "msg" in sh else "rect")
    col = tuple(sh.get("color", (235, 225, 210))[:3])
    a = int(sh.get("alpha", 255)) * alpha // 255
    if a <= 0:
      return
    rgba = (*col, a)
    px = cx + int(sh.get("x", 0))
    py = cy + int(sh.get("y", 0))
    if kind == "text":
      size = int(sh.get("size", 28))
      font = pygame.font.SysFont("consolas", size)
      tmp = font.render(str(sh.get("msg", "")), True, col)
      tmp.set_alpha(a)
      surf.blit(tmp, tmp.get_rect(center=(px, py)))
    elif kind == "rect":
      w = int(sh.get("w", 40))
      h = int(sh.get("h", 10))
      line = int(sh.get("line", 0))
      rect = pygame.Rect(px - w // 2, py - h // 2, w, h)
      pygame.draw.rect(surf, rgba, rect, line)
    elif kind == "circle":
      r = int(sh.get("r", 10))
      line = int(sh.get("line", 0))
      pygame.draw.circle(surf, rgba, (px, py), r, line)
    elif kind == "line":
      x1 = cx + int(sh.get("x1", 40))
      y1 = cy + int(sh.get("y1", 0))
      width = int(sh.get("width", 2))
      pygame.draw.line(surf, rgba, (px, py), (x1, y1), width)
    elif kind == "polygon":
      pts = [(cx + int(px2), cy + int(py2)) for px2, py2 in sh.get("points", [])]
      if len(pts) >= 3:
        line = int(sh.get("line", 0))
        pygame.draw.polygon(surf, rgba, pts, line)

  def draw_overlays(self, hud, cam):
    # <STRANGE>#1319 draw flashes -> world texts -> toasts; order is deliberate
    sw, sh = hud.get_size()
    for f in self.flashes:
      k = f["t"] / f["dur"]
      a = int(f["alpha"] * (1.0 - k))
      if a <= 0:
        continue
      hud.rect(0, 0, sw, sh, f["color"], a)
    for tx in self.texts:
      k = tx["t"] / tx["dur"]
      alpha = 255 if k < 0.7 else int(255 * (1.0 - (k - 0.7) / 1.0))
      if alpha <= 0:
        continue
      size = max(8, int(tx["size"] * cam.scale))
      sx, sy = cam.to_screen(tx["x"], tx["y"])
      sy -= int(k * 30 * cam.scale)
      hud.text(tx["msg"], sx, sy, size, tx["color"], alpha, anchor="center")
    if self.toasts:
      cx = sw // 2
      y = sh - 120
      for tst in reversed(self.toasts):
        k = tst["t"] / tst["dur"]
        alpha = 255 if k < 0.7 else int(255 * (1.0 - (k - 0.7) / 1.0))
        if alpha <= 0:
          continue
        w, h = tst["w"], tst["h"]
        slot = tst.get("slot")
        if slot is None or slot.get_size() != (w, h):
          slot = pygame.Surface((w, h), pygame.SRCALPHA)
          tst["slot"] = slot
        slot.fill((0, 0, 0, 0))
        lcx, lcy = w // 2, h // 2
        if tst["kind"] == "draw":
          try:
            tst["draw"](slot, lcx, lcy, tst["t"], tst["dur"], alpha)
          except Exception as e:
            print(f"ctx.toast draw failed: {e}")
        else:
          for sh_ in tst["shapes"]:
            self._draw_toast_shape(slot, sh_, lcx, lcy, alpha)
        hud.surface(slot, cx - w // 2, y - h // 2, alpha=255, anchor="topleft")
        y -= h

  def open_note_ui(self, title, text):
    self.note_ui = {"title": title, "text": text, "t": 0.0}
    if self.cam:
      self.cam.shake(0.1, 2.0)

  def close_note_ui(self):
    if hasattr(self, "note_ui"):
      self.note_ui = None

  def update_notes(self, dt, events):
    if not hasattr(self, "note_ui") or not self.note_ui:
      return
    self.note_ui["t"] += dt

  def draw_notes(self, hud, cam):
    if not hasattr(self, "note_ui") or not self.note_ui:
      return
    sw, sh = hud.get_size()
    
    if not hasattr(self, "_note_ui_surf") or self._note_ui_surf.get_size() != (sw, sh):
        self._note_ui_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
    surf = self._note_ui_surf
    surf.fill((0, 0, 0, 0))
    
    # ????????????????????
    dim_alpha = int(180 * min(1.0, self.note_ui["t"] * 4))
    surf.fill((0, 0, 0, dim_alpha))
    
    # ???????????????????? ????????????????????
    box_w = int(sw * 0.32)
    box_h = int(box_w * 1.55)
    
    if box_h > sh * 0.85:
        box_h = int(sh * 0.85)
        box_w = int(box_h / 1.55)
    
    box_w = max(400, box_w)
    box_h = max(620, box_h)
    
    if box_w > sw * 0.9:
        box_w = int(sw * 0.9)
        box_h = int(box_w * 1.55)
    if box_h > sh * 0.95:
        box_h = int(sh * 0.95)
        box_w = int(box_h / 1.55)
        
    cx, cy = sw // 2, sh // 2
    box_rect = pygame.Rect(cx - box_w // 2, cy - box_h // 2, box_w, box_h)
    
    pygame.draw.rect(surf, (240, 235, 220), box_rect)
    pygame.draw.rect(surf, (100, 100, 100), box_rect, 2)
    
    font_title = pygame.font.SysFont("consolas", 32, bold=True)
    ts = font_title.render(self.note_ui["title"], True, (50, 50, 50))
    surf.blit(ts, ts.get_rect(center=(cx, box_rect.y + 60)))
    
    font = pygame.font.SysFont("consolas", 24)
    words = self.note_ui["text"].split()
    lines = []
    current_line = []
    max_line_w = box_w - 80
    for w in words:
      test_line = " ".join(current_line + [w])
      if font.size(test_line)[0] < max_line_w:
        current_line.append(w)
      else:
        if current_line:
          lines.append(" ".join(current_line))
        current_line = [w]
    if current_line:
      lines.append(" ".join(current_line))
      
    line_h = 34
    y = box_rect.y + 130
    max_y = box_rect.y + box_h - 40
    for line in lines:
      if y + line_h > max_y:
        break
      ts = font.render(line, True, (30, 30, 30))
      surf.blit(ts, ts.get_rect(center=(cx, y)))
      y += line_h
      
    hud.surface(surf, 0, 0, anchor="topleft")

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
    return self.backgrounds + self.platforms + self.pegs + self.buttons + free_items
