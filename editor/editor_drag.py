"""Мышь, drag/resize/create, ластик, зона разблокировки, snap, курсор."""
import math
import pygame

from .const import (
  BOT_H, MIN_SIZE, SNAP_DIST, PLAYER_R,
  CLICK_THRESHOLD, RESIZE_ZONE,
)
from .objects import (
  EditorPeg, EditorPlatform, EditorBackground, EditorItem, EditorSpawner,
)


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

  def _gather_x_refs(self, exclude=()):
    refs = []
    for obj in self.objects:
      if obj in exclude:
        continue
      l, r, b, t = self._obj_bounds(obj)
      refs.append(l)
      refs.append((l + r) / 2)
      refs.append(r)
    return refs

  def _gather_y_refs(self, exclude=()):
    refs = [0.0]
    for obj in self.objects:
      if obj in exclude:
        continue
      l, r, b, t = self._obj_bounds(obj)
      refs.append(b)
      refs.append((b + t) / 2)
      refs.append(t)
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

  # ---------- mouse down ----------
  def on_mouse_down(self, pos):
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
    alt = bool(pygame.key.get_mods() & pygame.KMOD_ALT)
    snap = self.snap_enabled and not alt

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
    guide_x = None
    guide_y = None

    if snap and primary_orig is not None:
      pl, pr, pb, pt = primary_orig
      moved_x = [pl + raw_dx, (pl + pr) / 2 + raw_dx, pr + raw_dx]
      moved_y = [pb + raw_dy, (pb + pt) / 2 + raw_dy, pt + raw_dy]

      x_refs = self._drag_x_refs
      y_refs = self._drag_y_refs

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
        guide_x = best_x_guide

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
        guide_y = best_y_guide

    for obj, ox, oy, _ in self._move_data:
      if obj.locked:
        continue
      obj.x = ox + snap_dx
      obj.y = oy + snap_dy

    if guide_x is not None:
      self.snap_guides_x.append(guide_x)
    if guide_y is not None:
      self.snap_guides_y.append(guide_y)

  def _apply_create(self, wx, wy, ox, oy, snap):
    guide_x = None
    guide_y = None
    if snap:
      x_refs = self._drag_x_refs if self._drag_x_refs else self._gather_x_refs(exclude=self.selection)
      y_refs = self._drag_y_refs if self._drag_y_refs else self._gather_y_refs(exclude=self.selection)
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
      x_refs = self._drag_x_refs
      y_refs = self._drag_y_refs
      if edge in ("left", "right"):
        wx, hit = self._snap_value(wx, x_refs)
        if hit:
          guide_x = wx
      elif edge in ("top", "bottom"):
        wy, hit = self._snap_value(wy, y_refs)
        if hit:
          guide_y = wy

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
    self._drag_x_refs = self._gather_x_refs(exclude=self.selection)
    self._drag_y_refs = self._gather_y_refs(exclude=self.selection)

  def _begin_resize(self, edge):
    self._resize_data = []
    for obj in self.selection:
      if isinstance(obj, (EditorPlatform, EditorBackground)) and not obj.locked:
        self._resize_data.append((obj, obj.world_rect()))
    self.drag = ("resize", edge)
    self._drag_x_refs = self._gather_x_refs(exclude=self.selection)
    self._drag_y_refs = self._gather_y_refs(exclude=self.selection)

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