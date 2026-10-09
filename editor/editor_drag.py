"""Мышь-логика: выделение, drag/resize, ластик, зона, snap, курсор."""
import math
from raylib import (
  SetMouseCursor,
  MOUSE_CURSOR_DEFAULT, MOUSE_CURSOR_CROSSHAIR,
  MOUSE_CURSOR_RESIZE_EW, MOUSE_CURSOR_RESIZE_NS,
)

from .const import (
  BOT_H, MIN_SIZE, SNAP_DIST, SNAP_RANGE, PLAYER_R,
  CLICK_THRESHOLD,
)
from .objects import (
  EditorPeg, EditorPlatform, EditorBackground, EditorItem, EditorSpawner,
)


class DragMixin:
  def update_cursor(self):
    if self.tool == "eraser":
      SetMouseCursor(MOUSE_CURSOR_CROSSHAIR); return
    if self.tool == "unlock_zone":
      SetMouseCursor(MOUSE_CURSOR_CROSSHAIR); return
    if self.tool == "lock":
      SetMouseCursor(MOUSE_CURSOR_DEFAULT); return

    want = MOUSE_CURSOR_DEFAULT
    if isinstance(self.selected, (EditorPlatform, EditorBackground)) \
       and not self.selected.locked:
      mx, my = self.get_mouse_pos()
      wx, wy = self.from_screen(mx, my)
      edge = self.selected.edge_hit(wx, wy, self._resize_zone_world())
      if edge in ("left", "right"):
        want = MOUSE_CURSOR_RESIZE_EW
      elif edge in ("top", "bottom"):
        want = MOUSE_CURSOR_RESIZE_NS
    SetMouseCursor(want)

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
      refs.append(l); refs.append((l + r) / 2); refs.append(r)
    return refs

  def _gather_y_refs(self, exclude=(), near=None):
    refs = [0.0]
    for obj in self.objects:
      if obj in exclude:
        continue
      l, r, b, t = self._obj_bounds(obj)
      if near is not None:
        nl, nr, nb, nt = near
        if r < nl or l > nr or t < nb or b > nt:
          continue
      refs.append(b); refs.append((b + t) / 2); refs.append(t)
    return refs

  @staticmethod
  def _snap_value(value, refs):
    best = value
    best_d = SNAP_DIST + 1
    for r in refs:
      d = abs(r - value)
      if d < best_d:
        best_d = d; best = r
    if best_d <= SNAP_DIST:
      return best, True
    return value, False

  # ---------- mouse down ----------
  def on_mouse_down(self, pos):
    x, y = pos
    _, sh = self.screen_size

    if y >= sh - BOT_H:
      if self.tab_ghost_rect() and self._hit_rect(pos, self.tab_ghost_rect()): self.set_tool("ghost")
      elif self._hit_rect(pos, self.tab_eraser_rect()): self.set_tool("eraser")
      elif self._hit_rect(pos, self.tab_peg_rect()): self.set_tool("peg")
      elif self._hit_rect(pos, self.tab_plat_rect()): self.set_tool("platform")
      elif self._hit_rect(pos, self.tab_bg_rect()): self.set_tool("background")
      elif self._hit_rect(pos, self.tab_item_rect()): self.set_tool("item")
      elif self._hit_rect(pos, self.tab_spawner_rect()): self.set_tool("spawner")
      return

    wx, wy = self.from_screen(x, y)
    ctrl = self._key_down_ctrl()
    shift = self._key_down_shift()
    zone = self._resize_zone_world()

    if shift:
      if isinstance(self.selected, (EditorPlatform, EditorBackground)) \
         and not self.selected.locked:
        edge = self.selected.edge_hit(wx, wy, zone)
        if edge:
          self._begin_resize(edge); return
      hit = None
      for obj in reversed(self.objects):
        if obj.locked: continue
        if obj.hit(wx, wy):
          hit = obj; break
      if hit is not None:
        if ctrl:
          self._toggle_selection(hit); return
        if hit not in self.selection:
          self._set_selection([hit])
        self._begin_move(wx, wy, hit); return
      self._begin_select_rect(wx, wy); return

    if self.tool == "unlock_zone":
      self.drag = ("zone_unlock", None)
      self.zone_start = (wx, wy); self.zone_now = (wx, wy); return
    if self.tool == "eraser":
      self.erasing = True
      self._erase_prev = (wx, wy)
      self._erase_at(wx, wy); return
    if self.tool == "lock":
      for obj in reversed(self.objects):
        if obj.hit(wx, wy):
          obj.locked = not obj.locked
          if obj.locked and obj in self.selection:
            self.selection.remove(obj)
            self.selected = self.selection[-1] if self.selection else None
            self._sync_inspector()
          self._mark_scene_dirty(); return
      return

    if isinstance(self.selected, (EditorPlatform, EditorBackground)) \
       and not self.selected.locked:
      edge = self.selected.edge_hit(wx, wy, zone)
      if edge:
        self._begin_resize(edge); return

    hit = None
    for obj in reversed(self.objects):
      if obj.locked: continue
      if obj.hit(wx, wy):
        hit = obj; break

    if hit is not None:
      if ctrl:
        self._toggle_selection(hit); return
      if hit not in self.selection:
        self._set_selection([hit])
      self._begin_move(wx, wy, hit); return

    gx, gy = self.ghost
    if (wx - gx) ** 2 + (wy - gy) ** 2 <= PLAYER_R ** 2:
      self.drag = ("ghost", (wx - gx, wy - gy)); return
    if self.tool == "ghost":
      self.ghost_target = [wx, wy]; return

    if self.tool == "peg":
      obj = EditorPeg(wx, wy)
      self.objects.append(obj)
      self._set_selection([obj])
      self._begin_move(wx, wy, obj)
      self._mark_scene_dirty()
    elif self.tool in ("platform", "background"):
      obj = (EditorBackground(wx, wy, 1, 1) if self.tool == "background"
             else EditorPlatform(wx, wy, 1, 1))
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

  def _hit_rect(self, pos, r):
    return r[0] <= pos[0] < r[0] + r[2] and r[1] <= pos[1] < r[1] + r[3]

  # ---------- mouse move ----------
  def on_mouse_move(self, world):
    wx, wy = world
    if self.drag is None: return
    mode, data = self.drag
    self.snap_guides_x = []; self.snap_guides_y = []
    snap = self.snap_enabled and not self._key_down_alt()
    if mode == "move": self._apply_move(wx, wy, snap)
    elif mode == "ghost":
      dx, dy = data
      self.ghost[0] = wx - dx; self.ghost[1] = wy - dy
      self.ghost_target = [self.ghost[0], self.ghost[1]]
    elif mode == "create":
      ox, oy = data
      self._apply_create(wx, wy, ox, oy, snap)
    elif mode == "resize":
      self._apply_resize(wx, wy, data, snap)

  def _apply_move(self, wx, wy, snap):
    if not self._move_data or self._move_start is None:
      return
    sx, sy = self._move_start
    raw_dx, raw_dy = wx - sx, wy - sy

    anchor = self._move_anchor
    primary_orig = None
    for obj, _, _, b in self._move_data:
      if obj is anchor:
        primary_orig = b; break
    if primary_orig is None and self._move_data:
      primary_orig = self._move_data[0][3]

    snap_dx, snap_dy = raw_dx, raw_dy

    if snap and primary_orig is not None:
      l0 = r0 = b0 = t0 = None
      for obj, ox, oy, (bl, br, bb, bt) in self._move_data:
        nl, nr = bl + raw_dx, br + raw_dx
        nb, nt = bb + raw_dy, bt + raw_dy
        l0 = nl if l0 is None else min(l0, nl)
        r0 = nr if r0 is None else max(r0, nr)
        b0 = nb if b0 is None else min(b0, nb)
        t0 = nt if t0 is None else max(t0, nt)
      near = (l0 - SNAP_RANGE, r0 + SNAP_RANGE,
              b0 - SNAP_RANGE, t0 + SNAP_RANGE)

      x_refs = self._gather_x_refs(exclude=self.selection, near=near)
      y_refs = self._gather_y_refs(exclude=self.selection, near=near)

      pl, pr, pb, pt = primary_orig
      moved_x = [pl + raw_dx, (pl + pr) / 2 + raw_dx, pr + raw_dx]
      moved_y = [pb + raw_dy, (pb + pt) / 2 + raw_dy, pt + raw_dy]

      best_x_d, best_x_diff, best_x = SNAP_DIST + 1, 0, None
      for mx in moved_x:
        for rx in x_refs:
          d = abs(rx - mx)
          if d < best_x_d:
            best_x_d, best_x_diff, best_x = d, rx - mx, rx
      if best_x is not None:
        snap_dx = raw_dx + best_x_diff
        self.snap_guides_x.append(best_x)

      best_y_d, best_y_diff, best_y = SNAP_DIST + 1, 0, None
      for my in moved_y:
        for ry in y_refs:
          d = abs(ry - my)
          if d < best_y_d:
            best_y_d, best_y_diff, best_y = d, ry - my, ry
      if best_y is not None:
        snap_dy = raw_dy + best_y_diff
        self.snap_guides_y.append(best_y)

    for obj, ox, oy, _ in self._move_data:
      if obj.locked: continue
      obj.x = ox + snap_dx
      obj.y = oy + snap_dy

  def _apply_create(self, wx, wy, ox, oy, snap):
    guide_x = guide_y = None
    if snap:
      near = (min(ox, wx) - SNAP_RANGE, max(ox, wx) + SNAP_RANGE,
              min(oy, wy) - SNAP_RANGE, max(oy, wy) + SNAP_RANGE)
      x_refs = self._gather_x_refs(exclude=self.selection, near=near)
      y_refs = self._gather_y_refs(exclude=self.selection, near=near)
      wx, hx = self._snap_value(wx, x_refs)
      if hx: guide_x = wx
      wy, hy = self._snap_value(wy, y_refs)
      if hy: guide_y = wy

    l, r = min(ox, wx), max(ox, wx)
    b, t = min(oy, wy), max(oy, wy)
    obj = self.selected
    if obj is None: return
    obj.w = max(r - l, 1); obj.h = max(t - b, 1)
    obj.x = (l + r) / 2; obj.y = (b + t) / 2
    if guide_x is not None: self.snap_guides_x.append(guide_x)
    if guide_y is not None: self.snap_guides_y.append(guide_y)

  def _apply_resize(self, wx, wy, edge, snap):
    if not self._resize_data: return
    primary_orig = None
    for obj, r in self._resize_data:
      if obj is self.selected:
        primary_orig = r; break
    if primary_orig is None:
      primary_orig = self._resize_data[0][1]
    pl, pr, pb, pt = primary_orig
    guide_x = guide_y = None
    if snap:
      near = (pl - SNAP_RANGE, pr + SNAP_RANGE,
              pb - SNAP_RANGE, pt + SNAP_RANGE)
      x_refs = self._gather_x_refs(exclude=self.selection, near=near)
      y_refs = self._gather_y_refs(exclude=self.selection, near=near)
      if edge in ("left", "right"):
        wx, h = self._snap_value(wx, x_refs)
        if h: guide_x = wx
      elif edge in ("top", "bottom"):
        wy, h = self._snap_value(wy, y_refs)
        if h: guide_y = wy

    if edge == "right":
      delta = max(wx, pl + MIN_SIZE) - pr
      for obj, (l, r, b, t) in self._resize_data:
        nr = max(r + delta, l + MIN_SIZE)
        obj.w = nr - l; obj.x = l + obj.w / 2
    elif edge == "left":
      delta = min(wx, pr - MIN_SIZE) - pl
      for obj, (l, r, b, t) in self._resize_data:
        nl = min(l + delta, r - MIN_SIZE)
        obj.w = r - nl; obj.x = nl + obj.w / 2
    elif edge == "top":
      delta = max(wy, pb + MIN_SIZE) - pt
      for obj, (l, r, b, t) in self._resize_data:
        nt = max(t + delta, b + MIN_SIZE)
        obj.h = nt - b; obj.y = b + obj.h / 2
    elif edge == "bottom":
      delta = min(wy, pt - MIN_SIZE) - pb
      for obj, (l, r, b, t) in self._resize_data:
        nb = min(b + delta, t - MIN_SIZE)
        obj.h = t - nb; obj.y = nb + obj.h / 2

    if guide_x is not None: self.snap_guides_x.append(guide_x)
    if guide_y is not None: self.snap_guides_y.append(guide_y)

  def _begin_move(self, wx, wy, anchor):
    self._move_data = []
    for obj in self.selection:
      if obj.locked: continue
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

  def _begin_select_rect(self, wx, wy):
    self.select_start = (wx, wy)
    self.select_now = (wx, wy)
    self.drag = ("select_rect", None)

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

  def _zone_rect(self):
    if self.zone_start is None or self.zone_now is None:
      return None
    x0, y0 = self.zone_start; x1, y1 = self.zone_now
    return (min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1))

  def _apply_zone_unlock(self):
    rect = self._zone_rect()
    if rect is None: return
    l, r, b, t = rect
    changed = False
    if l == r and b == t:
      for obj in reversed(self.objects):
        if obj.hit(l, b):
          if obj.locked:
            obj.locked = False; changed = True
          break
    else:
      for obj in self.objects:
        if obj.locked and obj.intersects_rect(l, r, b, t):
          obj.locked = False; changed = True
    if changed: self._mark_scene_dirty()

  def _select_rect(self):
    if self.select_start is None or self.select_now is None:
      return None
    x0, y0 = self.select_start; x1, y1 = self.select_now
    return (min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1))

  def _finalize_select_rect(self, ctrl):
    rect = self._select_rect()
    if rect is None: return
    l, r, b, t = rect
    if (r - l) < CLICK_THRESHOLD and (t - b) < CLICK_THRESHOLD:
      if not ctrl:
        self._clear_selection()
      return
    hits = [o for o in self.objects if not o.locked and o.intersects_rect(l, r, b, t)]
    if ctrl: self._add_to_selection(hits)
    else: self._set_selection(hits)

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

  def _key_down_ctrl(self):
    from raylib import IsKeyDown, KEY_LEFT_CONTROL, KEY_RIGHT_CONTROL
    return IsKeyDown(KEY_LEFT_CONTROL) or IsKeyDown(KEY_RIGHT_CONTROL)

  def _key_down_shift(self):
    from raylib import IsKeyDown, KEY_LEFT_SHIFT, KEY_RIGHT_SHIFT
    return IsKeyDown(KEY_LEFT_SHIFT) or IsKeyDown(KEY_RIGHT_SHIFT)

  def _key_down_alt(self):
    from raylib import IsKeyDown, KEY_LEFT_ALT, KEY_RIGHT_ALT
    return IsKeyDown(KEY_LEFT_ALT) or IsKeyDown(KEY_RIGHT_ALT)