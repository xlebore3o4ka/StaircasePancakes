"""Undo/redo, clipboard, снапшоты сцены."""
from .const import (
  UNDO_LIMIT, PASTE_OFFSET,
  DEFAULT_ITEM_TYPE, PLAT_DEFAULT_W, PLAT_DEFAULT_H,
  PLAT_FILL, PLAT_EDGE, BG_DEFAULT_COLOR,
  DEFAULT_ARTIFACT_TYPE,
)
from .objects import (
  EditorPeg, EditorPlatform, EditorBackground, EditorItem, EditorSpawner,
  EditorArtifact, EditorTrigger, EditorButton, EditorAnchor,
  EditorLight, EditorLabel, EditorNote,
)


class UndoMixin:
  # ---------- serialize one object ----------
  def _obj_to_state(self, o):
    if isinstance(o, EditorPeg):
      return {"t": "peg", "x": o.x, "y": o.y,
              "id": getattr(o, "id", ""),
              "locked": o.locked, "layer": o.layer}
    if isinstance(o, EditorButton):
      return {"t": "button", "x": o.x, "y": o.y,
              "id": getattr(o, "id", ""),
              "locked": o.locked, "layer": o.layer}
    if isinstance(o, EditorPlatform):
      return {"t": "plat", "x": o.x, "y": o.y, "w": o.w, "h": o.h,
              "id": getattr(o, "id", ""),
              "fill": tuple(o.fill), "edge": tuple(o.edge),
              "locked": o.locked, "layer": o.layer,
              "polygon": bool(getattr(o, "polygon", False)),
              "points": [list(p) for p in getattr(o, "points", [])],
              "absorption": float(getattr(o, "absorption", 0.5))}
    if isinstance(o, EditorBackground):
      return {"t": "bg", "x": o.x, "y": o.y, "w": o.w, "h": o.h,
              "id": getattr(o, "id", ""),
              "fill": tuple(o.fill), "locked": o.locked, "layer": o.layer,
                                          "polygon": bool(getattr(o, "polygon", False)),
              "points": [list(p) for p in getattr(o, "points", [])]}
    if isinstance(o, EditorItem):
      return {"t": "item", "x": o.x, "y": o.y, "item_type": o.item_type,
              "id": getattr(o, "id", ""),
              "contents": [dict(e) for e in o.contents],
              "locked": o.locked, "layer": o.layer}
    if isinstance(o, EditorSpawner):
      entries = [{"type": e.get("type", "nothing"),
                  "count": int(e.get("count", 1))} for e in o.items]
      return {"t": "spawner", "x": o.x, "y": o.y, "entries": entries,
              "locked": o.locked, "layer": o.layer}
    if isinstance(o, EditorArtifact):
      return {"t": "bag", "x": o.x, "y": o.y,
              "id": getattr(o, "id", ""),
              "locked": o.locked, "layer": o.layer}
    if isinstance(o, EditorTrigger):
      return {"t": "trigger", "x": o.x, "y": o.y,
              "w": o.w, "h": o.h,
              "id": getattr(o, "id", ""),
              "script": getattr(o, "script", ""),
              "locked": o.locked, "layer": o.layer}
    if isinstance(o, EditorLight):
      d = {"t": "light", "x": o.x, "y": o.y, "kind": getattr(o, "kind", "lamp"),
           "color": tuple(getattr(o, "color", (255, 200, 120))),
           "intensity": float(getattr(o, "intensity", 1.0)),
           "id": getattr(o, "id", ""),
           "locked": o.locked, "layer": o.layer}
      if getattr(o, "kind", "lamp") == "lamp":
        d["radius"] = float(getattr(o, "radius", 300.0))
      else:
        d["angle"] = float(getattr(o, "angle", 4.712))
        d["length"] = float(getattr(o, "length", 600.0))
        d["cone"] = float(getattr(o, "cone", 0.8))
      return d
    if isinstance(o, EditorNote):
      return {"t": "note", "x": o.x, "y": o.y,
              "title": o.title, "text": o.text,
              "locked": o.locked, "layer": o.layer}
    if isinstance(o, EditorLabel):
      return {"t": "label", "x": o.x, "y": o.y,
              "text": str(getattr(o, "text", "")),
              "target_trigger_id": str(getattr(o, "target_trigger_id", "")),
              "chips": [{"kind": c.get("kind", ""),
                          "params": dict(c.get("params", {}))}
                         for c in getattr(o, "chips", [])],
              "locked": o.locked, "layer": o.layer}
    if isinstance(o, EditorAnchor):
      return {"t": "anchor", "x": o.x, "y": o.y,
              "variant": o.variant,
              "binding": getattr(o, "binding", ""),
              "name": getattr(o, "name", ""),
              "weight": int(getattr(o, "weight", 1)),
              "max_limit": int(getattr(o, "max_limit", 1)),
              "locked": o.locked, "layer": o.layer}
    return None

  def _make_from_state(self, s):
    t = s["t"]
    if t == "peg":
      o = EditorPeg(s["x"], s["y"])
    elif t == "button":
      o = EditorButton(s["x"], s["y"])
    elif t == "plat":
      o = EditorPlatform(s["x"], s["y"], s["w"], s["h"])
      o.fill = tuple(s["fill"]); o.edge = tuple(s["edge"])
      o.polygon = bool(s.get("polygon", False))
      o.points = [list(p) for p in s.get("points", [])]
      o.absorption = float(s.get("absorption", 0.5))
    elif t == "bg":
      o = EditorBackground(s["x"], s["y"], s["w"], s["h"])
      o.fill = tuple(s["fill"])
      o.polygon = bool(s.get("polygon", False))
      o.points = [list(p) for p in s.get("points", [])]
    elif t == "item":
      o = EditorItem(s["x"], s["y"], s.get("item_type", DEFAULT_ITEM_TYPE),
                     s.get("contents"))
    elif t == "spawner":
      o = EditorSpawner(s["x"], s["y"])
      o.items = [dict(e) for e in s.get("entries", [])]
    elif t == "trigger":
      o = EditorTrigger(s["x"], s["y"], s.get("w"), s.get("h"))
      o.id = s.get("id", "")
      o.script = s.get("script", "")
    elif t == "light":
      o = EditorLight(s["x"], s["y"], s.get("kind", "lamp"))
      o.color = tuple(s.get("color", (255, 200, 120)))
      o.intensity = float(s.get("intensity", 1.0))
      o.id = s.get("id", "")
      if s.get("kind", "lamp") == "lamp":
        o.radius = float(s.get("radius", 300.0))
      else:
        o.angle = float(s.get("angle", 4.712))
        o.length = float(s.get("length", 600.0))
        o.cone = float(s.get("cone", 0.8))
    elif t == "note":
      o = EditorNote(s["x"], s["y"], s.get("text", ""), s.get("title", "??????????????"))
    elif t == "label":
      o = EditorLabel(s["x"], s["y"], s.get("text", ""))
      o.target_trigger_id = str(s.get("target_trigger_id", ""))
      o.chips = [{"kind": c.get("kind", ""),
                  "params": dict(c.get("params", {}))}
                 for c in s.get("chips", [])]
    elif t == "anchor":
      o = EditorAnchor(s["x"], s["y"], s.get("variant", "A"))
      o.binding = s.get("binding", "")
      o.name = s.get("name", "")
      o.weight = int(s.get("weight", 1))
      o.max_limit = int(s.get("max_limit", 1))
    elif t == "bag":
      o = EditorArtifact(s["x"], s["y"])
    else:
      return None
    o.locked = s.get("locked", False)
    o.layer = s.get("layer", None)
    if hasattr(o, "id"):
      o.id = s.get("id", "")
    return o

  # ---------- snapshots ----------
  def _snapshot(self):
    # <STRANGE>#1131: filter None entries; they poison the undo stack
    out = []
    for o in self.objects:
      if o is None:
        continue
      st = self._obj_to_state(o)
      if st is not None:
        out.append(st)
    return out

  def _restore(self, snap):
    objs = []
    for s in snap:
      if s is None:
        continue
      o = self._make_from_state(s)
      if o is not None:
        objs.append(o)
    self.objects = objs
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
    self.clipboard = []
    for o in self.selection:
      st = self._obj_to_state(o)
      if st is not None:
        self.clipboard.append(st)

  def paste(self):
    if not self.clipboard:
      return
    before = self._snapshot()
    new = []
    for st in self.clipboard:
      if st is None:
        continue
      s2 = dict(st)
      s2["x"] = s2["x"] + PASTE_OFFSET
      s2["y"] = s2["y"] - PASTE_OFFSET
      o = self._make_from_state(s2)
      if o is not None:
        new.append(o)
    if not new:
      return
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
      if s is None:
        continue
      s["x"] += PASTE_OFFSET
      s["y"] -= PASTE_OFFSET
      o = self._make_from_state(s)
      if o is not None:
        new.append(o)
    if not new:
      return
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
        # <STRANGE>#564: ?? ???????????????? ???????????????? ?? ?????????????????? ??????????
        if isinstance(o, EditorBackground) and getattr(o, "polygon", False):
          for p in o.points:
            p[0] = -p[0]
        o.x = 2 * c - o.x
    else:
      ys = [o.y for o in objs]
      c = (min(ys) + max(ys)) / 2
      for o in objs:
        if isinstance(o, EditorBackground) and getattr(o, "polygon", False):
          for p in o.points:
            p[1] = -p[1]
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
    # <STRANGE>#1002: open inspector for any selected world object
    if self.selected is not None:
      self.push_inspector(self.selected)
    else:
      self._close_all_inspectors()