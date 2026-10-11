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
  EditorArtifact, EditorTrigger,
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
    if not path:
      return
    pegs = [o.to_json() for o in self.objects if isinstance(o, EditorPeg)]
    platforms = [o.to_json() for o in self.objects if isinstance(o, EditorPlatform)]
    backgrounds = [o.to_json() for o in self.objects if isinstance(o, EditorBackground)]
    items = [o.to_json() for o in self.objects if isinstance(o, EditorItem)]
    spawners = [o.to_json() for o in self.objects if isinstance(o, EditorSpawner)]
    triggers = [o.to_json() for o in self.objects if isinstance(o, EditorTrigger)]
    # bag ??? ?????????????????? ????????????, ???????? ????????
    bag = None
    for o in self.objects:
      if isinstance(o, EditorArtifact):
        bag = o.to_json()
        break
    out = {"version": str(_game_version_read())}
    out.update({
      "pegs": pegs,
      "platforms": platforms,
      "backgrounds": backgrounds,
      "items": items,
      "itemSpawners": spawners,
      "triggers": triggers,
    })
    if bag is not None:
      out["bag"] = bag
    if str(path).lower().endswith(".tar"):
      tar_io.save_level(path, out, extra_files=getattr(self, "embedded_files", None))
    else:
      with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2)
      if getattr(self, "embedded_files", None):
        try:
          from .messages import WARN
          self.messages.toast_only(WARN,
              "Embedded scripts only saved in .tar (not in .json)", 4.0)
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
    if not path:
      return
    try:
      if str(path).lower().endswith(".tar"):
        data = tar_io.load_level(path)
        try:
          self.embedded_files = tar_io.load_files(path)
        except Exception:
          self.embedded_files = {}
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
    # bag ??? ??????????????????
    bag_data = data.get("bag")
    if bag_data:
      if isinstance(bag_data, dict):
        b = EditorArtifact(bag_data.get("x", 0), bag_data.get("y", 0))
        b.id = str(bag_data.get("id", ""))
      else:
        b = EditorArtifact(bag_data[0], bag_data[1])
      self.objects.append(b)
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
