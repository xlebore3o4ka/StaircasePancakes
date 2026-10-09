"""РЇРґСЂРѕ СЂРµРґР°РєС‚РѕСЂР°: __init__, main loop, РєРѕРѕСЂРґРёРЅР°С‚С‹, РєСЌС€ СЃС†РµРЅС‹, inspector stack."""
from raylib import (
  InitWindow, SetTargetFPS, WindowShouldClose, BeginDrawing, EndDrawing,
  ClearBackground, CloseWindow, GetScreenWidth, GetScreenHeight,
  GetMousePosition, SetWindowTitle,
  DrawCircle, DrawCircleLines, DrawRectangle, DrawRectangleLines,
  HideCursor, ShowCursor,
)

from .const import (
  BODY_R, ARM_R, ARM_DX,
  PLAYER_R,
  GHOST_LERP, GHOST_SNAP, GHOST_RETURN_DELAY,
  BOT_H, LAYER_FLOOR, GHOST_LAYER,
  ZOOM_MIN, ZOOM_MAX,
  DEFAULT_ITEM_TYPE, INSPECTOR_MAX_DEPTH,
  BG,
)
from .helpers import C
from .objects import default_layer_for
from .panel import TopPanel


class CoreMixin:
  def __init__(self):
    InitWindow(1280, 800, b"level editor")
    SetTargetFPS(60)
    SetWindowTitle(b"level editor")

    self.screen_size = (GetScreenWidth(), GetScreenHeight())

    self.running = True
    self.tool = "peg"
    self.objects = []

    self.selection = []
    self.selected = None

    self.drag = None
    self._move_data = []
    self._move_start = None
    self._move_anchor = None
    self._resize_data = []

    self.cam_x = 0.0
    self.cam_y = 0.0
    self.zoom = 1.0
    self.scale = 1.0
    self.panning = False
    self.pan_last = (0.0, 0.0)

    self.ghost = [0.0, float(BODY_R)]
    self.ghost_target = [0.0, float(BODY_R)]
    self.ghost_idle = 0.0

    self.erasing = False
    self._erase_prev = None

    self.zone_start = None
    self.zone_now = None
    self.select_start = None
    self.select_now = None

    self.undo_stack = []
    self.redo_stack = []
    self._undo_before = None

    self.clipboard = []

    self.current_item_type = DEFAULT_ITEM_TYPE
    self.context_menu = None

    self.snap_enabled = True
    self.snap_guides_x = []
    self.snap_guides_y = []

    self._scene_dirty = True
    self._render_order = []
    self._locked_list = []

    self.panel = TopPanel(self)
    self.inspector_stack = []

    self._custom_cursor_on = False
    self._ghost_arm_dx = ARM_DX * self.zoom

  # ---------- inspector stack ----------
  def push_inspector(self, owner):
    self._close_all_inspectors()
    from .inspector import InspectorPanel
    self.inspector_stack.append(InspectorPanel(self, owner, depth=0))

  def push_inspector_entry(self, entry):
    if not self.inspector_stack:
      return
    from .inspector import InspectorPanel
    parent = self.inspector_stack[-1]
    depth = parent.depth + 1
    if depth >= INSPECTOR_MAX_DEPTH:
      return
    self.inspector_stack.append(InspectorPanel(self, entry, depth=depth))

  def pop_inspector(self):
    if not self.inspector_stack:
      return
    self.inspector_stack.pop()

  def close_inspector(self, panel):
    if panel not in self.inspector_stack:
      return
    idx = self.inspector_stack.index(panel)
    del self.inspector_stack[idx:]

  def _close_all_inspectors(self):
    self.inspector_stack.clear()

  def _sync_inspector(self):
    from .objects import EditorSpawner, EditorItem
    if isinstance(self.selected, EditorSpawner):
      self.push_inspector(self.selected)
    elif isinstance(self.selected, EditorItem) and self.selected.item_type == "cube":
      self.push_inspector(self.selected)
    else:
      self._close_all_inspectors()

  # ---------- helpers ----------
  def get_mouse_pos(self):
    m = GetMousePosition()
    return (m.x, m.y)

  def _rebuild_ghost_assets(self):
    self._ghost_arm_dx = ARM_DX * self.zoom

  # ---------- zoom ----------
  def _zoom_at(self, screen_pos, new_zoom):
    new_zoom = max(ZOOM_MIN, min(ZOOM_MAX, new_zoom))
    if new_zoom == self.zoom:
      return
    wx, wy = self.from_screen(*screen_pos)
    self.zoom = new_zoom
    self.scale = new_zoom
    sw, sh = self.screen_size
    sx, sy = screen_pos
    self.cam_x = wx - (sx - sw / 2) / self.zoom
    self.cam_y = wy + (sy - sh / 2) / self.zoom
    self._rebuild_ghost_assets()

  # ---------- scene cache ----------
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

  # ---------- coordinates ----------
  def to_screen(self, wx, wy):
    sw, sh = self.screen_size
    return ((wx - self.cam_x) * self.zoom + sw / 2,
            sh / 2 - (wy - self.cam_y) * self.zoom)

  def from_screen(self, sx, sy):
    sw, sh = self.screen_size
    return ((sx - sw / 2) / self.zoom + self.cam_x,
            (sh / 2 - sy) / self.zoom + self.cam_y)

  def _resize_zone_world(self):
    from .const import RESIZE_ZONE
    return RESIZE_ZONE / max(0.01, self.zoom)

  # ---------- custom cursor ----------
  def _draw_custom_cursor(self):
    if self.tool != "lock":
      if self._custom_cursor_on:
        ShowCursor()
        self._custom_cursor_on = False
      return
    if not self._custom_cursor_on:
      HideCursor()
      self._custom_cursor_on = True
    mx, my = self.get_mouse_pos()
    cx, cy = int(mx), int(my)
    DrawCircle(cx, cy, 14, (0, 0, 0, 100))
    body_w, body_h = 14, 11
    bx = cx - body_w // 2
    by = cy - body_h // 2 + 2
    DrawCircleLines(cx, by - 3, 5, (255, 215, 0, 255))
    DrawRectangle(bx, by, body_w, body_h, (255, 215, 0, 255))
    DrawRectangleLines(bx, by, body_w, body_h, (0, 0, 0, 255))
    DrawCircle(cx, by + body_h // 2 - 1, 2, (0, 0, 0, 255))

  # ---------- ghost update ----------
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

  # ---------- main loop ----------
  def run(self):
    while not WindowShouldClose() and self.running:
      dt = 1.0 / 60.0
      self.handle_mouse()
      self.handle_keyboard()

      self.update_cursor()
      self.update_ghost()
      self.panel.update(dt)
      for p in self.inspector_stack:
        p.update(dt)

      BeginDrawing()
      ClearBackground(C(BG))
      self.draw()
      self._draw_custom_cursor()
      EndDrawing()

    if self._custom_cursor_on:
      ShowCursor()
    CloseWindow()

  # ---------- tool ----------
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