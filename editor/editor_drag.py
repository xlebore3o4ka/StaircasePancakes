"""Мышь, drag/resize/create, ластик, зона разблокировки, snap, курсор."""
import math
import pygame

from .const import (
  BOT_H, MIN_SIZE, SNAP_DIST, SNAP_RANGE, PLAYER_R,
  CLICK_THRESHOLD, RESIZE_ZONE,
)
from .objects import (
  EditorPeg, EditorPlatform, EditorBackground, EditorItem, EditorSpawner,
)
from . import settings


class DragMixin:
  # ---------- cursor ----------
  def _make_lock_cursor(self):
    surf = pygame.Surface((28, 28), pygame.SRCALPHA)
    pygame.draw.circle(surf, (0, 0, 0, 90), (14, 16), 12)
    body = pygame.Rect(7, 13, 14, 11)
    pygame.draw.arc(surf, (255, 215, 0), (9, 4, 10, 14), 0, math.pi, 3)
    pygame.draw.arc(surf, (0, 0, 0),     (9, 4, 10, 14), 0, math.pi, 1)
    pygame.draw.rect(surf, (255, 215, 0), body, border_radius=2)
    pygame.draw.rect(surf, (0, 0, 0),     body, 2, border_radius=2)
    pygame.draw.circle(surf, (0, 0, 0), (14, body.y + body.h // 2 - 1), 2)
    try:
      return pygame.cursors.Cursor((14, 16), surf)
    except Exception:
      return None

  def update_cursor(self):
    # <STRANGE>#603: ?????? ???????????? ??? crosshair, ?????????????????? ???????? ??????????????????
    try:
      mx, my = pygame.mouse.get_pos()
      if self._rotate_arc_hit((mx, my)) is not None:
        if self.cursor != "rotate":
          pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_CROSSHAIR)
          self.cursor = "rotate"
        return
    except Exception:
      pass
    if self.tool == "lock":
      if self.cursor != "lock":
        if self._lock_cursor is not None:
          pygame.mouse.set_cursor(self._lock_cursor)
        else:
          pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
        self.cursor = "lock"
      return
    if self.tool == "eraser":
      if self.cursor != "eraser":
        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_CROSSHAIR)
        self.cursor = "eraser"
      return
    if self.tool == "unlock_zone":
      if self.cursor != "zone":
        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_CROSSHAIR)
        self.cursor = "zone"
      return

    want = pygame.SYSTEM_CURSOR_ARROW
    if isinstance(self.selected, (EditorPlatform, EditorBackground)) \
       and not self.selected.locked:
      mx, my = pygame.mouse.get_pos()
      wx, wy = self.from_screen(mx, my)
      edge = self.selected.edge_hit(wx, wy, self._resize_zone_world())
      if edge in ("left", "right"):
        want = pygame.SYSTEM_CURSOR_SIZEWE
      elif edge in ("top", "bottom"):
        want = pygame.SYSTEM_CURSOR_SIZENS
    if want != self.cursor:
      pygame.mouse.set_cursor(want)
      self.cursor = want

  # ---------- bounds ----------
  def _obj_bounds(self, obj):
    if isinstance(obj, (EditorPeg, EditorSpawner)):
      return (obj.x - obj.r, obj.x + obj.r, obj.y - obj.r, obj.y + obj.r)
    l, r, b, t = obj.world_rect()
    return (l, r, b, t)

  def _gather_x_refs(self, exclude=(), near=None):
    refs = []
    for obj in self.objects:
      if obj in exclude:
        continue
      l, r, b, t = self._obj_bounds(obj)
      if near is not None:
        nl, nr, nb, nt = near
        if r < nl or l > nr or t < nb or b > nt:
          continue
      refs.append(l)
      refs.append((l + r) / 2)
      refs.append(r)
      # <STRANGE>#561: ???????? ?????????????????? ??? ???????? ???????? ????????????????
      if isinstance(obj, EditorBackground) and getattr(obj, "polygon", False):
        for wx, wy in obj.world_points():
          refs.append(wx)
    return refs

  def _gather_y_refs(self, exclude=(), near=None):
    refs = [0.0]  # ?????? ??? ???????????? ????????????????
    for obj in self.objects:
      if obj in exclude:
        continue
      l, r, b, t = self._obj_bounds(obj)
      if near is not None:
        nl, nr, nb, nt = near
        if r < nl or l > nr or t < nb or b > nt:
          continue
      refs.append(b)
      refs.append((b + t) / 2)
      refs.append(t)
      if isinstance(obj, EditorBackground) and getattr(obj, "polygon", False):
        for wx, wy in obj.world_points():
          refs.append(wy)
    return refs

  @staticmethod
  def _snap_value(value, refs):
    best = value
    best_d = SNAP_DIST + 1
    for r in refs:
      d = abs(r - value)
      if d < best_d:
        best_d = d
        best = r
    if best_d <= SNAP_DIST:
      return best, True
    return value, False

  # ---------- polygon edit helpers ----------
  def _polygon_edit_pick(self, pos):
    # <STRANGE>#511: ?????????????? ('vertex', i) / ('edge', i) / (None, None)
    bg = self.polygon_edit
    if bg is None:
      return None, None
    wx, wy = self.from_screen(*pos)
    r_world = 8 / max(0.01, self.zoom)
    vpts = bg.world_points()
    for i, (vx, vy) in enumerate(vpts):
      if (wx - vx) ** 2 + (wy - vy) ** 2 <= r_world ** 2:
        return "vertex", i
    n = len(vpts)
    if n >= 2:
      for i in range(n):
        x0, y0 = vpts[i]
        x1, y1 = vpts[(i + 1) % n]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        if (wx - mx) ** 2 + (wy - my) ** 2 <= r_world ** 2:
          return "edge", i
    return None, None

  def _polygon_edit_down(self, pos):
    bg = self.polygon_edit
    if bg is None:
      return
    wx, wy = self.from_screen(*pos)
    kind, idx = self._polygon_edit_pick(pos)
    shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
    if kind == "vertex":
      if shift:
        if idx in bg.active_points:
          bg.active_points.discard(idx)
        else:
          bg.active_points.add(idx)
      else:
        if idx not in bg.active_points:
          bg.active_points = {idx}
      vpts = bg.world_points()
      data = []
      for i in bg.active_points:
        if 0 <= i < len(vpts):
          vx, vy = vpts[i]
          data.append((i, wx - vx, wy - vy))
      self.drag = ("poly_vertex", data)
      return
    if kind == "edge":
      vpts = bg.world_points()
      n = len(vpts)
      x0, y0 = vpts[idx]
      x1, y1 = vpts[(idx + 1) % n]
      mx, my = (x0 + x1) / 2, (y0 + y1) / 2
      new_dx = int(mx - bg.x)
      new_dy = int(my - bg.y)
      bg.points.insert(idx + 1, [new_dx, new_dy])
      bg.active_points = {idx + 1}
      self.drag = ("poly_vertex", [(idx + 1, wx - mx, wy - my)])
      self._mark_scene_dirty()
      return
    # <STRANGE>#550: ???????? ???? ?????????????? ???????????? ?????????????????? ?????????? ??????????????????.
    # ?????? ?????????????? ?????????? ?????? ???????????????? ???? ???????????????????? ?????????? < CLICK_THRESHOLD,
    # ?? ???? ???????????? ???????????? ?????????????????? (shift = ???????????????? ?? ????????????????).
    self.select_start = (wx, wy)
    self.select_now = (wx, wy)
    self.drag = ("poly_select_rect", bool(shift))


  # ---------- mouse down ----------
  def on_mouse_down(self, pos):
    if self.polygon_edit is not None:
      self._polygon_edit_down(pos)
      return

    # <STRANGE>#601: ????????-?????????????? ?????????????????? ?????? ??????????????????
    arc = self._rotate_arc_hit(pos)
    if arc is not None:
      bg = self.selected
      mx, my = self.from_screen(*pos)
      import math as _m
      cx, cy = bg.x, bg.y
      start_ang = _m.degrees(_m.atan2(my - cy, mx - cx))
      self.drag = ("rotate", {"arc": arc, "start_ang": start_ang,
                              "start_points": [list(p) for p in
                                               (bg.points if bg.polygon else [])],
                              "start_polygon": bg.polygon,
                              "start_w": bg.w, "start_h": bg.h})
      return

    x, y = pos
    sh = self.screen.get_height()

    if y >= sh - BOT_H:
      if self.tab_ghost_rect().collidepoint(pos):
        self.set_tool("ghost")
      elif self.tab_eraser_rect().collidepoint(pos):
        self.set_tool("eraser")
      elif self.tab_peg_rect().collidepoint(pos):
        self.set_tool("peg")
      elif self.tab_plat_rect().collidepoint(pos):
        self.set_tool("platform")
      elif self.tab_bg_rect().collidepoint(pos):
        self.set_tool("background")
      elif self.tab_item_rect().collidepoint(pos):
        self.set_tool("item")
      elif self.tab_spawner_rect().collidepoint(pos):
        self.set_tool("spawner")
      return

    wx, wy = self.from_screen(x, y)
    mods = pygame.key.get_mods()
    ctrl = bool(mods & pygame.KMOD_CTRL)
    shift = bool(mods & pygame.KMOD_SHIFT)
    zone = self._resize_zone_world()

    if shift:
      if isinstance(self.selected, (EditorPlatform, EditorBackground)) \
         and not self.selected.locked:
        edge = self.selected.edge_hit(wx, wy, zone)
        if edge:
          self._begin_resize(edge)
          return

      hit = None
      for obj in reversed(self.objects):
        if obj.locked:
          continue
        if obj.hit(wx, wy):
          hit = obj
          break

      if hit is not None:
        if ctrl:
          self._toggle_selection(hit)
          return
        if hit not in self.selection:
          self._set_selection([hit])
        self._begin_move(wx, wy, hit)
        return

      self._begin_select_rect(wx, wy)
      return

    if self.tool == "unlock_zone":
      self.drag = ("zone_unlock", None)
      self.zone_start = (wx, wy)
      self.zone_now = (wx, wy)
      return

    if self.tool == "eraser":
      self.erasing = True
      self._erase_prev = (wx, wy)
      self._erase_at(wx, wy)
      return

    if self.tool == "lock":
      for obj in reversed(self.objects):
        if obj.hit(wx, wy):
          obj.locked = not obj.locked
          if obj.locked and obj in self.selection:
            self.selection.remove(obj)
            self.selected = self.selection[-1] if self.selection else None
            self._sync_inspector()
          self._mark_scene_dirty()
          return
      return

    if isinstance(self.selected, (EditorPlatform, EditorBackground)) \
       and not self.selected.locked:
      edge = self.selected.edge_hit(wx, wy, zone)
      if edge:
        self._begin_resize(edge)
        return

    hit = None
    for obj in reversed(self.objects):
      if obj.locked:
        continue
      if obj.hit(wx, wy):
        hit = obj
        break

    if hit is not None:
      if ctrl:
        self._toggle_selection(hit)
        return
      if hit not in self.selection:
        self._set_selection([hit])
      self._begin_move(wx, wy, hit)
      return

    gx, gy = self.ghost
    if (wx - gx) ** 2 + (wy - gy) ** 2 <= PLAYER_R ** 2:
      self.drag = ("ghost", (wx - gx, wy - gy))
      return
    if self.tool == "ghost":
      self.ghost_target = [wx, wy]
      return

    if self.tool == "peg":
      obj = EditorPeg(wx, wy)
      self.objects.append(obj)
      self._set_selection([obj])
      self._begin_move(wx, wy, obj)
      self._mark_scene_dirty()
    elif self.tool in ("platform", "background"):
      if self.tool == "background":
        obj = EditorBackground(wx, wy, 1, 1)
      else:
        obj = EditorPlatform(wx, wy, 1, 1)
      self.objects.append(obj)
      self._set_selection([obj])
      self.drag = ("create", (wx, wy))
      self._mark_scene_dirty()
    elif self.tool == "item":
      obj = EditorItem(wx, wy, self.current_item_type)
      self.objects.append(obj)
      self._set_selection([obj])
      self._begin_move(wx, wy, obj)
      self._mark_scene_dirty()
    elif self.tool == "spawner":
      obj = EditorSpawner(wx, wy)
      self.objects.append(obj)
      self._set_selection([obj])
      self._begin_move(wx, wy, obj)
      self._mark_scene_dirty()

  # ---------- mouse move ----------
  def on_mouse_move(self, world):
    wx, wy = world
    if self.drag is None:
      return
    mode, data = self.drag

    self.snap_guides_x = []
    self.snap_guides_y = []
    self.smart_guides = []
    alt = bool(pygame.key.get_mods() & pygame.KMOD_ALT)
    snap = self.snap_enabled and not alt

    if mode == "rotate":
      bg = self.selected
      if bg is None:
        return
      import math as _m
      cx, cy = bg.x, bg.y
      cur_ang = _m.degrees(_m.atan2(wy - cy, wx - cx))
      delta = cur_ang - data["start_ang"]

      # <STRANGE>#620: snap ?? ?????????????? 45?? ?????? ???????????????????? Snap (???????????? 7??)
      snapped_delta = delta
      if self.snap_enabled:
        target = round(delta / 45.0) * 45.0
        if abs(target - delta) <= 7.0:
          snapped_delta = target
      # <STRANGE>#621: ???????? Snap ???? ???????????????? ??? ?????????????? grid_step_angle
      if abs(snapped_delta - delta) < 1e-6 and \
         getattr(self, "grid_enabled", False) and \
         getattr(self, "grid_step_angle", 0) > 0:
        step = float(self.grid_step_angle)
        target = round(delta / step) * step
        if abs(target - delta) > 1e-6:
          snapped_delta = target

      # ?????????????????????????????? ?????????????????? ??????????????????
      if not data["start_polygon"]:
        bg.w = data["start_w"]
        bg.h = data["start_h"]
        bg.polygon = False
        bg.points = []
        bg.to_polygon()
      else:
        bg.polygon = True
        bg.points = [list(p) for p in data["start_points"]]

      bg.rotate_around_center(snapped_delta)
      self._mark_scene_dirty()
      return
    if mode == "poly_select_rect":
      self.select_now = (wx, wy)
      return
    if mode == "poly_select_rect":
      self.select_now = (wx, wy)
      return
    if mode == "poly_select_rect":
      self.select_now = (wx, wy)
      return
    if mode == "poly_vertex":
      bg = self.polygon_edit
      if bg is None:
        return
      for idx, off_x, off_y in data:
        if 0 <= idx < len(bg.points):
          bg.points[idx][0] = int(wx - bg.x - off_x)
          bg.points[idx][1] = int(wy - bg.y - off_y)
      self._mark_scene_dirty()
      return
    if mode == "move":
      self._apply_move(wx, wy, snap)
    elif mode == "ghost":
      dx, dy = data
      self.ghost[0] = wx - dx
      self.ghost[1] = wy - dy
      self.ghost_target = [self.ghost[0], self.ghost[1]]
    elif mode == "create":
      ox, oy = data
      self._apply_create(wx, wy, ox, oy, snap)
    elif mode == "resize":
      self._apply_resize(wx, wy, data, snap)

  # ---------- move ----------
  def _apply_move(self, wx, wy, snap):
    if not self._move_data or self._move_start is None:
      return
    sx, sy = self._move_start
    raw_dx = wx - sx
    raw_dy = wy - sy

    anchor = self._move_anchor
    primary_orig = None
    if anchor is not None:
      for obj, _, _, b in self._move_data:
        if obj is anchor:
          primary_orig = b
          break
    if primary_orig is None and self._move_data:
      primary_orig = self._move_data[0][3]

    snap_dx = raw_dx
    snap_dy = raw_dy
    edge_x = False
    edge_y = False

    if snap and primary_orig is not None:
      l0, r0, b0, t0 = None, None, None, None
      for obj, ox, oy, (bl, br, bb, bt) in self._move_data:
        nl = bl + raw_dx
        nr = br + raw_dx
        nb = bb + raw_dy
        nt = bt + raw_dy
        if l0 is None or nl < l0: l0 = nl
        if r0 is None or nr > r0: r0 = nr
        if b0 is None or nb < b0: b0 = nb
        if t0 is None or nt > t0: t0 = nt
      near = (l0 - SNAP_RANGE, r0 + SNAP_RANGE,
              b0 - SNAP_RANGE, t0 + SNAP_RANGE)

      x_refs = self._gather_x_refs(exclude=self.selection, near=near)
      y_refs = self._gather_y_refs(exclude=self.selection, near=near)

      pl, pr, pb, pt = primary_orig
      moved_x = [pl + raw_dx, (pl + pr) / 2 + raw_dx, pr + raw_dx]
      moved_y = [pb + raw_dy, (pb + pt) / 2 + raw_dy, pt + raw_dy]
      # <STRANGE>#562: ???????? ?????????? ?????????????? ??? ?????? ?????? ???????? ???????? ??????????????????
      if anchor is not None and isinstance(anchor, EditorBackground) \
         and getattr(anchor, "polygon", False):
        for vx, vy in anchor.world_points():
          moved_x.append(vx + raw_dx)
          moved_y.append(vy + raw_dy)

      best_x_diff = 0
      best_x_dist = SNAP_DIST + 1
      best_x_guide = None
      for mx in moved_x:
        for rx in x_refs:
          d = abs(rx - mx)
          if d < best_x_dist:
            best_x_dist = d
            best_x_diff = rx - mx
            best_x_guide = rx
      if best_x_guide is not None:
        snap_dx = raw_dx + best_x_diff
        edge_x = True
        self.snap_guides_x.append(best_x_guide)

      best_y_diff = 0
      best_y_dist = SNAP_DIST + 1
      best_y_guide = None
      for my in moved_y:
        for ry in y_refs:
          d = abs(ry - my)
          if d < best_y_dist:
            best_y_dist = d
            best_y_diff = ry - my
            best_y_guide = ry
      if best_y_guide is not None:
        snap_dy = raw_dy + best_y_diff
        edge_y = True
        self.snap_guides_y.append(best_y_guide)

    # <STRANGE>#563: grid step ??? ???????? edge-snap ???? ???????????????? ???? ???????? ??????
    if getattr(self, "grid_enabled", False) and \
       getattr(self, "grid_step", 0) > 0 and anchor is not None:
      step = float(self.grid_step)
      if not edge_x:
        tx = round((anchor.x + snap_dx) / step) * step
        snap_dx = tx - anchor.x
      if not edge_y:
        ty = round((anchor.y + snap_dy) / step) * step
        snap_dy = ty - anchor.y

    for obj, ox, oy, _ in self._move_data:
      if obj.locked:
        continue
      obj.x = ox + snap_dx
      obj.y = oy + snap_dy


  # ---------- create ----------
  def _apply_create(self, wx, wy, ox, oy, snap):
    guide_x = None
    guide_y = None
    if snap:
      l0 = min(ox, wx) - SNAP_RANGE
      r0 = max(ox, wx) + SNAP_RANGE
      b0 = min(oy, wy) - SNAP_RANGE
      t0 = max(oy, wy) + SNAP_RANGE
      near = (l0, r0, b0, t0)
      x_refs = self._gather_x_refs(exclude=self.selection, near=near)
      y_refs = self._gather_y_refs(exclude=self.selection, near=near)
      wx, hit_x = self._snap_value(wx, x_refs)
      if hit_x:
        guide_x = wx
      wy, hit_y = self._snap_value(wy, y_refs)
      if hit_y:
        guide_y = wy

    l = min(ox, wx); r = max(ox, wx)
    b = min(oy, wy); t = max(oy, wy)
    obj = self.selected
    if obj is None:
      return
    obj.w = max(r - l, 1)
    obj.h = max(t - b, 1)
    obj.x = (l + r) / 2
    obj.y = (b + t) / 2

    if guide_x is not None:
      self.snap_guides_x.append(guide_x)
    if guide_y is not None:
      self.snap_guides_y.append(guide_y)

  # ---------- smart refs (mirror) ----------
  def _smart_refs_x(self, fixed_edge):
    """??????????-??????????????: 2*center_neighbor - fixed_edge. ???????????????? ?????? ??????????????
    ???????? ????????????????, ???? ???????????????? ?????? SMART ?????? ?????????????????? ???????????? ????????????."""
    out = []
    for obj in self.objects:
      if obj in self.selection:
        continue
      bl, br, bb, bt = self._obj_bounds(obj)
      bcx = (bl + br) / 2
      mirror_x = 2 * bcx - fixed_edge
      y_top = bt
      y_bot = bb
      out.append((mirror_x, obj, y_top, y_bot))
    return out

  def _smart_refs_y(self, fixed_edge):
    out = []
    for obj in self.objects:
      if obj in self.selection:
        continue
      bl, br, bb, bt = self._obj_bounds(obj)
      bcy = (bb + bt) / 2
      mirror_y = 2 * bcy - fixed_edge
      x_l = bl
      x_r = br
      out.append((mirror_y, obj, x_l, x_r))
    return out

  # ---------- resize ----------
  def _apply_resize(self, wx, wy, edge, snap):
    if not self._resize_data:
      return
    primary_orig = None
    for obj, r in self._resize_data:
      if obj is self.selected:
        primary_orig = r
        break
    if primary_orig is None:
      primary_orig = self._resize_data[0][1]
    pl, pr, pb, pt = primary_orig

    guide_x = None
    guide_y = None

    if snap:
      near = (pl - SNAP_RANGE, pr + SNAP_RANGE,
              pb - SNAP_RANGE, pt + SNAP_RANGE)
      x_refs = self._gather_x_refs(exclude=self.selection, near=near)
      y_refs = self._gather_y_refs(exclude=self.selection, near=near)

      if edge in ("left", "right"):
        # <STRANGE>#590: mirror-???????? ???????????????????????? ???????????? ????????????
        # fixed = ?????????????????????????????? ????????, ?? ???????????????? ?????????????????????? ??????????????
        fixed = pr if edge == "left" else pl
        smart = self._smart_refs_x(fixed)
        best_d = SNAP_DIST + 1
        best_x = None
        best_smart = None
        for rx in x_refs:
          d = abs(rx - wx)
          if d < best_d:
            best_d = d
            best_x = rx
            best_smart = None
        for mx, mobj, mt, mb in smart:
          d = abs(mx - wx)
          if d < best_d:
            best_d = d
            best_x = mx
            best_smart = (mobj, mt, mb)
        if best_x is not None:
          wx = best_x
          if best_smart is not None:
            mobj, mt, mb = best_smart
            self.smart_guides.append(
              ("mirror_x", best_x, (mt + mb) / 2, "MIRROR"))
          else:
            guide_x = best_x
      elif edge in ("top", "bottom"):
        fixed = pt if edge == "bottom" else pb
        smart = self._smart_refs_y(fixed)
        best_d = SNAP_DIST + 1
        best_y = None
        best_smart = None
        for ry in y_refs:
          d = abs(ry - wy)
          if d < best_d:
            best_d = d
            best_y = ry
            best_smart = None
        for my, mobj, ml, mr in smart:
          d = abs(my - wy)
          if d < best_d:
            best_d = d
            best_y = my
            best_smart = (mobj, ml, mr)
        if best_y is not None:
          wy = best_y
          if best_smart is not None:
            mobj, ml, mr = best_smart
            self.smart_guides.append(
              ("mirror_y", (ml + mr) / 2, best_y, "MIRROR"))
          else:
            guide_y = best_y

    if edge == "right":
      delta = max(wx, pl + MIN_SIZE) - pr
      for obj, (l, r, b, t) in self._resize_data:
        nr = max(r + delta, l + MIN_SIZE)
        obj.w = nr - l
        obj.x = l + obj.w / 2
    elif edge == "left":
      delta = min(wx, pr - MIN_SIZE) - pl
      for obj, (l, r, b, t) in self._resize_data:
        nl = min(l + delta, r - MIN_SIZE)
        obj.w = r - nl
        obj.x = nl + obj.w / 2
    elif edge == "top":
      delta = max(wy, pb + MIN_SIZE) - pt
      for obj, (l, r, b, t) in self._resize_data:
        nt = max(t + delta, b + MIN_SIZE)
        obj.h = nt - b
        obj.y = b + obj.h / 2
    elif edge == "bottom":
      delta = min(wy, pt - MIN_SIZE) - pb
      for obj, (l, r, b, t) in self._resize_data:
        nb = min(b + delta, t - MIN_SIZE)
        obj.h = t - nb
        obj.y = nb + obj.h / 2

    if guide_x is not None:
      self.snap_guides_x.append(guide_x)
    if guide_y is not None:
      self.snap_guides_y.append(guide_y)

  # ---------- drag initiators ----------
  def _begin_move(self, wx, wy, anchor):
    self._move_data = []
    for obj in self.selection:
      if obj.locked:
        continue
      self._move_data.append((obj, obj.x, obj.y, self._obj_bounds(obj)))
    self._move_start = (wx, wy)
    self._move_anchor = anchor
    self.drag = ("move", None)

  def _begin_resize(self, edge):
    self._resize_data = []
    for obj in self.selection:
      if isinstance(obj, (EditorPlatform, EditorBackground)) and not obj.locked:
        self._resize_data.append((obj, obj.world_rect()))
    self.drag = ("resize", edge)
    # <STRANGE>#400: ???????? ???????????? ?????????????????? ??? ????????????????, ?????? ???????????? ????????
    # ?????????????????? ?? ?????????????????? ?????????????????? (editor/settings.json), ?? ???? ?? ???????? ????????.
    if len(self._resize_data) == 1:
      obj = self._resize_data[0][0]
      if isinstance(obj, EditorPlatform):
        self._editor_save_size_kind = "platform"
      elif isinstance(obj, EditorBackground):
        self._editor_save_size_kind = "background"
      else:
        self._editor_save_size_kind = None
    else:
      self._editor_save_size_kind = None

  def _finalize_editor_panel_size(self):
    # <STRANGE>#401: ?????????????????? ???????????? ???????????? ?? ?????????????????? ??????????????????
    kind = getattr(self, "_editor_save_size_kind", None)
    if not kind:
      return
    if self.selected is not None:
      settings.set_panel_size(kind, int(self.selected.w), int(self.selected.h))
    self._editor_save_size_kind = None




  def _finalize_polygon_select_rect(self, additive):
    # <STRANGE>#551: ?????????????????? ?????????? ?? ???????????????? ???????????????????????????? ????????????????
    bg = self.polygon_edit
    if bg is None:
      return
    if self.select_start is None or self.select_now is None:
      return
    x0, y0 = self.select_start
    x1, y1 = self.select_now
    l, r = min(x0, x1), max(x0, x1)
    b, t = min(y0, y1), max(y0, y1)
    if (r - l) < CLICK_THRESHOLD and (t - b) < CLICK_THRESHOLD:
      # ???????? ?????? ???????????????? ??? ?????????? ?????????????????? (shift ???? ????????????????????)
      if not additive:
        bg.active_points = set()
        self._mark_scene_dirty()
      return
    vpts = bg.world_points()
    hits = set()
    for i, (vx, vy) in enumerate(vpts):
      if l <= vx <= r and b <= vy <= t:
        hits.add(i)
    if additive:
      bg.active_points = bg.active_points | hits
    else:
      bg.active_points = hits
    self._mark_scene_dirty()

  def _begin_select_rect(self, wx, wy):
    self.select_start = (wx, wy)
    self.select_now = (wx, wy)
    self.drag = ("select_rect", None)

  # ---------- eraser ----------
  def _erase_at(self, wx, wy):
    removed = False
    keep = []
    for obj in self.objects:
      if not obj.locked and obj.hit(wx, wy):
        if obj in self.selection:
          self.selection.remove(obj)
        removed = True
        continue
      keep.append(obj)
    if removed:
      self.objects = keep
      self.selected = self.selection[-1] if self.selection else None
      self._sync_inspector()
      self._mark_scene_dirty()

  def _erase_segment(self, x0, y0, x1, y1, step=6.0):
    d = math.hypot(x1 - x0, y1 - y0)
    steps = max(1, int(d / step))
    for i in range(steps + 1):
      t = i / steps
      self._erase_at(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)

  # ---------- zone unlock ----------
  def _zone_rect(self):
    if self.zone_start is None or self.zone_now is None:
      return None
    x0, y0 = self.zone_start
    x1, y1 = self.zone_now
    return (min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1))

  def _apply_zone_unlock(self):
    rect = self._zone_rect()
    if rect is None:
      return
    l, r, b, t = rect
    changed = False
    if l == r and b == t:
      for obj in reversed(self.objects):
        if obj.hit(l, b):
          if obj.locked:
            obj.locked = False
            changed = True
          break
    else:
      for obj in self.objects:
        if obj.locked and obj.intersects_rect(l, r, b, t):
          obj.locked = False
          changed = True
    if changed:
      self._mark_scene_dirty()

  # ---------- rubber-band select ----------
  def _select_rect(self):
    if self.select_start is None or self.select_now is None:
      return None
    x0, y0 = self.select_start
    x1, y1 = self.select_now
    return (min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1))

  def _finalize_select_rect(self, ctrl):
    rect = self._select_rect()
    if rect is None:
      return
    l, r, b, t = rect
    if (r - l) < CLICK_THRESHOLD and (t - b) < CLICK_THRESHOLD:
      if not ctrl:
        self._clear_selection()
      return
    hits = [o for o in self.objects if not o.locked and o.intersects_rect(l, r, b, t)]
    if ctrl:
      self._add_to_selection(hits)
    else:
      self._set_selection(hits)

  # ---------- visibility ----------
  def _visible(self, obj, sw, sh):
    if isinstance(obj, (EditorPeg, EditorSpawner)):
      sx, sy = self.to_screen(obj.x, obj.y)
      r = obj.r * self.zoom + 6
      return (sx + r >= 0 and sx - r <= sw and
              sy + r >= 0 and sy - r <= sh)
    l, r, b, t = obj.world_rect()
    x0, y0 = self.to_screen(l, t)
    x1, y1 = self.to_screen(r, b)
    lo_x, hi_x = (x0, x1) if x0 < x1 else (x1, x0)
    lo_y, hi_y = (y0, y1) if y0 < y1 else (y1, y0)
    return (hi_x >= -4 and lo_x <= sw + 4 and
            hi_y >= -4 and lo_y <= sh + 4)