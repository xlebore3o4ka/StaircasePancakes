"""Точка сборки класса Editor из миксинов."""
import json
import tkinter as tk
from tkinter import filedialog

from .const import (
  PLAT_DEFAULT_W, PLAT_DEFAULT_H, PLAT_FILL, PLAT_EDGE,
  BG_DEFAULT_COLOR, DEFAULT_ITEM_TYPE,
  ARTIFACT_TYPES,
  DEFAULT_ARTIFACT_TYPE,
  TRIGGER_DEFAULT_W, TRIGGER_DEFAULT_H,
)
from .objects import (
  EditorPeg, EditorPlatform, EditorBackground, EditorItem, EditorSpawner,
  EditorArtifact, EditorTrigger, EditorButton, EditorAnchor, EditorLight,
  EditorLabel,
)
from . import tar_io
from .editor_core import CoreMixin, _game_version_read
from .editor_undo import UndoMixin
from .editor_events import EventsMixin
from .editor_drag import DragMixin
from .editor_render import RenderMixin


class Editor(CoreMixin, UndoMixin, EventsMixin, DragMixin, RenderMixin):
  # ---------- save / load ----------
  def save(self):
    root = tk.Tk()
    root.withdraw()
    path = filedialog.asksaveasfilename(
      defaultextension=".json",
      initialdir="levels",
      filetypes=[("Level", "*.json *.tar"), ("JSON", "*.json"), ("TAR", "*.tar")],
    )
    root.destroy()
    try:
      self._flush_pygame_events()
    except Exception:
      pass
    if not path:
      return
    pegs = [o.to_json() for o in self.objects if isinstance(o, EditorPeg)]
    buttons = [o.to_json() for o in self.objects if isinstance(o, EditorButton)]
    platforms = [o.to_json() for o in self.objects if isinstance(o, EditorPlatform)]
    backgrounds = [o.to_json() for o in self.objects if isinstance(o, EditorBackground)]
    items = [o.to_json() for o in self.objects if isinstance(o, EditorItem)]
    spawners = [o.to_json() for o in self.objects if isinstance(o, EditorSpawner)]
    triggers = [o.to_json() for o in self.objects if isinstance(o, EditorTrigger)]
    # bag ??? ?????????????????? ????????????, ???????? ????????
    bag = None
    lantern = None
    for o in self.objects:
      if isinstance(o, EditorArtifact):
        if getattr(o, "artifact_type", "bag") == "lantern":
          lantern = o.to_json()
        else:
          bag = o.to_json()
    lights = self._lights_for_output()
    out = {"version": str(_game_version_read())}
    if getattr(self, "lighting", None) is not None or lights:
      cfg = getattr(self, "lighting", None) or {
        "ambient": list(getattr(self, "lighting_ambient", (0, 0, 0))),
        "gain": float(getattr(self, "lighting_gain", 1.0)),
      }
      out["lighting"] = dict(cfg)
      out["lights"] = lights
    out.update({
      "pegs": pegs,
      "platforms": platforms,
      "backgrounds": backgrounds,
      "items": items,
      "itemSpawners": spawners,
      "triggers": triggers,
      "buttons": buttons,
    })
    if bag is not None:
      out["bag"] = bag
    if lantern is not None:
      out["lantern"] = lantern
    if str(path).lower().endswith(".tar"):
      extra = dict(getattr(self, "embedded_files", None) or {})
      try:
        anchors = [o.to_json() for o in self.objects
                   if isinstance(o, EditorAnchor)]
        labels = [o.to_json() for o in self.objects
                  if isinstance(o, EditorLabel)]
        meta = {"version": 1, "anchors": anchors}
        if labels:
          meta["labels"] = labels
        try:
          pt = list(getattr(self, "color_templates", {}).get("platform", []))
          bt = list(getattr(self, "color_templates", {}).get("background", []))
          if pt:
            meta["platform_color_templates"] = pt
          if bt:
            meta["background_color_templates"] = bt
          lt = list(getattr(self, "color_templates", {}).get("light", []))
          if lt:
            meta["light_color_templates"] = lt
        except Exception:
          pass
        extra["editor.json"] = json.dumps(meta, indent=2)
      except Exception:
        pass
      tar_io.save_level(path, out, extra_files=extra)
    else:
      with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2)
      has_anchors = any(isinstance(o, EditorAnchor) for o in self.objects)
      if getattr(self, "embedded_files", None) or has_anchors:
        try:
          from .messages import WARN
          self.messages.toast_only(WARN,
              "Anchors/scripts are only stored in .tar (not in .json)", 4.0)
        except Exception:
          pass
    try:
      self._refresh_version_warning()
    except Exception:
      pass
    try:
      from .messages import INFO
      self.messages.toast_only(INFO, "Saved (v%s): %s" % (str(_game_version_read()), path), 3.0)
    except Exception:
      pass

  def load(self):
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(
      initialdir="levels",
      filetypes=[("Level", "*.json *.tar"), ("JSON", "*.json"), ("TAR", "*.tar")],
    )
    root.destroy()
    try:
      self._flush_pygame_events()
    except Exception:
      pass
    if not path:
      return
    try:
      _editor_meta = None
      if str(path).lower().endswith(".tar"):
        data = tar_io.load_level(path)
        try:
          _files = tar_io.load_files(path)
        except Exception:
          _files = {}
        try:
          _meta_bytes = _files.pop("editor.json", None)
          if _meta_bytes:
            _editor_meta = json.loads(_meta_bytes.decode("utf-8"))
        except Exception:
          _editor_meta = None
        self.embedded_files = _files
      else:
        with open(path, "r", encoding="utf-8") as f:
          data = json.load(f)
        self.embedded_files = {}
    except Exception as _ex:
      # <STRANGE>#1070: never crash on a broken file; show an error toast.
      try:
        from .messages import ERROR
        self.messages.toast_only(
            ERROR, "Load failed: " + str(_ex)[:80], 5.0)
      except Exception:
        pass
      return
    before = self._snapshot()
    _v = data.get("version")
    self.loaded_version = _v.strip() if isinstance(_v, str) and _v.strip() else None
    self.objects = []
    for p in data.get("pegs", []):
      # <STRANGE>#700: ?????? ?????????? ???????? [x, y], [x, y, locked] ?????? dict
      if isinstance(p, dict):
        obj = EditorPeg(p["x"], p["y"])
        obj.locked = bool(p.get("locked", False))
        obj.id = str(p.get("id", ""))
        if "layer" in p:
          obj.layer = int(p["layer"])
      else:
        obj = EditorPeg(p[0], p[1])
        if len(p) > 2:
          obj.locked = bool(p[2])
      self.objects.append(obj)
    for bt in data.get("buttons", []):
      b = EditorButton(bt["x"], bt["y"])
      b.id = str(bt.get("id", ""))
      b.locked = bool(bt.get("locked", False))
      if "layer" in bt:
        b.layer = int(bt["layer"])
      self.objects.append(b)
    for pd in data.get("platforms", []):
      obj = EditorPlatform(pd["x"], pd["y"],
                           pd.get("w", PLAT_DEFAULT_W),
                           pd.get("h", PLAT_DEFAULT_H))
      obj.fill = tuple(pd.get("fill", PLAT_FILL))
      obj.edge = tuple(pd.get("edge", PLAT_EDGE))
      obj.locked = bool(pd.get("locked", False))
      obj.id = str(pd.get("id", ""))
      if "layer" in pd:
        obj.layer = int(pd["layer"])
      # <STRANGE>#1112: restore polygon/points for platforms
      if pd.get("polygon"):
        obj.polygon = True
        obj.points = [[int(p[0]), int(p[1])] for p in pd.get("points", [])]
      self.objects.append(obj)
    for bd in data.get("backgrounds", []):
      obj = EditorBackground(bd["x"], bd["y"],
                             bd.get("w", PLAT_DEFAULT_W),
                             bd.get("h", PLAT_DEFAULT_H))
      obj.fill = tuple(bd.get("color", BG_DEFAULT_COLOR))
      obj.locked = bool(bd.get("locked", False))
      obj.id = str(bd.get("id", ""))
      if "layer" in bd:
        obj.layer = int(bd["layer"])
      if bd.get("polygon"):
        obj.polygon = True
        obj.points = [[int(p[0]), int(p[1])] for p in bd.get("points", [])]
      self.objects.append(obj)
    for it in data.get("items", []):
      obj = EditorItem(it["x"], it["y"], it.get("type", DEFAULT_ITEM_TYPE),
                       it.get("contents"))
      obj.locked = bool(it.get("locked", False))
      obj.id = str(it.get("id", ""))
      if "layer" in it:
        obj.layer = int(it["layer"])
      self.objects.append(obj)
    for sp in data.get("itemSpawners", []):
      obj = EditorSpawner(sp["x"], sp["y"])
      obj.items = [{"type": e.get("type", "nothing"),
                    "count": int(e.get("count", 1)),
                    "id": str(e.get("id", ""))}
                   for e in sp.get("items", [])]
      obj.locked = bool(sp.get("locked", False))
      if "layer" in sp:
        obj.layer = int(sp["layer"])
      self.objects.append(obj)
    for tg in data.get("triggers", []):
      obj = EditorTrigger(tg["x"], tg["y"],
                          tg.get("w", TRIGGER_DEFAULT_W),
                          tg.get("h", TRIGGER_DEFAULT_H))
      obj.id = tg.get("id", "")
      obj.script = tg.get("script", "")
      obj.locked = bool(tg.get("locked", False))
      if "layer" in tg:
        obj.layer = int(tg["layer"])
      self.objects.append(obj)
    # bag / lantern artifacts
    bag_data = data.get("bag")
    if bag_data:
      if isinstance(bag_data, dict):
        b = EditorArtifact(bag_data.get("x", 0), bag_data.get("y", 0), "bag")
        b.id = str(bag_data.get("id", ""))
      else:
        b = EditorArtifact(bag_data[0], bag_data[1], "bag")
      self.objects.append(b)
    lantern_data = data.get("lantern")
    if lantern_data:
      if isinstance(lantern_data, dict):
        b = EditorArtifact(lantern_data.get("x", 0), lantern_data.get("y", 0), "lantern")
        b.id = str(lantern_data.get("id", ""))
      else:
        b = EditorArtifact(lantern_data[0], lantern_data[1], "lantern")
      self.objects.append(b)
    # <STRANGE>#1901: extract sun from lights[] into passive config
    _raw_lights = list(data.get("lights", []))
    _sun_entry = None
    _non_sun_lights = []
    for _ld in _raw_lights:
      if isinstance(_ld, dict) and _ld.get("type") == "sun":
        _sun_entry = _ld
      else:
        _non_sun_lights.append(_ld)
    if _sun_entry is not None:
      try:
        self.sun_enabled = True
        c = _sun_entry.get("color", [180, 200, 240])
        self.sun_color = (int(c[0]), int(c[1]), int(c[2]))
        self.sun_intensity = float(_sun_entry.get("intensity", 0.45))
        d = _sun_entry.get("direction", [0.6, 1.0])
        self.sun_direction = (float(d[0]), float(d[1]))
        self.sun_shadow_length = float(_sun_entry.get("shadow_length", 2000.0))
        self.sun_gradient_length = float(_sun_entry.get("gradient_length", 60.0))
      except Exception:
        self.sun_enabled = False
    else:
      self.sun_enabled = False
    # <STRANGE>#1511: lights array + lighting block
    for ld in _non_sun_lights:
      try:
        kind = ld.get("type", "lamp")
        L = EditorLight(int(ld.get("x", 0)), int(ld.get("y", 0)), kind)
        if "color" in ld:
          L.color = tuple(int(c) for c in ld["color"][:3])
        if "intensity" in ld:
          L.intensity = float(ld["intensity"])
        L.id = str(ld.get("id", ""))
        L.locked = bool(ld.get("locked", False))
        if "layer" in ld:
          L.layer = int(ld["layer"])
        if kind == "lamp" and "radius" in ld:
          L.radius = float(ld["radius"])
        if kind == "spot":
          if "angle" in ld: L.angle = float(ld["angle"])
          if "length" in ld: L.length = float(ld["length"])
          if "cone" in ld: L.cone = float(ld["cone"])
        if kind == "sun" and "direction" in ld:
          try:
            dirv = ld["direction"]
            if isinstance(dirv, (list, tuple)) and len(dirv) >= 2:
              L.direction = [float(dirv[0]), float(dirv[1])]
          except Exception:
            pass
        self.objects.append(L)
      except Exception:
        pass
    _lg = data.get("lighting")
    if isinstance(_lg, dict):
      self.lighting = {
        "ambient": list(_lg.get("ambient", [0, 0, 0])),
        "gain": float(_lg.get("gain", 1.0)),
      }
      self.lighting_ambient = tuple(self.lighting["ambient"])
      self.lighting_gain = self.lighting["gain"]
    else:
      self.lighting = None
    # <STRANGE>#1411: anchors come from editor.json (tar only)
    if _editor_meta and isinstance(_editor_meta, dict):
      for ad in _editor_meta.get("anchors", []):
        try:
          a = EditorAnchor(int(ad["x"]), int(ad["y"]),
                           ad.get("variant", "A"))
          a.binding = str(ad.get("binding", ""))
          a.name = str(ad.get("name", ""))
          a.weight = int(ad.get("weight", 1))
          a.max_limit = int(ad.get("max_limit", 1))
          a.locked = bool(ad.get("locked", False))
          if "layer" in ad:
            a.layer = int(ad["layer"])
          self.objects.append(a)
        except Exception:
          pass
    # <STRANGE>#1902: restore labels from editor.json
    if _editor_meta and isinstance(_editor_meta, dict):
      for ldata in _editor_meta.get("labels", []):
        try:
          lb = EditorLabel(ldata.get("x", 0), ldata.get("y", 0),
                           ldata.get("text", "label"))
          lb.target_trigger_id = str(ldata.get("target_trigger_id", ""))
          lb.chips = [{"kind": c.get("kind", ""),
                       "params": dict(c.get("params", {}))}
                      for c in ldata.get("chips", [])]
          lb.locked = bool(ldata.get("locked", False))
          if "layer" in ldata:
            lb.layer = int(ldata["layer"])
          self.objects.append(lb)
        except Exception:
          pass
    # <STRANGE>#1503: restore color templates from editor.json
    if _editor_meta and isinstance(_editor_meta, dict):
      try:
        pt = _editor_meta.get("platform_color_templates")
        if isinstance(pt, list):
          self.color_templates["platform"] = list(pt)
        bt = _editor_meta.get("background_color_templates")
        if isinstance(bt, list):
          self.color_templates["background"] = list(bt)
        lt = _editor_meta.get("light_color_templates")
        if isinstance(lt, list):
          self.color_templates["light"] = list(lt)
      except Exception:
        pass
    self._clear_selection()
    self._mark_scene_dirty()
    self._push_undo_now(before)
    try:
      from .messages import INFO
      _cur_v = str(_game_version_read())
      _fv = self.loaded_version
      if _fv and _fv != _cur_v:
        self.messages.toast_only(INFO, "Loaded: %s -> %s" % (_fv, _cur_v), 3.0)
      else:
        self.messages.toast_only(INFO, "Loaded (v%s): %s" % (_cur_v, path), 3.0)
    except Exception:
      pass
