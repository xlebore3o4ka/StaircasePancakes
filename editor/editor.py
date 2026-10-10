"""Точка сборки класса Editor из миксинов."""
import json
import tkinter as tk
from tkinter import filedialog

from .const import (
  PLAT_DEFAULT_W, PLAT_DEFAULT_H, PLAT_FILL, PLAT_EDGE,
  BG_DEFAULT_COLOR, DEFAULT_ITEM_TYPE,
)
from .objects import (
  EditorPeg, EditorPlatform, EditorBackground, EditorItem, EditorSpawner,
)
from .editor_core import CoreMixin
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
      filetypes=[("JSON", "*.json")],
    )
    root.destroy()
    if not path:
      return
    pegs = [o.to_json() for o in self.objects if isinstance(o, EditorPeg)]
    platforms = [o.to_json() for o in self.objects if isinstance(o, EditorPlatform)]
    backgrounds = [o.to_json() for o in self.objects if isinstance(o, EditorBackground)]
    items = [o.to_json() for o in self.objects if isinstance(o, EditorItem)]
    spawners = [o.to_json() for o in self.objects if isinstance(o, EditorSpawner)]
    with open(path, "w") as f:
      json.dump({
        "pegs": pegs,
        "platforms": platforms,
        "backgrounds": backgrounds,
        "items": items,
        "itemSpawners": spawners,
      }, f, indent=2)

  def load(self):
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(
      initialdir="levels",
      filetypes=[("JSON", "*.json")],
    )
    root.destroy()
    if not path:
      return
    data = json.load(open(path))
    before = self._snapshot()
    self.objects = []
    for p in data.get("pegs", []):
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
      if "layer" in pd:
        obj.layer = int(pd["layer"])
      self.objects.append(obj)
    for bd in data.get("backgrounds", []):
      obj = EditorBackground(bd["x"], bd["y"],
                             bd.get("w", PLAT_DEFAULT_W),
                             bd.get("h", PLAT_DEFAULT_H))
      obj.fill = tuple(bd.get("color", BG_DEFAULT_COLOR))
      obj.locked = bool(bd.get("locked", False))
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
      if "layer" in it:
        obj.layer = int(it["layer"])
      self.objects.append(obj)
    for sp in data.get("itemSpawners", []):
      obj = EditorSpawner(sp["x"], sp["y"])
      obj.items = [{"type": e.get("type", "nothing"),
                    "count": int(e.get("count", 1))}
                   for e in sp.get("items", [])]
      obj.locked = bool(sp.get("locked", False))
      if "layer" in sp:
        obj.layer = int(sp["layer"])
      self.objects.append(obj)
    self._clear_selection()
    self._mark_scene_dirty()
    self._push_undo_now(before)