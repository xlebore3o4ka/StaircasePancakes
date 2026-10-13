"""Ядро редактора: __init__, main loop, координаты, кэш сцены, inspector stack."""
import math
import pygame

from .const import (
  BODY_R, ARM_R, ARM_DX, JUMP_H,
  PLAYER_R, GHOST_ALPHA, ARM_ALPHA,
  GHOST_LERP, GHOST_SNAP, GHOST_RETURN_DELAY,
  BOT_H, LAYER_FLOOR, GHOST_LAYER,
  ZOOM_MIN, ZOOM_MAX,
  DEFAULT_ITEM_TYPE, DEFAULT_ARTIFACT_TYPE,
)
from .objects import default_layer_for
from .messages import MessageStore, WARN, INFO, ERROR, DEFERRED
from . import settings as _editor_settings
try:
  from shared import version as _game_version
except Exception:
  _game_version = None

def _game_version_read():
  if _game_version is None:
    return "0.0.0"
  try:
    return str(_game_version.read())
  except Exception:
    return "0.0.0"

def _version_parse(v):
  try:
    parts = str(v).split(".")
    nums = [int(p) for p in parts[:3]]
    while len(nums) < 3:
      nums.append(0)
    return tuple(nums)
  except Exception:
    return (0, 0, 0)

def _version_incompatible(level_v, game_v):
  lv = _version_parse(level_v)
  gv = _version_parse(game_v)
  return (lv[0], lv[1]) != (gv[0], gv[1]) and lv > gv
from .panel import TopPanel


class CoreMixin:
  def __init__(self):
    pygame.init()
    # <STRANGE>#1100: bigger window so all tabs + zoom indicator fit
    self.screen = pygame.display.set_mode((1440, 820))
    pygame.display.set_caption("level editor")
    self.clock = pygame.time.Clock()
    self.font = pygame.font.SysFont(None, 22)
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

    self.cam_x = 0
    self.cam_y = 0
    self.zoom = 1.0
    self.scale = 1.0
    self.panning = False
    self.pan_last = (0, 0)

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
    self.current_artifact_type = DEFAULT_ARTIFACT_TYPE
    self.context_menu = None

    self.snap_enabled = True
    self.snap_guides_x = []
    self.snap_guides_y = []
    # <STRANGE>#580: smart-?????????????????? (CENTER/CORNER/TOUCH)
    self.smart_guides = []

    self.cursor = None
    self._lock_cursor = self._make_lock_cursor()

    self._rebuild_ghost_assets()

    self._render_order = []
    self._locked_list = []
    self._scene_dirty = True

    self.level_version = _game_version_read()
    self.loaded_version = None
    self.version_warning = ""
    self.version_warning_t = 0.0
    self.version_warning_total = 3.6
    self.version_input_visible = False
    self.version_input_text = self.level_version
    self.messages = MessageStore()
    # <STRANGE>#1061: files embedded into the level tar (name -> bytes)
    self.embedded_files = {}
    # <STRANGE>#1091: ignore input until this timestamp (ms)
    self._swallow_events_until = 0
    # <STRANGE>#1031: per-artifact-type history of past positions
    self._artifact_history = {}
    # list of {kind, x, y, t} markers drawn in the world (info dots etc)
    self.world_markers = []
    self.panel = TopPanel(self)
    self.inspector_stack = []
    # <STRANGE>#560: grid step (?????? ?? rbxl studio) ??? ?????????????? ??????????
    self.grid_enabled = False
    self.grid_step = 10
    self.grid_step_angle = 15
    # <STRANGE>#508: ?????????????????????????? ?????????????????????????? ?????? (?????? None)
    self.polygon_edit = None

  # ---------- rotate arcs ----------
  def _rotate_arc_centers(self, bg):
    """???????????????????? (center_tl, center_br) ?? ???????????????? ?????????????????????? ?? ????????????."""
    from .const import ROTATE_ARC_R, ROTATE_ARC_OFF
    l, r, b, t = bg.world_rect()
    x0, y0 = self.to_screen(l, t)
    x1, y1 = self.to_screen(r, b)
    # ???????????? ?????????????? ???????? ??? ?????????????? ???? ??????????????????
    c_tl = (x1 + ROTATE_ARC_OFF, y0 - ROTATE_ARC_OFF)
    # ?????????? ???????????? ????????
    c_br = (x0 - ROTATE_ARC_OFF, y1 + ROTATE_ARC_OFF)
    return c_tl, c_br, ROTATE_ARC_R

  def _rotate_arc_hit(self, pos):
    """???????? pos ?????????? ?? ???????? ???? ?????? ??? ???????????? 'tl'/'br', ?????????? None."""
    from .objects import EditorBackground, EditorPlatform
    bg = self.selected
    if not isinstance(bg, (EditorBackground, EditorPlatform)):
      return None
    if bg.locked:
      return None
    if self.polygon_edit is not None:
      return None
    c_tl, c_br, rr = self._rotate_arc_centers(bg)
    x, y = pos
    r2 = rr * rr
    if (x - c_tl[0]) ** 2 + (y - c_tl[1]) ** 2 <= r2:
      return "tl"
    if (x - c_br[0]) ** 2 + (y - c_br[1]) ** 2 <= r2:
      return "br"
    return None

  # ---------- polygon edit ----------
  def enter_polygon_edit(self, bg):
    # <STRANGE>#509: ???????? ?? ?????????? ???????????? ????????????
    if bg is None or not getattr(bg, "polygon", False):
      return
    self._close_all_inspectors()
    self.polygon_edit = bg
    bg.active_points = set()
    self._mark_scene_dirty()

  def exit_polygon_edit(self):
    if self.polygon_edit is not None:
      self.polygon_edit.active_points = set()
    self.polygon_edit = None
    self._mark_scene_dirty()

  def toggle_polygon_edit(self):
    # <STRANGE>#510: ???????????? Poly ??? ????????/?????????? ?????? ?????????????????????? ????????
    if self.polygon_edit is not None:
      self.exit_polygon_edit()
      return
    from .objects import EditorBackground, EditorPlatform
    b = self.selected
    if not isinstance(b, (EditorBackground, EditorPlatform)):
      return
    if not b.polygon:
      b.to_polygon()
    self.enter_polygon_edit(b)

  # ---------- inspector stack ----------
  def push_inspector(self, owner):
    self._close_all_inspectors()
    from .inspector import InspectorPanel
    self.inspector_stack.append(InspectorPanel(self, owner, depth=0))

  def push_inspector_entry(self, entry):
    if not self.inspector_stack:
      return
    from .inspector import InspectorPanel
    from .const import INSPECTOR_MAX_DEPTH
    parent = self.inspector_stack[-1]
    depth = parent.depth + 1
    if depth >= INSPECTOR_MAX_DEPTH:
      return
    self.inspector_stack.append(InspectorPanel(self, entry, depth=depth))

  def pop_inspector(self):
    if not self.inspector_stack:
      return
    self.inspector_stack.pop()

  def _close_all_inspectors(self):
    self.inspector_stack.clear()

  # ---------- ghost assets ----------
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

  # ---------- zoom ----------
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
      if obj is None:
        continue
      items.append((self._effective_layer(obj), i, "obj", obj))
      if getattr(obj, "locked", False):
        locked.append(obj)
    items.append((LAYER_FLOOR, -1, "floor", None))
    items.append((GHOST_LAYER, -1, "ghost", None))
    items.sort(key=lambda t: (t[0], t[1]))
    self._render_order = items
    self._locked_list = locked
    self._scene_dirty = False

  # ---------- coordinates ----------
  def to_screen(self, wx, wy):
    sw, sh = self.screen.get_size()
    return ((wx - self.cam_x) * self.zoom + sw / 2,
            sh / 2 - (wy - self.cam_y) * self.zoom)

  def from_screen(self, sx, sy):
    sw, sh = self.screen.get_size()
    return ((sx - sw / 2) / self.zoom + self.cam_x,
            (sh / 2 - sy) / self.zoom + self.cam_y)

  def _resize_zone_world(self):
    from .const import RESIZE_ZONE
    return RESIZE_ZONE / max(0.01, self.zoom)

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

  # ---------- level version ----------
  def _refresh_version_warning(self):
    game_v = _game_version_read()
    if _version_incompatible(self.level_version, game_v):
      self.version_warning = "level %s > game %s" % (self.level_version, game_v)
      self.version_warning_t = self.version_warning_total
    else:
      self.version_warning = ""
      self.version_warning_t = 0.0

  def _set_level_version(self, v):
    v = (v or "").strip() or _game_version_read()
    self.level_version = v
    self.version_input_text = v
    self._refresh_version_warning()

  def _tick_version_warning(self, dt):
    if self.version_warning_t > 0.0:
      self.version_warning_t = max(0.0, self.version_warning_t - dt)

  def _flush_pygame_events(self):
    # <STRANGE>#1090: after tkinter dialogs SDL has queued events.
    # Drop them all and swallow the first frames of input.
    try:
      pygame.event.clear()
      pygame.event.pump()
      pygame.event.clear()
    except Exception:
      pass
    self._swallow_events_until = pygame.time.get_ticks() + 150

  def _tick_world_markers(self, dt):
    alive = []
    for m in self.world_markers:
      m["t"] -= dt
      if m["t"] > 0:
        alive.append(m)
    self.world_markers = alive

  def _recompute_messages(self):
    # <STRANGE>#1003: scan for duplicate non-empty ids among all objects
    id_map = {}
    for o in self.objects:
      oid = getattr(o, "id", "")
      if oid:
        id_map.setdefault(oid, []).append(o)
      # also scan spawner entries
      if hasattr(o, "items"):
        for e in o.items:
          eid = e.get("id", "")
          if eid:
            id_map.setdefault(eid, []).append(o)
    dups = {k: v for k, v in id_map.items() if len(v) > 1}
    # <STRANGE>#1020: only unlocked duplicates are a real warning.
    # If <=1 unlocked among the duplicates, defer it (grey #, no stripes).
    seen = set()
    for key, objs in dups.items():
      mk = "dup_id:" + key
      seen.add(mk)
      unlocked = [o for o in objs if not getattr(o, "locked", False)]
      if len(unlocked) >= 2:
        self.messages.set(mk, WARN, "Duplicate ID " + key, unlocked)
      else:
        self.messages.set(mk, DEFERRED, "Duplicate ID " + key, [])
    for k in list(self.messages.active.keys()):
      if k.startswith("dup_id:") and k not in seen:
        self.messages.clear(k)

  # ---------- main loop ----------
  def run(self):
    while self.running:
      dt = self.clock.tick(60) / 1000.0
      # <STRANGE>#1050: skip timers on frames right after a blocking
      # dialog (tkinter save/load/browse), otherwise messages expire
      # before the user sees them.
      if dt > 0.5:
        dt = 0.0
      _now_ms = pygame.time.get_ticks()
      _swallow = _now_ms < getattr(self, "_swallow_events_until", 0)
      for e in pygame.event.get():
        if _swallow and e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                                   pygame.KEYDOWN, pygame.KEYUP,
                                   pygame.MOUSEMOTION):
          continue
        self.handle_event(e)
      self.update_cursor()
      self.update_ghost()
      self.panel.update(dt)
      if self._scene_dirty:
        self._recompute_messages()
      self.messages.update(dt)
      self._tick_world_markers(dt)
      for p in self.inspector_stack:
        p.update(dt)
      self.draw()
      pygame.display.flip()
    pygame.quit()

  # ---------- tool ----------
  def set_tool(self, name):
    self.exit_polygon_edit()
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