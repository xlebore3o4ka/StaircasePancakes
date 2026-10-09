"""Undo/redo, clipboard, снапшоты сцены."""
from .const import (
  UNDO_LIMIT, PASTE_OFFSET,
  DEFAULT_ITEM_TYPE, PLAT_DEFAULT_W, PLAT_DEFAULT_H,
  PLAT_FILL, PLAT_EDGE, BG_DEFAULT_COLOR,
)
from .objects import (
  EditorPeg, EditorPlatform, EditorBackground, EditorItem, EditorSpawner,
)


class UndoMixin:
  # ---------- serialize one object ----------
  def _obj_to_state(self, o):
    if isinstance(o, EditorPeg):
      return {"t": "peg", "x": o.x, "y": o.y,
              "locked": o.locked, "layer": o.layer}
    if isinstance(o, EditorPlatform):
      return {"t": "plat", "x": o.x, "y": o.y, "w": o.w, "h": o.h,
              "fill": tuple(o.fill), "edge": tuple(o.edge),
              "locked": o.locked, "layer": o.layer}
    if isinstance(o, EditorBackground):
      return {"t": "bg", "x": o.x, "y": o.y, "w": o.w, "h": o.h,
              "fill": tuple(o.fill), "locked": o.locked, "layer": o.layer}
    if isinstance(o, EditorItem):
      return {"t": "item", "x": o.x, "y": o.y, "item_type": o.item_type,
              "contents": [dict(e) for e in o.contents],
              "locked": o.locked, "layer": o.layer}
    if isinstance(o, EditorSpawner):
      entries = [{"type": e.get("type", "nothing"),
                  "count": int(e.get("count", 1))} for e in o.items]
      return {"t": "spawner", "x": o.x, "y": o.y, "entries": entries,
              "locked": o.locked, "layer": o.layer}
    return None

  def _make_from_state(self, s):
    t = s["t"]
    if t == "peg":
      o = EditorPeg(s["x"], s["y"])
    elif t == "plat":
      o = EditorPlatform(s["x"], s["y"], s["w"], s["h"])
      o.fill = tuple(s["fill"]); o.edge = tuple(s["edge"])
    elif t == "bg":
      o = EditorBackground(s["x"], s["y"], s["w"], s["h"])
      o.fill = tuple(s["fill"])
    elif t == "item":
      o = EditorItem(s["x"], s["y"], s.get("item_type", DEFAULT_ITEM_TYPE),
                     s.get("contents"))
    elif t == "spawner":
      o = EditorSpawner(s["x"], s["y"])
      o.items = [dict(e) for e in s.get("entries", [])]
    else:
      return None
    o.locked = s.get("locked", False)
    o.layer = s.get("layer", None)
    return o

  # ---------- snapshots ----------
  def _snapshot(self):
    return [self._obj_to_state(o) for o in self.objects]

  def _restore(self, snap):
    self.objects = [self._make_from_state(s) for s in snap]
    self._clear_selection()
    self._mark_scene_dirty()

  def begin_undo(self):
    self._undo_before = self._snapshot()

  def commit_undo(self):
    if self._undo_before is None:
      return
    if self._snapshot() != self._undo_before:
      self.undo_stack.append(self._undo_before)
      if len(self.undo_stack) > UNDO_LIMIT:
        self.undo_stack.pop(0)
      self.redo_stack.clear()
    self._undo_before = None

  def _push_undo_now(self, before):
    if self._snapshot() != before:
      self.undo_stack.append(before)
      if len(self.undo_stack) > UNDO_LIMIT:
        self.undo_stack.pop(0)
      self.redo_stack.clear()

  def _cancel_interaction(self):
    self.drag = None
    self.erasing = False
    self._erase_prev = None
    self.zone_start = None
    self.zone_now = None
    self.select_start = None
    self.select_now = None
    self._move_data = []
    self._move_start = None
    self._move_anchor = None
    self._resize_data = []
    self.snap_guides_x = []
    self.snap_guides_y = []
    self._undo_before = None

  def undo(self):
    if not self.undo_stack:
      return
    self.redo_stack.append(self._snapshot())
    snap = self.undo_stack.pop()
    self._restore(snap)
    self._cancel_interaction()

  def redo(self):
    if not self.redo_stack:
      return
    self.undo_stack.append(self._snapshot())
    snap = self.redo_stack.pop()
    self._restore(snap)
    self._cancel_interaction()

  # ---------- clipboard ----------
  def copy_selected(self):
    if not self.selection:
      return
    self.clipboard = [self._obj_to_state(o) for o in self.selection]

  def paste(self):
    if not self.clipboard:
      return
    before = self._snapshot()
    new = []
    for s in self.clipboard:
      s2 = dict(s)
      s2["x"] = s2["x"] + PASTE_OFFSET
      s2["y"] = s2["y"] - PASTE_OFFSET
      o = self._make_from_state(s2)
      if o is not None:
        new.append(o)
    self.objects.extend(new)
    self._set_selection(new)
    self._push_undo_now(before)
    self._mark_scene_dirty()

  def duplicate_selected(self):
    if not self.selection:
      return
    before = self._snapshot()
    new = []
    for obj in self.selection:
      s = self._obj_to_state(obj)
      s["x"] += PASTE_OFFSET
      s["y"] -= PASTE_OFFSET
      o = self._make_from_state(s)
      if o is not None:
        new.append(o)
    self.objects.extend(new)
    self._set_selection(new)
    self._push_undo_now(before)
    self._mark_scene_dirty()

  def delete_selected(self):
    if not self.selection:
      return
    targets = [o for o in self.selection if not o.locked and o in self.objects]
    if not targets:
      return
    before = self._snapshot()
    for o in targets:
      self.objects.remove(o)
    self._clear_selection()
    self._push_undo_now(before)
    self._mark_scene_dirty()

  def _delete_objects(self, objs):
    for o in list(objs):
      if not o.locked and o in self.objects:
        self.objects.remove(o)
    self._clear_selection()
    self._mark_scene_dirty()

  def _flip_objects(self, objs, horizontal):
    objs = [o for o in objs if not o.locked]
    if not objs:
      return
    if horizontal:
      xs = [o.x for o in objs]
      c = (min(xs) + max(xs)) / 2
      for o in objs:
        o.x = 2 * c - o.x
    else:
      ys = [o.y for o in objs]
      c = (min(ys) + max(ys)) / 2
      for o in objs:
        o.y = 2 * c - o.y

  # ---------- selection helpers ----------
  def _set_selection(self, objs):
    self.selection = [o for o in objs if not o.locked]
    self.selected = self.selection[-1] if self.selection else None
    self._sync_inspector()

  def _add_to_selection(self, objs):
    for o in objs:
      if not o.locked and o not in self.selection:
        self.selection.append(o)
    self.selected = self.selection[-1] if self.selection else None
    self._sync_inspector()

  def _toggle_selection(self, obj):
    if obj.locked:
      return
    if obj in self.selection:
      self.selection.remove(obj)
    else:
      self.selection.append(obj)
    self.selected = self.selection[-1] if self.selection else None
    self._sync_inspector()

  def _select_all(self):
    # <STRANGE>#404: ???????????????? ?????? ?????????????????????????????????? ?????????????? (?????? ???????????? "All")
    self._set_selection(list(self.objects))

  def _clear_selection(self):
    self.selection = []
    self.selected = None
    self._sync_inspector()

  def _sync_inspector(self):
    if isinstance(self.selected, EditorSpawner):
      self.push_inspector(self.selected)
    elif isinstance(self.selected, EditorItem) and self.selected.item_type == "cube":
      self.push_inspector(self.selected)
    else:
      self._close_all_inspectors()