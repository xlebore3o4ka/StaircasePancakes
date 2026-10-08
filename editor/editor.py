"""Главный класс редактора уровней."""
import json
import math
import pygame
import tkinter as tk
from tkinter import filedialog

from .const import (
  BODY_R, ARM_R, ARM_DX, JUMP_H,
  PLAYER_R, GHOST_ALPHA, ARM_ALPHA, JUMP_ALPHA,
  GHOST_LERP, GHOST_SNAP, GHOST_RETURN_DELAY,
  BOT_H, BG, GOLD, GREEN, SEL_BLUE, SNAP_COLOR,
  RESIZE_ZONE, MIN_SIZE,
  PLAT_DEFAULT_W, PLAT_DEFAULT_H, PLAT_FILL, PLAT_EDGE,
  BG_DEFAULT_COLOR, BG_FILL,
  UNDO_LIMIT, PASTE_OFFSET, CLICK_THRESHOLD, SNAP_DIST,
  ZOOM_MIN, ZOOM_MAX, ZOOM_STEP,
  LAYER_FLOOR, GHOST_LAYER,
  DEFAULT_ITEM_TYPE,
  ITEM_TYPES,
  PEG_FILL, PEG_EDGE, PEG_R,
  PLAT_EDGE_W,
  CUBE_FILL, CUBE_EDGE, CUBE_EDGE_W,
  SODA_BLUE, SODA_WHITE,
  UI_BG, GREY, PANEL_HEADER_H,
)
from .helpers import (
  render_text, draw_lock_badge,
)
from .objects import (
  EditorPeg, EditorPlatform, EditorBackground, EditorItem,
  default_layer_for, make_fake_item,
)
from .widgets import ContextMenu
from .panel import TopPanel


class _IconCam:
  """Мини-cam для отрисовки предмета в прямоугольнике иконки."""

  def __init__(self, center, scale):
    self._cx, self._cy = center
    self.scale = scale

  def to_screen(self, wx, wy):
    return (self._cx + wx * self.scale,
            self._cy - wy * self.scale)


class Editor:
  def __init__(self):
    pygame.init()
    self.screen = pygame.display.set_mode((1280, 800))
    pygame.display.set_caption("level editor")
    self.clock = pygame.time.Clock()
    self.font = pygame.font.SysFont(None, 22)
    self.running = True
    self.tool = "peg"
    self.objects = []
    # ---- selection ----
    self.selection = []
    self.selected = None
    # ---- drag ----
    self.drag = None
    self._move_data = []
    self._move_start = None
    self._move_anchor = None
    self._resize_data = []
    self._drag_x_refs = []
    self._drag_y_refs = []
    # ---- camera / zoom ----
    self.cam_x = 0
    self.cam_y = 0
    self.zoom = 1.0
    self.scale = 1.0     # алиас zoom для игровых draw_at
    self.panning = False
    self.pan_last = (0, 0)
    # ---- ghost ----
    self.ghost = [0.0, float(BODY_R)]
    self.ghost_target = [0.0, float(BODY_R)]
    self.ghost_idle = 0.0
    # ---- eraser ----
    self.erasing = False
    self._erase_prev = None
    # ---- zone unlock ----
    self.zone_start = None
    self.zone_now = None
    # ---- rubber-band select ----
    self.select_start = None
    self.select_now = None
    # ---- undo/redo ----
    self.undo_stack = []
    self.redo_stack = []
    self._undo_before = None
    # ---- clipboard ----
    self.clipboard = []
    # ---- items ----
    self.current_item_type = DEFAULT_ITEM_TYPE
    self.context_menu = None
    # ---- snap ----
    self.snap_enabled = True
    self.snap_guides_x = []
    self.snap_guides_y = []
    # ---- cursor ----
    self.cursor = None
    self._lock_cursor = self._make_lock_cursor()

    self._rebuild_ghost_assets()

    # ---- render order cache ----
    self._render_order = []
    self._locked_list = []
    self._scene_dirty = True

    self.panel = TopPanel(self)

  # =========================================================
  # Ghost assets (rebuild on zoom change)
  # =========================================================
  def _rebuild_ghost_assets(self):
    body_r = max(1, int(PLAYER_R * self.zoom))
    d = body_r * 2
    body = pygame.Surface((d, d), pygame.SRCALPHA)
    pygame.draw.circle(body, (255, 255, 255, GHOST_ALPHA), (body_r, body_r), body_r)
    self._ghost_body = body
    self._ghost_body_r = body_r

    arm_r = max(1, int(ARM_R * self.zoom))
    ad = arm_r * 2
    arm = pygame.Surface((ad, ad), pygame.SRCALPHA)
    pygame.draw.circle(arm, (255, 255, 255, ARM_ALPHA), (arm_r, arm_r), arm_r)
    self._ghost_arm = arm
    self._ghost_arm_r = arm_r

    self._ghost_arm_dx = ARM_DX * self.zoom

  # =========================================================
  # Zoom
  # =========================================================
  def _zoom_at(self, screen_pos, new_zoom):
    new_zoom = max(ZOOM_MIN, min(ZOOM_MAX, new_zoom))
    if new_zoom == self.zoom:
      return
    wx, wy = self.from_screen(*screen_pos)
    self.zoom = new_zoom
    self.scale = new_zoom
    sw, sh = self.screen.get_size()
    sx, sy = screen_pos
    self.cam_x = wx - (sx - sw / 2) / self.zoom
    self.cam_y = wy + (sy - sh / 2) / self.zoom
    self._rebuild_ghost_assets()

  # =========================================================
  # Scene cache
  # =========================================================
  def _mark_scene_dirty(self):
    self._scene_dirty = True

  def _effective_layer(self, obj):
    if getattr(obj, "layer", None) is not None:
      return obj.layer
    return default_layer_for(obj)

  def _rebuild_scene_lists(self):
    items = []
    locked = []
    for i, obj in enumerate(self.objects):
      items.append((self._effective_layer(obj), i, "obj", obj))
      if obj.locked:
        locked.append(obj)
    items.append((LAYER_FLOOR, -1, "floor", None))
    items.append((GHOST_LAYER, -1, "ghost", None))
    items.sort(key=lambda t: (t[0], t[1]))
    self._render_order = items
    self._locked_list = locked
    self._scene_dirty = False

  # =========================================================
  # Visibility culling
  # =========================================================
  def _visible(self, obj, sw, sh):
    if isinstance(obj, EditorPeg):
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

  # =========================================================
  # Bounds helpers
  # =========================================================
  def _obj_bounds(self, obj):
    if isinstance(obj, EditorPeg):
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
    refs = [0.0]  # пол — всегда доступная цель снэпа
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

  # =========================================================
  # Selection helpers
  # =========================================================
  def _set_selection(self, objs):
    self.selection = [o for o in objs if not o.locked]
    self.selected = self.selection[-1] if self.selection else None

  def _add_to_selection(self, objs):
    for o in objs:
      if not o.locked and o not in self.selection:
        self.selection.append(o)
    self.selected = self.selection[-1] if self.selection else None

  def _toggle_selection(self, obj):
    if obj.locked:
      return
    if obj in self.selection:
      self.selection.remove(obj)
    else:
      self.selection.append(obj)
    self.selected = self.selection[-1] if self.selection else None

  def _clear_selection(self):
    self.selection = []
    self.selected = None

  # =========================================================
  # Undo / redo
  # =========================================================
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
      o = EditorItem(s["x"], s["y"], s.get("item_type", DEFAULT_ITEM_TYPE))
    else:
      return None
    o.locked = s.get("locked", False)
    o.layer = s.get("layer", None)
    return o

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
    self._drag_x_refs = []
    self._drag_y_refs = []
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

  # =========================================================
  # Clipboard & bulk ops
  # =========================================================
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

  # =========================================================
  # Cursors
  # =========================================================
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

  def set_tool(self, name):
    self.ghost_idle = 0.0
    self.tool = name
    self.erasing = False
    self._erase_prev = None
    self.zone_start = None
    self.zone_now = None
    self.select_start = None
    self.select_now = None
    self.snap_guides_x = []
    self.snap_guides_y = []
    self._undo_before = None
    if hasattr(self, "panel"):
      self.panel.sync_tool(name)

  # =========================================================
  # Eraser
  # =========================================================
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
      self._mark_scene_dirty()

  def _erase_segment(self, x0, y0, x1, y1, step=6.0):
    d = math.hypot(x1 - x0, y1 - y0)
    steps = max(1, int(d / step))
    for i in range(steps + 1):
      t = i / steps
      self._erase_at(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)

  # =========================================================
  # Zone unlock
  # =========================================================
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

  # =========================================================
  # Rubber-band select
  # =========================================================
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

  # =========================================================
  # Drag initiators
  # =========================================================
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

  # =========================================================
  # Coordinates
  # =========================================================
  def to_screen(self, wx, wy):
    sw, sh = self.screen.get_size()
    return ((wx - self.cam_x) * self.zoom + sw / 2,
            sh / 2 - (wy - self.cam_y) * self.zoom)

  def from_screen(self, sx, sy):
    sw, sh = self.screen.get_size()
    return ((sx - sw / 2) / self.zoom + self.cam_x,
            (sh / 2 - sy) / self.zoom + self.cam_y)

  def _resize_zone_world(self):
    return RESIZE_ZONE / max(0.01, self.zoom)

  # =========================================================
  # Main loop
  # =========================================================
  def run(self):
    while self.running:
      dt = self.clock.tick(60) / 1000.0
      for e in pygame.event.get():
        self.handle_event(e)
      self.update_cursor()
      self.update_ghost()
      self.panel.update(dt)
      self.draw()
      pygame.display.flip()
    pygame.quit()

  def update_ghost(self):
    dragging = self.drag is not None and self.drag[0] == "ghost"
    if dragging:
      self.ghost_idle = 0.0
    elif self.tool == "ghost":
      self.ghost_idle = 0.0
    else:
      self.ghost_idle += 1 / 60
      if self.ghost_idle >= GHOST_RETURN_DELAY:
        self.ghost_target = [0.0, float(BODY_R)]
    gx, gy = self.ghost
    tx, ty = self.ghost_target
    dx, dy = tx - gx, ty - gy
    if abs(dx) < GHOST_SNAP and abs(dy) < GHOST_SNAP:
      self.ghost[0], self.ghost[1] = tx, ty
    else:
      self.ghost[0] += dx * GHOST_LERP
      self.ghost[1] += dy * GHOST_LERP

  # =========================================================
  # Events
  # =========================================================
  def handle_event(self, e):
    if e.type == pygame.QUIT:
      self.running = False
      return

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

    if self.panel.on_event(e):
      return
    if self.panel.wants_keyboard() and e.type == pygame.KEYDOWN \
       and e.key != pygame.K_ESCAPE:
      return

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
      if self.drag is not None and self.drag[0] == "zone_unlock":
        self._apply_zone_unlock()
      if self.drag is not None and self.drag[0] == "create" and self.selected is not None:
        if self.selected.w < MIN_SIZE:
          self.selected.w = MIN_SIZE
        if self.selected.h < MIN_SIZE:
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

    if e.key == pygame.K_ESCAPE:
      self.running = False
    elif e.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
      self.delete_selected()
    elif e.key == pygame.K_SPACE:
      self.cam_x, self.cam_y = self.ghost[0], self.ghost[1]
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
    elif e.key == pygame.K_l:
      self.set_tool("lock")
    elif e.key == pygame.K_u:
      self.set_tool("unlock_zone")

  # =========================================================
  # Context menus
  # =========================================================
  def _try_open_context_menu(self, pos):
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
    return False

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

    options = []
    if not is_group and isinstance(obj, EditorItem):
      options.append(("Change type...", ("change_type", None)))
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
      if act == "change_type":
        self._open_change_type_menu(obj, pos)
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
    options = [(t, t) for t in ITEM_TYPES]
    title = f"Item type  ·  {item.item_type}"
    self.context_menu = ContextMenu(self.screen.get_size(), options, pos,
                                    on_select, title=title)

  def _open_pick_type_menu(self, pos):
    def on_select(t):
      self.current_item_type = t
    options = [(t, t) for t in ITEM_TYPES]
    title = f"Place item  ·  current: {self.current_item_type}"
    self.context_menu = ContextMenu(self.screen.get_size(), options, pos,
                                    on_select, title=title)

  # =========================================================
  # Mouse down
  # =========================================================
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

  # =========================================================
  # Mouse move
  # =========================================================
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

  # =========================================================
  # Cursor
  # =========================================================
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

  # =========================================================
  # Draw
  # =========================================================
  def draw(self):
    if self._scene_dirty:
      self._rebuild_scene_lists()
    sw, sh = self.screen.get_size()

    self.screen.fill(BG)

    for _layer, _order, kind, obj in self._render_order:
      if kind == "floor":
        self.draw_floor_line()
      elif kind == "ghost":
        self.draw_ghost()
      else:
        if self._visible(obj, sw, sh):
          obj.draw(self.screen, self)

    for obj in self.selection:
      sx, sy = self.to_screen(obj.x, obj.y)
      pygame.draw.circle(self.screen, GREEN, (int(sx), int(sy)), 6)

    self.draw_zone_preview()
    self.draw_select_rect_preview()
    self.draw_snap_guides()

    for obj in self._locked_list:
      bx, by = obj.badge_screen_pos(self)
      draw_lock_badge(self.screen, bx, by)

    self.draw_bottom_bar()
    self.panel.draw(self.screen)
    if self.context_menu is not None:
      self.context_menu.draw(self.screen)

  def draw_snap_guides(self):
    sw, sh = self.screen.get_size()
    for gx in self.snap_guides_x:
      sx, _ = self.to_screen(gx, 0)
      pygame.draw.line(self.screen, SNAP_COLOR, (int(sx), 0), (int(sx), sh), 1)
    for gy in self.snap_guides_y:
      _, sy = self.to_screen(0, gy)
      pygame.draw.line(self.screen, SNAP_COLOR, (0, int(sy)), (sw, int(sy)), 1)

  def draw_zone_preview(self):
    rect = self._zone_rect()
    if rect is None:
      return
    l, r, b, t = rect
    x0, y0 = self.to_screen(l, t)
    x1, y1 = self.to_screen(r, b)
    rr = pygame.Rect(int(min(x0, x1)), int(min(y0, y1)),
                     int(abs(x1 - x0)), int(abs(y1 - y0)))
    if rr.w <= 0 or rr.h <= 0:
      pygame.draw.circle(self.screen, GOLD, rr.topleft, 3)
      return
    overlay = pygame.Surface(rr.size, pygame.SRCALPHA)
    overlay.fill((255, 215, 0, 40))
    self.screen.blit(overlay, rr.topleft)
    pygame.draw.rect(self.screen, GOLD, rr, 2)

  def draw_select_rect_preview(self):
    rect = self._select_rect()
    if rect is None:
      return
    l, r, b, t = rect
    x0, y0 = self.to_screen(l, t)
    x1, y1 = self.to_screen(r, b)
    rr = pygame.Rect(int(min(x0, x1)), int(min(y0, y1)),
                     int(abs(x1 - x0)), int(abs(y1 - y0)))
    if rr.w <= 0 or rr.h <= 0:
      return
    overlay = pygame.Surface(rr.size, pygame.SRCALPHA)
    overlay.fill((100, 200, 255, 50))
    self.screen.blit(overlay, rr.topleft)
    pygame.draw.rect(self.screen, SEL_BLUE, rr, 2)

  def draw_floor_line(self):
    _, y = self.to_screen(0, 0)
    surf = pygame.Surface((self.screen.get_width(), 2), pygame.SRCALPHA)
    surf.fill((255, 255, 255, 90))
    self.screen.blit(surf, (0, y - 1))

  def draw_ghost(self):
    gx, gy = self.ghost
    sx, sy = self.to_screen(gx, gy)

    _, ey = self.to_screen(gx, gy + JUMP_H)
    line_h = max(1, int(sy - ey))
    line = pygame.Surface((2, line_h), pygame.SRCALPHA)
    line.fill((255, 255, 255, JUMP_ALPHA))
    self.screen.blit(line, (int(sx) - 1, int(ey)))
    cap = pygame.Surface((10, 2), pygame.SRCALPHA)
    cap.fill((255, 255, 255, JUMP_ALPHA))
    self.screen.blit(cap, (int(sx) - 5, int(ey) - 1))

    arm_dx = self._ghost_arm_dx
    aw = self._ghost_arm.get_width()
    ah = self._ghost_arm.get_height()
    self.screen.blit(self._ghost_arm, (int(sx - arm_dx) - aw // 2, int(sy) - ah // 2))
    self.screen.blit(self._ghost_arm, (int(sx + arm_dx) - aw // 2, int(sy) - ah // 2))
    body_r = self._ghost_body_r
    self.screen.blit(self._ghost_body, (int(sx) - body_r, int(sy) - body_r))

  def draw_bottom_bar(self):
    h = self.screen.get_height()
    pygame.draw.rect(self.screen, UI_BG, (0, h - BOT_H, self.screen.get_width(), BOT_H))
    self.draw_tab(self.tab_ghost_rect(), "ghost", self.tool == "ghost")
    self.draw_tab(self.tab_eraser_rect(), "eraser", self.tool == "eraser")
    self.draw_tab(self.tab_peg_rect(), "peg", self.tool == "peg")
    self.draw_tab(self.tab_plat_rect(), "platform", self.tool == "platform")
    self.draw_tab(self.tab_bg_rect(), "background", self.tool == "background")
    self.draw_tab(self.tab_item_rect(), "item", self.tool == "item")

    z = f"{int(self.zoom * 100)}%"
    surf = render_text(self.font, z, GOLD)
    self.screen.blit(surf, (self.screen.get_width() - surf.get_width() - 14,
                            h - BOT_H + (BOT_H - surf.get_height()) // 2))

  def draw_tab(self, r, name, active):
    pygame.draw.rect(self.screen, (45, 50, 60), r)
    color = GOLD if active else GREY
    pygame.draw.rect(self.screen, color, r, 3 if active else 2)
    cx, cy = r.center
    if name == "peg":
      pygame.draw.circle(self.screen, PEG_FILL, (cx, cy), PEG_R)
      pygame.draw.circle(self.screen, PEG_EDGE, (cx, cy), PEG_R, 4)
    elif name == "background":
      rr = pygame.Rect(0, 0, 100, 40)
      rr.center = r.center
      pygame.draw.rect(self.screen, BG_DEFAULT_COLOR, rr)
    elif name == "ghost":
      ar = max(4, ARM_R // 2)
      br = max(6, PLAYER_R // 2)
      pygame.draw.circle(self.screen, (255, 255, 255), (cx - br - ar - 1, cy), ar)
      pygame.draw.circle(self.screen, (255, 255, 255), (cx + br + ar + 1, cy), ar)
      pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), br)
    elif name == "eraser":
      rr = pygame.Rect(0, 0, 84, 32)
      rr.center = r.center
      pygame.draw.rect(self.screen, (240, 150, 170), rr, border_radius=4)
      band = pygame.Rect(rr.x, rr.centery - 4, rr.w, 8)
      pygame.draw.rect(self.screen, (200, 90, 120), band)
      pygame.draw.rect(self.screen, (60, 60, 70), rr, 2, border_radius=4)
    elif name == "item":
      self._draw_item_icon(self.screen, r, self.current_item_type)
    else:
      rr = pygame.Rect(0, 0, 100, 40)
      rr.center = r.center
      pygame.draw.rect(self.screen, PLAT_FILL, rr)
      pygame.draw.rect(self.screen, PLAT_EDGE, rr, PLAT_EDGE_W)

  def _draw_item_icon(self, screen, r, item_type):
    game = make_fake_item(item_type)
    if game is None:
      ir = pygame.Rect(0, 0, 60, 32)
      ir.center = r.center
      pygame.draw.rect(screen, (200, 180, 120), ir)
      pygame.draw.rect(screen, (80, 70, 50), ir, 2)
      return

    box_w, box_h = 60, 40
    sx = box_w / max(1, game.w)
    sy = box_h / max(1, game.h)
    scale = min(sx, sy)

    cam = _IconCam(r.center, scale)
    game.draw_at(screen, cam, (0, 0), 0.0, 255, 1.0)

  # =========================================================
  # Bottom tabs
  # =========================================================
  def tab_ghost_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(10, h - BOT_H + 6, 120, BOT_H - 12)

  def tab_eraser_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(140, h - BOT_H + 6, 120, BOT_H - 12)

  def tab_peg_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(270, h - BOT_H + 6, 120, BOT_H - 12)

  def tab_plat_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(400, h - BOT_H + 6, 120, BOT_H - 12)

  def tab_bg_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(530, h - BOT_H + 6, 120, BOT_H - 12)

  def tab_item_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(660, h - BOT_H + 6, 120, BOT_H - 12)

  # =========================================================
  # Save / Load
  # =========================================================
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
    with open(path, "w") as f:
      json.dump({
        "pegs": pegs,
        "platforms": platforms,
        "backgrounds": backgrounds,
        "items": items,
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
      obj = EditorPlatform(pd["x"], pd["y"], pd.get("w", PLAT_DEFAULT_W), pd.get("h", PLAT_DEFAULT_H))
      obj.fill = tuple(pd.get("fill", PLAT_FILL))
      obj.edge = tuple(pd.get("edge", PLAT_EDGE))
      obj.locked = bool(pd.get("locked", False))
      if "layer" in pd:
        obj.layer = int(pd["layer"])
      self.objects.append(obj)
    for bd in data.get("backgrounds", []):
      obj = EditorBackground(bd["x"], bd["y"], bd.get("w", PLAT_DEFAULT_W), bd.get("h", PLAT_DEFAULT_H))
      obj.fill = tuple(bd.get("color", BG_DEFAULT_COLOR))
      obj.locked = bool(bd.get("locked", False))
      if "layer" in bd:
        obj.layer = int(bd["layer"])
      self.objects.append(obj)
    for it in data.get("items", []):
      obj = EditorItem(it["x"], it["y"], it.get("type", DEFAULT_ITEM_TYPE))
      obj.locked = bool(it.get("locked", False))
      if "layer" in it:
        obj.layer = int(it["layer"])
      self.objects.append(obj)
    self._clear_selection()
    self._mark_scene_dirty()
    self._push_undo_now(before)