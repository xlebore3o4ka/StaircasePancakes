"""Обработка событий: клавиатура, mouse down/up/motion, контекстные меню."""
import json as _json
import pygame

from .const import (
  BOT_H, MIN_SIZE, ZOOM_STEP, ITEM_TYPES, PASTE_OFFSET,
  ARTIFACT_TYPES,
  DEFAULT_ARTIFACT_TYPE,
)
from .objects import EditorItem, EditorSpawner, EditorArtifact, EditorAnchor
from .widgets import ContextMenu


class EventsMixin:
  def handle_event(self, e):
    if e.type == pygame.QUIT:
      self.running = False
      return

    # 1. context menu
    if self.context_menu is not None:
      menu = self.context_menu
      if e.type == pygame.MOUSEMOTION:
        menu.hover_index(e.pos)
        return
      if e.type == pygame.MOUSEBUTTONDOWN:
        if e.button == 1:
          idx = menu.hover_index(e.pos)
          if idx >= 0:
            opt = menu.options[idx]
            if opt is not None:
              _, value = opt
              menu.on_select(value)
              if self.context_menu is menu:
                self.context_menu = None
          else:
            self.context_menu = None
        else:
          self.context_menu = None
        return
      if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
        self.context_menu = None
        return
      return

    # 2. inspector panels (top-first)
    for p in reversed(self.inspector_stack):
      if p.on_event(e):
        return
    if any(p.wants_keyboard() for p in self.inspector_stack) \
       and e.type == pygame.KEYDOWN and e.key != pygame.K_ESCAPE:
      return

    # 3. top panel
    if self.panel.on_event(e):
      return
    if self.panel.wants_keyboard() and e.type == pygame.KEYDOWN \
       and e.key != pygame.K_ESCAPE:
      return

    # 4. world
    if e.type == pygame.KEYDOWN:
      self._on_keydown(e)
      return

    if e.type == pygame.MOUSEWHEEL:
      mx, my = pygame.mouse.get_pos()
      if e.y > 0:
        self._zoom_at((mx, my), self.zoom * ZOOM_STEP)
      elif e.y < 0:
        self._zoom_at((mx, my), self.zoom / ZOOM_STEP)
      return

    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
      try:
        if self._handle_message_click(e.pos):
          return
      except Exception:
        pass
      try:
        if self._handle_plan_click(e.pos):
          return
      except Exception:
        pass
      try:
        if self._handle_markup_click(e.pos):
          return
      except Exception:
        pass
      try:
        if self._handle_anchor_click(e.pos):
          return
      except Exception:
        pass
    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
      if self._try_open_context_menu(e.pos):
        return
      self.panning = True
      self.pan_last = e.pos
    elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 2:
      self.panning = True
      self.pan_last = e.pos
    elif e.type == pygame.MOUSEBUTTONUP and e.button in (2, 3):
      self.panning = False
    elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
      self.snap_guides_x = []
      self.snap_guides_y = []
      self.begin_undo()
      self.on_mouse_down(e.pos)
    elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
      ctrl = bool(pygame.key.get_mods() & pygame.KMOD_CTRL)

      if self.drag is not None and self.drag[0] == "select_rect":
        self._finalize_select_rect(ctrl)
      if self.drag is not None and self.drag[0] == "poly_select_rect":
        # <STRANGE>#552: additive = shift, ???????????????????????? ?? drag data
        self._finalize_polygon_select_rect(self.drag[1])
      if self.drag is not None and self.drag[0] == "plan_drag":
        self._finalize_plan_drag()
      if self.drag is not None and self.drag[0] == "plan_drag":
        self._finalize_plan_drag()
      if self.drag is not None and self.drag[0] == "zone_unlock":
        self._apply_zone_unlock()
      if self.drag is not None and self.drag[0] == "create" and self.selected is not None:
        if hasattr(self.selected, "w") and self.selected.w < MIN_SIZE:
          self.selected.w = MIN_SIZE
        if hasattr(self.selected, "h") and self.selected.h < MIN_SIZE:
          self.selected.h = MIN_SIZE

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
      self._drag_x_refs = []
      self._drag_y_refs = []
      self.snap_guides_x = []
      self.snap_guides_y = []
      self._finalize_editor_panel_size()
      self.commit_undo()
    elif e.type == pygame.MOUSEMOTION:
      if self.panning:
        dx = e.pos[0] - self.pan_last[0]
        dy = e.pos[1] - self.pan_last[1]
        self.cam_x -= dx / self.zoom
        self.cam_y += dy / self.zoom
        self.pan_last = e.pos
      elif self.drag is not None and self.drag[0] == "select_rect":
        self.select_now = self.from_screen(*e.pos)
      elif self.drag is not None and self.drag[0] == "poly_select_rect":
        self.select_now = self.from_screen(*e.pos)
      elif self.drag is not None and self.drag[0] == "zone_unlock":
        self.zone_now = self.from_screen(*e.pos)
      elif self.erasing:
        wx, wy = self.from_screen(*e.pos)
        if self._erase_prev is None:
          self._erase_at(wx, wy)
        else:
          px, py = self._erase_prev
          self._erase_segment(px, py, wx, wy)
        self._erase_prev = (wx, wy)
      elif self.drag is not None:
        self.on_mouse_move(self.from_screen(*e.pos))

  def _handle_plan_click(self, pos):
    # <STRANGE>#1167: hit test on plan panel buttons
    if not getattr(self, "mind_mode", False):
      return False
    if self.tool != "planner":
      return False
    p = getattr(self, "plan", None)
    if p is None:
      return False
    info = getattr(self, "_plan_panel_pos", None)
    if not isinstance(info, dict):
      return False
    # <STRANGE>#1183: editable rows first (screen coords, from render)
    rows = info.get("rows", {})
    for key in ("dx", "dy", "dur"):
      r = rows.get(key)
      if r is not None and r.collidepoint(pos):
        if self.plan_focus is not None:
          self._plan_field_commit()
        self.plan_focus = key
        self.plan_buffer = ""
        self.plan_cursor_blink = 0.0
        return True
    re_ = rows.get("ease")
    if re_ is not None and re_.collidepoint(pos):
      order = ["linear", "in", "out", "inout"]
      cur = self.plan.get("ease", "out")
      try:
        idx = order.index(cur)
      except ValueError:
        idx = -1
      self.plan["ease"] = order[(idx + 1) % len(order)]
      self._mark_scene_dirty()
      return True
    # buttons (screen coords from render)
    for r, key in info.get("buttons", []):
      if r.collidepoint(pos):
        if key == "preview":
          if getattr(self, "plan_preview_active", False):
            self._stop_plan_preview()
          else:
            self._start_plan_preview()
        elif key == "copy":
          self._copy_plan_text()
        elif key == "clear":
          try:
            self._stop_plan_preview()
          except Exception:
            pass
          self.plan = None
          self._mark_scene_dirty()
        return True
    # <STRANGE>#1191: clicked inside the panel but not on an interactive row -> unfocus
    try:
      px, py, pw, ph = 10, self.panel.height() + 8, 300, 10
      if self.plan is not None:
        info_obj = getattr(self, "_plan_panel_pos", None)
        if isinstance(info_obj, dict):
          pass
      if self.plan_focus is not None:
        self._plan_field_commit()
    except Exception:
      pass
    return False

  def _handle_anchor_click(self, pos):
    # <STRANGE>#1473: buttons first, then rows based on variant
    if not getattr(self, "mind_mode", False):
      return False
    if self.tool != "anchor":
      return False
    info = getattr(self, "_anchor_panel_pos", None)
    if not isinstance(info, dict):
      return False
    for r, key in info.get("buttons", []):
      if r.collidepoint(pos):
        if key == "bake":
          for o in self.selection:
            if getattr(o, "variant", "") == "S":
              self._bake_zone(o)
              break
        return True
    first = None
    for o in self.selection:
      if hasattr(o, "variant"):
        first = o
        break
    if first is None:
      return False
    variant = getattr(first, "variant", "A")
    if variant in ("A", "B"):
      valid = ("binding",)
    elif variant == "S":
      valid = ("name", "weight", "max_limit")
    else:
      return False
    rows = info.get("rows", {})
    for key in valid:
      r = rows.get(key)
      if r is not None and r.collidepoint(pos):
        if self.anchor_focus is not None:
          self._anchor_field_commit()
        self.anchor_focus = key
        if key == "weight":
          self.anchor_buffer = str(int(getattr(first, "weight", 1)))
        elif key == "max_limit":
          self.anchor_buffer = str(int(getattr(first, "max_limit", 1)))
        elif key == "binding":
          self.anchor_buffer = getattr(first, "binding", "")
        elif key == "name":
          self.anchor_buffer = getattr(first, "name", "")
        self.anchor_cursor_blink = 0.0
        return True
    if self.anchor_focus is not None:
      self._anchor_field_commit()
    return False

  def _export_anchor_info(self, anchor):
    # <STRANGE>#1445: full export - zones with their S, free spawns, no overlap
    try:
      self._recompute_messages()
    except Exception:
      pass
    store = getattr(self, "messages", None)
    if store is not None and "anchor_overlap" in getattr(store, "active", {}):
      try:
        from .messages import ERROR
        self.messages.toast_only(ERROR,
            "Cannot export: zones overlap", 3.0)
      except Exception:
        pass
      return
    pairs, free_s, assigned, zone_s = self._anchor_pairs()
    data = {"version": 1, "anchors": [], "zones": [], "free_spawns": []}
    # zones that have their S
    good_zones = []
    for bnd, a, b in pairs:
      if bnd not in zone_s:
        continue
      good_zones.append((bnd, a, b))
    # anchors: A/B of good zones + free S
    for bnd, a, b in good_zones:
      data["anchors"].append(a.to_json())
      data["anchors"].append(b.to_json())
    for s in free_s:
      data["anchors"].append({"x": int(s.x), "y": int(s.y), "variant": "S"})
    # zones
    for bnd, a, b in good_zones:
      l, r, bt, tt = self._anchor_zone_rect(a, b)
      inside = []
      for o in self.objects:
        if hasattr(o, "variant"):
          continue
        try:
          if o.intersects_rect(l, r, bt, tt):
            inside.append(getattr(o, "id", "") or "<no id>")
        except Exception:
          pass
      zs = None
      for s in self.objects:
        if (getattr(s, "variant", "") == "S"
            and assigned.get(id(s)) == bnd):
          zs = [int(s.x), int(s.y)]
          break
      data["zones"].append({
        "binding": bnd,
        "name": getattr(a, "name", "") or getattr(b, "name", ""),
        "weight": int(getattr(a, "weight", 1)),
        "max_limit": int(getattr(a, "max_limit", 1)),
        "A": [int(a.x), int(a.y)],
        "B": [int(b.x), int(b.y)],
        "S": zs,
        "size": [int(abs(b.x - a.x)), int(abs(b.y - a.y))],
        "objects": inside,
      })
    # free spawns
    for s in free_s:
      data["free_spawns"].append({"x": int(s.x), "y": int(s.y)})
    txt = _json.dumps(data, indent=2)
    try:
      import tkinter as _tk
      r = _tk.Tk()
      r.withdraw()
      r.clipboard_clear()
      r.clipboard_append(txt)
      r.update()
      r.destroy()
    except Exception:
      try:
        pygame.scrap.put_text(txt)
      except Exception:
        pass
    try:
      from .messages import INFO
      self.messages.toast_only(INFO, "Exported %d zone(s)" % len(data["zones"]), 2.5)
    except Exception:
      pass

  def _handle_markup_click(self, pos):
    # <STRANGE>#1307: click handling for the markup panel
    if not getattr(self, "mind_mode", False):
      return False
    if self.tool != "markup":
      return False
    info = getattr(self, "_markup_panel_pos", None)
    if not isinstance(info, dict):
      return False
    rows = info.get("rows", {})
    for key in ("prefix", "postfix", "min", "sep"):
      r = rows.get(key)
      if r is not None and r.collidepoint(pos):
        if self.markup_focus is not None:
          self._markup_field_commit()
        self.markup_focus = key
        if key == "min":
          self.markup_buffer = str(self.markup.get("min", 0))
        else:
          self.markup_buffer = self.markup.get(key, "")
        self.markup_cursor_blink = 0.0
        return True
    for r, key in info.get("buttons", []):
      if r.collidepoint(pos):
        if key == "apply":
          self._markup_apply()
        elif key == "clear":
          self.markup_focus = None
          self.markup_buffer = ""
          self._clear_selection()
        return True
    # clicked inside panel but not on a row/button: commit focus
    if self.markup_focus is not None:
      self._markup_field_commit()
    return False

  def _copy_plan_text(self):
    # <STRANGE>#1168: put ctx.move_to(...) lines into the clipboard
    p = getattr(self, "plan", None)
    if p is None:
      return
    dx = float(p.get("dx", 0.0)); dy = float(p.get("dy", 0.0))
    dur = float(p.get("dur", 0.5)); ease = p.get("ease", "out")
    lines = []
    for obj in p.get("objects", []):
      oid = getattr(obj, "id", "")
      if not oid:
        continue
      tx = int(round(obj.x + dx))
      ty = int(round(obj.y + dy))
      lines.append('ctx.move_to(ctx.by_id("%s"), x=%d, y=%d, dur=%.2f, ease="%s")'
                   % (oid, tx, ty, dur, ease))
    text = "\n".join(lines)
    if not text:
      return
    try:
      import tkinter as _tk
      r = _tk.Tk()
      r.withdraw()
      r.clipboard_clear()
      r.clipboard_append(text)
      r.update()
      r.destroy()
    except Exception:
      try:
        pygame.scrap.put_text(text)
      except Exception:
        pass
    try:
      from .messages import INFO
      self.messages.toast_only(INFO, "Copied %d line(s)" % len(lines), 2.5)
    except Exception:
      pass

  def _finalize_plan_drag(self):
    # <STRANGE>#1153: commit the plan, or warn if any selected object has no id.
    if getattr(self, "_plan_preview", None) is None:
      self._plan_preview = None
      self._plan_drag_data = []
      return
    dx = self._plan_preview.get("dx", 0.0)
    dy = self._plan_preview.get("dy", 0.0)
    objs = list(self.selection)
    no_id = [o for o in objs if not getattr(o, "id", "")]
    if no_id:
      try:
        from .messages import WARN
        self.messages.set("plan_no_id", WARN,
                          "Cannot plan: %d object(s) have no id" % len(no_id),
                          no_id, ttl=5.0)
      except Exception:
        pass
      self.plan = None
    else:
      self.plan = {
        "dx": float(dx),
        "dy": float(dy),
        "objects": objs,
        "orig_positions": {id(o): (o.x, o.y) for o in objs},
        "dur": 0.5,
        "ease": "out",
      }
      try:
        self.messages.clear("plan_no_id")
      except Exception:
        pass
    print("PLAN-FINALIZE: plan=%s objects=%d dx=%s dy=%s" % (
        self.plan is not None,
        len(self.plan.get("objects", [])) if self.plan else 0,
        self.plan.get("dx") if self.plan else None,
        self.plan.get("dy") if self.plan else None))
    self._plan_preview = None
    self._plan_drag_data = []
    self._plan_start = None
    self.drag = None
    self._mark_scene_dirty()

  def _finalize_plan_drag(self):
    # <STRANGE>#1153: commit the plan, or warn if any selected object has no id.
    if getattr(self, "_plan_preview", None) is None:
      self._plan_preview = None
      self._plan_drag_data = []
      return
    dx = self._plan_preview.get("dx", 0.0)
    dy = self._plan_preview.get("dy", 0.0)
    objs = list(self.selection)
    no_id = [o for o in objs if not getattr(o, "id", "")]
    if no_id:
      try:
        from .messages import WARN
        self.messages.set("plan_no_id", WARN,
                          "Cannot plan: %d object(s) have no id" % len(no_id),
                          no_id, ttl=5.0)
      except Exception:
        pass
      self.plan = None
    else:
      self.plan = {
        "dx": float(dx),
        "dy": float(dy),
        "objects": objs,
        "orig_positions": {id(o): (o.x, o.y) for o in objs},
        "dur": 0.5,
        "ease": "out",
      }
      try:
        self.messages.clear("plan_no_id")
      except Exception:
        pass
    self._plan_preview = None
    self._plan_drag_data = []
    self._plan_start = None
    self.drag = None
    self._mark_scene_dirty()

  # ---------- keyboard ----------
  def _on_keydown(self, e):
    ctrl = bool(e.mod & pygame.KMOD_CTRL)
    shift = bool(e.mod & pygame.KMOD_SHIFT)

    if ctrl:
      if e.key == pygame.K_z:
        if shift:
          self.redo()
        else:
          self.undo()
      elif e.key == pygame.K_y:
        self.redo()
      elif e.key == pygame.K_d:
        self.duplicate_selected()
      elif e.key == pygame.K_c:
        self.copy_selected()
      elif e.key == pygame.K_v:
        self.paste()
      elif e.key == pygame.K_s:
        self.save()
      elif e.key == pygame.K_o:
        self.load()
      elif e.key == pygame.K_a:
        self._set_selection(list(self.objects))
      elif e.key == pygame.K_0:
        self.zoom = 1.0
        self.scale = 1.0
        self._rebuild_ghost_assets()
      elif e.key == pygame.K_l:
        self.set_tool("peg" if self.tool == "lock" else "lock")
      return

    if getattr(self, "plan_focus", None) is not None:
      self._plan_field_key(e)
      return
    if getattr(self, "markup_focus", None) is not None:
      self._markup_field_key(e)
      return
    if getattr(self, "anchor_focus", None) is not None:
      self._anchor_field_key(e)
      return
    if e.key == pygame.K_ESCAPE:
      if self.polygon_edit is not None:
        self.exit_polygon_edit()
      elif self.inspector_stack:
        self.pop_inspector()
      else:
        self.running = False
    elif e.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
      # <STRANGE>#523: ?? polygon_edit ?????????????? ?????? ???????????????????? ??????????????
      if self.polygon_edit is not None and self.polygon_edit.active_points:
        bg = self.polygon_edit
        for p in sorted(bg.active_points, reverse=True):
          if 0 <= p < len(bg.points):
            del bg.points[p]
        bg.active_points = set()
        self._mark_scene_dirty()
      else:
        self.delete_selected()
    elif e.key == pygame.K_SPACE:
      self.cam_x, self.cam_y = self.ghost[0], self.ghost[1]
    elif e.key == pygame.K_p and getattr(self, "mind_mode", False):
      # <STRANGE>#1165: P toggles preview
      if getattr(self, "plan_preview_active", False):
        self._stop_plan_preview()
      else:
        self._start_plan_preview()
    elif e.key == pygame.K_c and getattr(self, "mind_mode", False) and bool(e.mod & pygame.KMOD_CTRL):
      pass
    elif e.key == pygame.K_t:
      # <STRANGE>#1148: T toggles the thinking mode
      mm = not getattr(self, "mind_mode", False)
      self.mind_mode = mm
      try:
        self.panel.think_btn.active = mm
      except Exception:
        pass
      if mm:
        self.set_tool("planner")
      else:
        self.set_tool("peg")
    elif e.key == pygame.K_1:
      self.set_tool("ghost")
    elif e.key == pygame.K_2:
      self.set_tool("eraser")
    elif e.key == pygame.K_3:
      self.set_tool("peg")
    elif e.key == pygame.K_4:
      self.set_tool("platform")
    elif e.key == pygame.K_5:
      self.set_tool("background")
    elif e.key == pygame.K_6:
      self.set_tool("item")
    elif e.key == pygame.K_7:
      self.set_tool("spawner")
    elif e.key == pygame.K_8:
      self.set_tool("bag")
    elif e.key == pygame.K_9:
      self.set_tool("trigger")
    elif e.key == pygame.K_0:
      self.set_tool("button")
    elif e.key == pygame.K_l:
      self.set_tool("lock")
    elif e.key == pygame.K_u:
      self.set_tool("unlock_zone")

  # ---------- context menus ----------
  def _try_open_context_menu(self, pos):
    if self.polygon_edit is not None:
      return self._try_polygon_edit_menu(pos)
    x, y = pos
    sh = self.screen.get_height()
    if y < self.panel.height() or y >= sh - BOT_H:
      return False
    wx, wy = self.from_screen(x, y)

    for obj in reversed(self.objects):
      if obj.locked:
        continue
      if obj.hit(wx, wy):
        self._open_object_menu(obj, pos)
        return True

    if self.tool == "item":
      self._open_pick_type_menu(pos)
      return True
    if self.tool == "artifact":
      self._open_pick_artifact_menu(pos)
      return True
    if self.tool == "anchor":
      self._open_pick_anchor_menu(pos)
      return True
    return False

  def _try_polygon_edit_menu(self, pos):
    # <STRANGE>#524: ?????????????????????? ???????? ???????????? ???????????? ????????????????
    bg = self.polygon_edit
    if bg is None:
      return False
    kind, idx = self._polygon_edit_pick(pos)
    wx, wy = self.from_screen(*pos)
    options = []
    if kind == "vertex":
      title = "Vertex #%d" % idx
      options.append(("Delete vertex", ("del_vertex", idx)))
      options.append(("Split edge", ("split_edge", idx)))
    elif kind == "edge":
      title = "Edge #%d" % idx
      options.append(("Add vertex on edge", ("add_edge", idx)))
    else:
      title = "Polygon"
      options.append(("Add vertex here", ("add_here", None)))
    options.append(None)
    options.append(("Select all vertices", ("sel_all", None)))
    options.append(("Clear selection", ("sel_none", None)))
    options.append(None)
    options.append(("Convert to rect", ("to_rect", None)))
    options.append(("Exit edit", ("exit_edit", None)))

    before = self._snapshot()

    def _reindex_after_remove(removed):
      new_set = set()
      for p in bg.active_points:
        if p == removed:
          continue
        new_set.add(p if p < removed else p - 1)
      bg.active_points = new_set

    def on_select(value):
      act, data = value
      if act == "add_here":
        bg.points.append([int(wx - bg.x), int(wy - bg.y)])
        bg.active_points = {len(bg.points) - 1}
        self._push_undo_now(before)
        self._mark_scene_dirty()
      elif act == "add_edge":
        vpts = bg.world_points()
        n = len(vpts)
        x0, y0 = vpts[data]
        x1, y1 = vpts[(data + 1) % n]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        bg.points.insert(data + 1, [int(mx - bg.x), int(my - bg.y)])
        bg.active_points = {data + 1}
        self._push_undo_now(before)
        self._mark_scene_dirty()
      elif act == "split_edge":
        vpts = bg.world_points()
        n = len(vpts)
        x0, y0 = vpts[data]
        x1, y1 = vpts[(data + 1) % n]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        bg.points.insert(data + 1, [int(mx - bg.x), int(my - bg.y)])
        bg.active_points = {data + 1}
        self._push_undo_now(before)
        self._mark_scene_dirty()
      elif act == "del_vertex":
        p = data
        if 0 <= p < len(bg.points) and len(bg.points) > 3:
          del bg.points[p]
          _reindex_after_remove(p)
          self._push_undo_now(before)
          self._mark_scene_dirty()
      elif act == "sel_all":
        bg.active_points = set(range(len(bg.points)))
        self._mark_scene_dirty()
      elif act == "sel_none":
        bg.active_points = set()
        self._mark_scene_dirty()
      elif act == "to_rect":
        self.exit_polygon_edit()
        bg.to_rect()
        self._push_undo_now(before)
        self._mark_scene_dirty()
      elif act == "exit_edit":
        self.exit_polygon_edit()

    self.context_menu = ContextMenu(self.screen.get_size(), options, pos,
                                    on_select, title=title)
    return True

  def _open_object_menu(self, obj, pos):
    is_group = len(self.selection) > 1 and obj in self.selection
    targets = list(self.selection) if is_group else [obj]

    if is_group:
      title = f"{len(targets)} objects selected"
    else:
      cur = self._effective_layer(obj)
      is_default = obj.layer is None
      kind = type(obj).__name__.replace("Editor", "")
      title = f"{kind}  ·  layer {cur}" + ("  (default)" if is_default else "")

    from .objects import EditorBackground, EditorPlatform, EditorAnchor
    options = []
    if not is_group and isinstance(obj, (EditorBackground, EditorPlatform)):
      if getattr(obj, "polygon", False):
        options.append(("Edit points", ("edit_points", None)))
        options.append(("Convert to rect", ("to_rect", None)))
      else:
        options.append(("Convert to polygon", ("to_polygon", None)))
      options.append(None)
    if not is_group and isinstance(obj, EditorItem):
      options.append(("Change type...", ("change_type", None)))
    if not is_group and isinstance(obj, EditorArtifact):
      options.append(("Change artifact type...", ("change_artifact_type", None)))
    # <STRANGE>#1080: Open inspector entry for every object
    if not is_group:
      options.append(("Open inspector", ("open_inspector", None)))
    # <STRANGE>#1407: anchors can export their pair info
    if not is_group and isinstance(obj, EditorAnchor):
      options.append(("Change variant...", ("change_anchor_variant", None)))
      options.append(("Export info", ("export_anchor", None)))
    options.append(("Layer  +1", ("layer", 1)))
    options.append(("Layer  -1", ("layer", -1)))
    options.append(("Layer  +5", ("layer", 5)))
    options.append(("Layer  -5", ("layer", -5)))
    if is_group or obj.layer is not None:
      options.append(("Reset layer to default", ("layer_reset", None)))
    options.append(None)
    options.append(("Delete", ("delete", None)))
    options.append(("Lock", ("lock", None)))
    if is_group:
      options.append(None)
      options.append(("Flip horizontal", ("flip_h", None)))
      options.append(("Flip vertical", ("flip_v", None)))

    before = self._snapshot()

    def on_select(value):
      act, delta = value
      if act == "to_polygon":
        obj.to_polygon()
        self._push_undo_now(before)
        self._mark_scene_dirty()
        self.enter_polygon_edit(obj)
        return
      if act == "to_rect":
        if self.polygon_edit is obj:
          self.exit_polygon_edit()
        obj.to_rect()
        self._push_undo_now(before)
        self._mark_scene_dirty()
        return
      if act == "edit_points":
        if not obj.polygon:
          obj.to_polygon()
        self.enter_polygon_edit(obj)
        return
      if act == "change_artifact_type":
        self._open_change_artifact_type_menu(obj, pos)
        return
      if act == "change_type":
        self._open_change_type_menu(obj, pos)
        return
      if act == "open_inspector":
        self.push_inspector(obj)
        return
      if act == "export_anchor":
        self._export_anchor_info(obj)
        return
      if act == "change_anchor_variant":
        self._open_change_anchor_variant_menu(obj, pos)
        return
      if act == "layer":
        for t in targets:
          t.layer = self._effective_layer(t) + delta
        self._push_undo_now(before)
        self._mark_scene_dirty()
      elif act == "layer_reset":
        for t in targets:
          t.layer = None
        self._push_undo_now(before)
        self._mark_scene_dirty()
      elif act == "delete":
        self._delete_objects(targets)
        self._push_undo_now(before)
      elif act == "lock":
        for t in targets:
          t.locked = True
        self._clear_selection()
        self._push_undo_now(before)
        self._mark_scene_dirty()
      elif act == "flip_h":
        self._flip_objects(targets, horizontal=True)
        self._push_undo_now(before)
        self._mark_scene_dirty()
      elif act == "flip_v":
        self._flip_objects(targets, horizontal=False)
        self._push_undo_now(before)
        self._mark_scene_dirty()

    self.context_menu = ContextMenu(self.screen.get_size(), options, pos,
                                    on_select, title=title)

  def _open_change_type_menu(self, item, pos):
    before = self._snapshot()
    def on_select(t):
      item.set_type(t)
      self.current_item_type = t
      self._push_undo_now(before)
      self._mark_scene_dirty()
      self._sync_inspector()
    options = [(t, t) for t in ITEM_TYPES]
    title = f"Item type  ·  {item.item_type}"
    self.context_menu = ContextMenu(self.screen.get_size(), options, pos,
                                    on_select, title=title)


  def _open_change_artifact_type_menu(self, artifact, pos):
    # <STRANGE>#730: change artifact type of existing object
    before = self._snapshot()

    def on_select(t):
      if t == artifact.artifact_type:
        return
      self.objects = [
        o for o in self.objects
        if not (isinstance(o, EditorArtifact)
                and o is not artifact
                and o.artifact_type == t)
      ]
      artifact.artifact_type = t
      self.current_artifact_type = t
      self._push_undo_now(before)
      self._mark_scene_dirty()
      self._sync_inspector()

    options = [(t, t) for t in ARTIFACT_TYPES]
    title = "Artifact type  \u00b7  %s" % artifact.artifact_type
    self.context_menu = ContextMenu(self.screen.get_size(), options, pos,
                                    on_select, title=title)

  def _open_pick_artifact_menu(self, pos):
    # <STRANGE>#731: pick artifact type to place (RMB on empty with artifact tool)
    def on_select(t):
      self.current_artifact_type = t

    options = [(t, t) for t in ARTIFACT_TYPES]
    cur = getattr(self, "current_artifact_type", DEFAULT_ARTIFACT_TYPE)
    title = "Place artifact  \u00b7  current: %s" % cur
    self.context_menu = ContextMenu(self.screen.get_size(), options, pos,
                                    on_select, title=title)

  def _open_change_anchor_variant_menu(self, anchor, pos):
    # <STRANGE>#1422: change variant of an existing anchor
    from .const import ANCHOR_VARIANTS
    before = self._snapshot()
    def on_select(t):
      if t == anchor.variant:
        return
      anchor.variant = t
      # <STRANGE>#1446: S uniqueness is per-zone, not global - do nothing here
      self._push_undo_now(before)
      self._mark_scene_dirty()
      self._sync_inspector()
    options = [(v, v) for v in ANCHOR_VARIANTS]
    title = "Variant  \u00b7  %s" % anchor.variant
    self.context_menu = ContextMenu(self.screen.get_size(), options, pos,
                                    on_select, title=title)

  def _open_pick_anchor_menu(self, pos):
    # <STRANGE>#1408: pick anchor variant (A / B / S)
    from .const import ANCHOR_VARIANTS
    def on_select(t):
      self.current_anchor_variant = t
    options = [(v, v) for v in ANCHOR_VARIANTS]
    cur = getattr(self, "current_anchor_variant", "A")
    title = "Place anchor  \u00b7  current: %s" % cur
    self.context_menu = ContextMenu(self.screen.get_size(), options, pos,
                                    on_select, title=title)

  def _open_pick_type_menu(self, pos):
    def on_select(t):
      self.current_item_type = t
    options = [(t, t) for t in ITEM_TYPES]
    title = f"Place item  ·  current: {self.current_item_type}"
    self.context_menu = ContextMenu(self.screen.get_size(), options, pos, on_select, title=title)