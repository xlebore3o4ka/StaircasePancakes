"""Обработка событий: клавиатура, mouse down/up/motion, контекстные меню."""
import pygame

from .const import (
  BOT_H, MIN_SIZE, ZOOM_STEP, ITEM_TYPES, PASTE_OFFSET,
)
from .objects import EditorItem, EditorSpawner
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

    if e.key == pygame.K_ESCAPE:
      if self.inspector_stack:
        self.pop_inspector()
      else:
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
    elif e.key == pygame.K_7:
      self.set_tool("spawner")
    elif e.key == pygame.K_l:
      self.set_tool("lock")
    elif e.key == pygame.K_u:
      self.set_tool("unlock_zone")

  # ---------- context menus ----------
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

  def _open_pick_type_menu(self, pos):
    def on_select(t):
      self.current_item_type = t
    options = [(t, t) for t in ITEM_TYPES]
    title = f"Place item  ·  current: {self.current_item_type}"
    self.context_menu = ContextMenu(self.screen.get_size(), options, pos, on_select, title=title)