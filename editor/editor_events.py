"""РћР±СЂР°Р±РѕС‚РєР° СЃРѕР±С‹С‚РёР№: РєР»Р°РІРёР°С‚СѓСЂР°, РјС‹С€СЊ, РєРѕРЅС‚РµРєСЃС‚РЅС‹Рµ РјРµРЅСЋ."""
from raylib import (
  GetMousePosition, IsMouseButtonPressed, IsMouseButtonDown,
  IsMouseButtonReleased,
  MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT, MOUSE_BUTTON_MIDDLE,
  GetMouseWheelMove,
  IsKeyPressed, IsKeyDown,
  KEY_LEFT_CONTROL, KEY_RIGHT_CONTROL, KEY_LEFT_SHIFT, KEY_RIGHT_SHIFT,
  KEY_ESCAPE, KEY_DELETE, KEY_BACKSPACE, KEY_SPACE,
  KEY_ONE, KEY_TWO, KEY_THREE, KEY_FOUR, KEY_FIVE, KEY_SIX, KEY_SEVEN,
  KEY_ZERO, KEY_L, KEY_U,
  KEY_A, KEY_C, KEY_D, KEY_O, KEY_S, KEY_V, KEY_Y, KEY_Z,
  GetCharPressed,
)
from .const import BOT_H, MIN_SIZE, ZOOM_STEP, ITEM_TYPES
from .objects import EditorItem, EditorSpawner
from .widgets import ContextMenu


class EventsMixin:
  def handle_mouse(self):
    m = GetMousePosition()
    pos = (m.x, m.y)

    # context menu modal
    if self.context_menu is not None:
      self.context_menu.hover_index(pos)
      if IsMouseButtonPressed(MOUSE_BUTTON_LEFT):
        idx = self.context_menu.hover_index(pos)
        if idx >= 0:
          opt = self.context_menu.options[idx]
          if opt is not None:
            _, value = opt
            self.context_menu.on_select(value)
        self.context_menu = None
      elif IsMouseButtonPressed(MOUSE_BUTTON_RIGHT):
        self.context_menu = None
      return

    # inspector panels (top-first)
    if IsMouseButtonPressed(MOUSE_BUTTON_LEFT):
      for p in reversed(self.inspector_stack):
        if p.on_event("down", pos, 0):
          return
    if IsMouseButtonPressed(MOUSE_BUTTON_RIGHT):
      for p in reversed(self.inspector_stack):
        if p.on_event("down", pos, 1):
          return

    # hover (С‚РѕР»СЊРєРѕ РµСЃР»Рё РЅРёС‡РµРіРѕ РЅРµ Р·Р°Р¶Р°С‚Рѕ)
    if not IsMouseButtonDown(MOUSE_BUTTON_LEFT) and \
       not IsMouseButtonDown(MOUSE_BUTTON_RIGHT):
      handled = False
      for p in reversed(self.inspector_stack):
        if p.on_event("move", pos, -1):
          handled = True
          break
      if not handled:
        self.panel.on_event("move", pos, -1)

    # top panel
    if IsMouseButtonPressed(MOUSE_BUTTON_LEFT):
      if self.panel.on_event("down", pos, 0):
        return
    if IsMouseButtonReleased(MOUSE_BUTTON_LEFT):
      if self.panel.on_event("up", pos, 0):
        return

    # zoom
    wheel = GetMouseWheelMove()
    if wheel != 0:
      if wheel > 0:
        self._zoom_at(pos, self.zoom * ZOOM_STEP)
      elif wheel < 0:
        self._zoom_at(pos, self.zoom / ZOOM_STEP)
      return

    # Р›РљРњ
    if IsMouseButtonPressed(MOUSE_BUTTON_LEFT):
      self.snap_guides_x = []
      self.snap_guides_y = []
      self.begin_undo()
      self.on_mouse_down(pos)
    elif IsMouseButtonReleased(MOUSE_BUTTON_LEFT) or (self.drag is not None and not IsMouseButtonDown(MOUSE_BUTTON_LEFT)):
      self.on_mouse_up(pos)
    elif IsMouseButtonPressed(MOUSE_BUTTON_RIGHT):
      if self._try_open_context_menu(pos):
        return
      self.panning = True
      self.pan_last = pos
    elif IsMouseButtonReleased(MOUSE_BUTTON_RIGHT):
      self.panning = False
    elif IsMouseButtonPressed(MOUSE_BUTTON_MIDDLE):
      self.panning = True
      self.pan_last = pos
    elif IsMouseButtonReleased(MOUSE_BUTTON_MIDDLE):
      self.panning = False

    # РґРІРёР¶РµРЅРёРµ
    if self.panning:
      dx = pos[0] - self.pan_last[0]
      dy = pos[1] - self.pan_last[1]
      self.cam_x -= dx / self.zoom
      self.cam_y += dy / self.zoom
      self.pan_last = pos
    elif self.drag is not None and self.drag[0] == "select_rect":
      self.select_now = self.from_screen(*pos)
    elif self.drag is not None and self.drag[0] == "zone_unlock":
      self.zone_now = self.from_screen(*pos)
    elif self.erasing and IsMouseButtonDown(MOUSE_BUTTON_LEFT):
      wx, wy = self.from_screen(*pos)
      if self._erase_prev is None:
        self._erase_at(wx, wy)
      else:
        px, py = self._erase_prev
        self._erase_segment(px, py, wx, wy)
      self._erase_prev = (wx, wy)
    elif self.drag is not None and IsMouseButtonDown(MOUSE_BUTTON_LEFT):
      self.on_mouse_move(self.from_screen(*pos))

  def on_mouse_up(self, pos):
    ctrl = IsKeyDown(KEY_LEFT_CONTROL) or IsKeyDown(KEY_RIGHT_CONTROL)

    if self.drag is not None and self.drag[0] == "select_rect":
      self._finalize_select_rect(ctrl)
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
    self.snap_guides_x = []
    self.snap_guides_y = []
    self.commit_undo()

  def handle_keyboard(self):
    if any(p.wants_keyboard() for p in self.inspector_stack):
      top = next(p for p in reversed(self.inspector_stack) if p.wants_keyboard())
      ch = GetCharPressed()
      while ch > 0:
        top.handle_text(chr(ch))
        ch = GetCharPressed()
      # РїСЂРѕС…РѕРґРёРј РїРѕ РІСЃРµРј РІРѕР·РјРѕР¶РЅС‹Рј РєРѕРґР°Рј РєР»Р°РІРёС€
      for key in range(512):
        if IsKeyPressed(key):
          top.handle_key(key)
          return
      return

    ctrl = IsKeyDown(KEY_LEFT_CONTROL) or IsKeyDown(KEY_RIGHT_CONTROL)
    shift = IsKeyDown(KEY_LEFT_SHIFT) or IsKeyDown(KEY_RIGHT_SHIFT)

    if ctrl:
      if IsKeyPressed(KEY_Z):
        if shift: self.redo()
        else: self.undo()
        return
      if IsKeyPressed(KEY_Y):
        self.redo(); return
      if IsKeyPressed(KEY_D):
        self.duplicate_selected(); return
      if IsKeyPressed(KEY_C):
        self.copy_selected(); return
      if IsKeyPressed(KEY_V):
        self.paste(); return
      if IsKeyPressed(KEY_S):
        self.save(); return
      if IsKeyPressed(KEY_O):
        self.load(); return
      if IsKeyPressed(KEY_A):
        self._set_selection(list(self.objects)); return
      if IsKeyPressed(KEY_ZERO):
        self.zoom = 1.0
        self.scale = 1.0
        self._rebuild_ghost_assets()
        return
      if IsKeyPressed(KEY_L):
        self.set_tool("peg" if self.tool == "lock" else "lock")
        return

    if IsKeyPressed(KEY_ESCAPE):
      if self.inspector_stack:
        self.pop_inspector()
      else:
        self.running = False
    elif IsKeyPressed(KEY_DELETE) or IsKeyPressed(KEY_BACKSPACE):
      self.delete_selected()
    elif IsKeyPressed(KEY_SPACE):
      self.cam_x, self.cam_y = self.ghost[0], self.ghost[1]
    elif IsKeyPressed(KEY_ONE):
      self.set_tool("ghost")
    elif IsKeyPressed(KEY_TWO):
      self.set_tool("eraser")
    elif IsKeyPressed(KEY_THREE):
      self.set_tool("peg")
    elif IsKeyPressed(KEY_FOUR):
      self.set_tool("platform")
    elif IsKeyPressed(KEY_FIVE):
      self.set_tool("background")
    elif IsKeyPressed(KEY_SIX):
      self.set_tool("item")
    elif IsKeyPressed(KEY_SEVEN):
      self.set_tool("spawner")
    elif IsKeyPressed(KEY_L):
      self.set_tool("lock")
    elif IsKeyPressed(KEY_U):
      self.set_tool("unlock_zone")

  def _try_open_context_menu(self, pos):
    x, y = pos
    _, sh = self.screen_size
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
      title = f"{kind}  В·  layer {cur}" + ("  (default)" if is_default else "")

    options = []
    if not is_group and isinstance(obj, EditorItem):
      options.append(("Change type...", ("change_type", None)))
    if not is_group and isinstance(obj, EditorSpawner):
      options.append(("Open inspector", ("open_inspector", None)))
    if not is_group and isinstance(obj, EditorItem) and obj.item_type == "cube":
      options.append(("Open contents...", ("open_inspector", None)))
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
      if act == "open_inspector":
        self.push_inspector(obj)
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

    self.context_menu = ContextMenu(self.screen_size, options, pos,
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
    title = f"Item type  В·  {item.item_type}"
    self.context_menu = ContextMenu(self.screen_size, options, pos,
                                    on_select, title=title)

  def _open_pick_type_menu(self, pos):
    def on_select(t):
      self.current_item_type = t
    options = [(t, t) for t in ITEM_TYPES]
    title = f"Place item  В·  current: {self.current_item_type}"
    self.context_menu = ContextMenu(self.screen_size, options, pos,
                                    on_select, title=title)