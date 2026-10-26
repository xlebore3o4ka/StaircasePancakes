"""Ядро редактора: __init__, main loop, координаты, кэш сцены, inspector stack."""
import math
import colorsys
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


def _ease(t, kind):
  # <STRANGE>#1164: same easings as ctx.move_to
  t = max(0.0, min(1.0, t))
  if kind == "linear":
    return t
  if kind == "in":
    return t * t
  if kind == "out":
    return 1.0 - (1.0 - t) * (1.0 - t)
  if kind == "inout":
    return 2.0 * t * t if t < 0.5 else 1.0 - 2.0 * (1.0 - t) * (1.0 - t)
  return t
from .panel import TopPanel

try:
  from game.core import light_c
  light_c.install()
except Exception as e:
  print(f"editor: light_c not installed ({e}); using slow python preview")


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
    # <STRANGE>#1140: mind (thinking) mode flag. Tools are replaced.
    self.mind_mode = False
    # <STRANGE>#1150: current plan produced by Planner tool
    self.plan = None
    # ephemeral preview during a plan drag
    self._plan_preview = None
    # <STRANGE>#1160: preview playback state
    self.plan_preview_active = False
    self.plan_preview_t = 0.0
    self.plan_preview_phase = "forward"  # forward | hold | back
    self.plan_preview_origin = {}  # id(obj) -> (x, y)
    # <STRANGE>#1170: inline plan field editing
    self.plan_focus = None       # 'dx' | 'dy' | 'dur' | None
    self.plan_buffer = ""        # current typed text
    self.plan_cursor_blink = 0.0
    # <STRANGE>#1300: markup tool state (batch id assignment)
    self.markup = {"prefix": "", "postfix": "", "min": 0, "sep": "_"}
    self.markup_focus = None
    self.markup_buffer = ""
    self.markup_cursor_blink = 0.0
    # <STRANGE>#1401: anchor tool state
    self.current_anchor_variant = "A"
    self.anchor_focus = None
    self.anchor_buffer = ""
    self.anchor_cursor_blink = 0.0
    # <STRANGE>#1800: autosave state (period 30s, only if dirty)
    self._autosave_timer = 0.0
    self._autosave_period = 30.0
    self._autosave_last_path = None
    # <STRANGE>#1700: label state
    self._label_modal_open = False
    self._label_modal_cursor = 0.0
    self._label_modal_target = None
    self._label_modal_geom = {}
    self._label_modal_buffer = ""
    self._label_modal_focus = None
    self._label_modal_scroll = 0
    self._label_chip_modal_kind = None
    self._label_chip_modal_params = {}
    self._label_chip_modal_geom = {}
    # <STRANGE>#1900: sun (passive sky light) state
    self.sun_enabled = False
    self.sun_color = (180, 200, 240)
    self.sun_intensity = 0.45
    self.sun_direction = (0.6, 1.0)
    self.sun_shadow_length = 2000.0
    self.sun_gradient_length = 60.0
    # <STRANGE>#1520: lighting state
    self.current_light_type = "lamp"
    self.lighting = None
    self.lighting_ambient = (0, 0, 0)
    self.lighting_gain = 1.0
    self.light_preview = False
    self._level_settings_open = False
    self._level_settings_drag = None
    self._level_settings_geom = {}
    self._ls_focus = None
    self._ls_buffer = ""
    self._radial_cache = {}
    self._scratch_surface = None
    # <STRANGE>#1500: color templates + color picker state
    self.color_templates = {"platform": [], "background": [], "light": []}
    # <STRANGE>#1504: current color/edge applied to new objects
    from .const import PLAT_FILL as _PF, PLAT_EDGE as _PE, BG_DEFAULT_COLOR as _BG
    self.current_platform_fill = tuple(_PF)
    self.current_platform_edge = tuple(_PE)
    self.current_background_fill = tuple(_BG)
    self._color_edit_owner = None
    self._color_edit_field = None
    self._color_edit_orig_color = (128, 128, 128)
    self._color_edit_before = None
    self._color_edit_h = 0.0
    self._color_edit_s = 1.0
    self._color_edit_v = 1.0
    self._color_drag = None
    self._color_picker_geom = {}
    self._color_wheel_surface = None
    # <STRANGE>#1150: current plan produced by Planner tool
    self.plan = None
    # ephemeral preview during a plan drag
    self._plan_preview = None
    self.grid_step = 10
    self.grid_step_angle = 15
    # <STRANGE>#508: ?????????????????????????? ?????????????????????????? ?????? (?????? None)
    self.polygon_edit = None
    try:
      self._check_autosave_on_start()
    except Exception:
      pass

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
    # <STRANGE>#1130: skip None objects so a bad undo snapshot can't crash us
    clean = []
    for obj in self.objects:
      if obj is not None:
        clean.append(obj)
    if len(clean) != len(self.objects):
      self.objects = clean
    for i, obj in enumerate(self.objects):
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

  def _plan_field_positions(self):
    # <STRANGE>#1182: rows come from the render side (screen coords).
    info = getattr(self, "_plan_panel_pos", None)
    if not isinstance(info, dict):
      return {}
    return dict(info.get("rows", {}))

  def _plan_field_commit(self):
    # <STRANGE>#1172: commit the current buffer to the plan field
    f = self.plan_focus
    if f is None or self.plan is None:
      self.plan_focus = None
      self.plan_buffer = ""
      return
    try:
      v = float(self.plan_buffer)
    except Exception:
      v = None
    if v is not None:
      if f == "dx":
        self.plan["dx"] = v
      elif f == "dy":
        self.plan["dy"] = v
      elif f == "dur":
        self.plan["dur"] = max(0.05, v)
    self.plan_focus = None
    self.plan_buffer = ""
    self._mark_scene_dirty()

  def _plan_field_key(self, e):
    # <STRANGE>#1173: keyboard handling for plan edit fields
    if self.plan_focus is None:
      return False
    if e.key == pygame.K_ESCAPE:
      self.plan_focus = None
      self.plan_buffer = ""
      return True
    if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
      self._plan_field_commit()
      return True
    if e.key == pygame.K_BACKSPACE:
      self.plan_buffer = self.plan_buffer[:-1]
      return True
    if e.unicode and (e.unicode.isdigit() or e.unicode in ".+-"):
      if len(self.plan_buffer) < 12:
        self.plan_buffer += e.unicode
      return True
    return True

  def _tick_plan_preview(self, dt):
    # <STRANGE>#1161: animate the group forward -> hold -> back
    if not getattr(self, "plan_preview_active", False):
      return
    p = getattr(self, "plan", None)
    if p is None:
      self.plan_preview_active = False
      return
    dur = float(p.get("dur", 0.5))
    dx = float(p.get("dx", 0.0))
    dy = float(p.get("dy", 0.0))
    HOLD = 0.3
    phase = self.plan_preview_phase
    self.plan_preview_t += dt
    if phase == "forward":
      k = min(1.0, self.plan_preview_t / max(0.001, dur))
      k = _ease(k, p.get("ease", "out"))
    else:
      # <STRANGE>#1200: hold phase only; return is a teleport, not animation
      k = 1.0
    for obj in p.get("objects", []):
      orig = self.plan_preview_origin.get(id(obj))
      if orig is None:
        continue
      obj.x = orig[0] + dx * k
      obj.y = orig[1] + dy * k
    # phases
    if phase == "forward" and self.plan_preview_t >= dur:
      self.plan_preview_phase = "hold"
      self.plan_preview_t = 0.0
    elif phase == "hold" and self.plan_preview_t >= HOLD:
      # <STRANGE>#1201: teleport home, no animated return
      self._stop_plan_preview()

  def _start_plan_preview(self):
    # <STRANGE>#1162: snapshot origins, begin forward phase
    p = getattr(self, "plan", None)
    if p is None:
      return
    self.plan_preview_origin = {}
    for obj in p.get("objects", []):
      self.plan_preview_origin[id(obj)] = (obj.x, obj.y)
    self.plan_preview_active = True
    self.plan_preview_t = 0.0
    self.plan_preview_phase = "forward"
    self._mark_scene_dirty()

  def _stop_plan_preview(self):
    # <STRANGE>#1163: restore origins and stop
    p = getattr(self, "plan", None)
    if p is not None:
      for obj in p.get("objects", []):
        orig = self.plan_preview_origin.get(id(obj))
        if orig is not None:
          obj.x, obj.y = orig
    self.plan_preview_origin = {}
    self.plan_preview_active = False
    self.plan_preview_t = 0.0
    self.plan_preview_phase = "forward"
    self._mark_scene_dirty()

  def _markup_field_commit(self):
    # <STRANGE>#1302: apply the typed buffer to the markup field
    f = self.markup_focus
    if f is None:
      return
    txt = self.markup_buffer
    if f == "min":
      try:
        self.markup["min"] = int(txt)
      except Exception:
        pass
    else:
      self.markup[f] = txt
    self.markup_focus = None
    self.markup_buffer = ""
    self._mark_scene_dirty()

  def _markup_field_key(self, e):
    # <STRANGE>#1303: keyboard for markup fields
    if self.markup_focus is None:
      return False
    if e.key == pygame.K_ESCAPE:
      self.markup_focus = None
      self.markup_buffer = ""
      return True
    if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
      self._markup_field_commit()
      return True
    if e.key == pygame.K_BACKSPACE:
      self.markup_buffer = self.markup_buffer[:-1]
      return True
    if e.unicode and e.unicode.isprintable():
      if len(self.markup_buffer) < 32:
        self.markup_buffer += e.unicode
      return True
    return True

  def _markup_apply(self):
    # <STRANGE>#1304: assign ids to all selected objects in document order
    objs = list(self.selection)
    if not objs:
      return
    pre = str(self.markup.get("prefix", ""))
    post = str(self.markup.get("postfix", ""))
    sep = str(self.markup.get("sep", "_"))
    n = int(self.markup.get("min", 0))
    order = [o for o in self.objects if o in objs]
    before = self._snapshot()
    for o in order:
      parts = []
      if pre:
        parts.append(pre)
      parts.append(str(n))
      if post:
        parts.append(post)
      o.id = sep.join(parts)
      n += 1
    self._push_undo_now(before)
    self._mark_scene_dirty()
    try:
      from .messages import INFO
      self.messages.toast_only(INFO, "Marked %d object(s)" % len(order), 2.5)
    except Exception:
      pass

  def _anchor_field_commit(self):
    # <STRANGE>#1470: A/B commit binding; S commits name/weight/max_limit
    f = self.anchor_focus
    if f is None:
      return
    objs = [o for o in self.selection if hasattr(o, "variant")]
    if not objs:
      self.anchor_focus = None
      self.anchor_buffer = ""
      return
    before = self._snapshot()
    for o in objs:
      v = getattr(o, "variant", "")
      if f == "binding" and v in ("A", "B"):
        o.binding = self.anchor_buffer
      elif f == "name" and v == "S":
        o.name = self.anchor_buffer
      elif f == "weight" and v == "S":
        try:
          val = int(self.anchor_buffer)
          if val < 1: val = 1
          o.weight = val
        except Exception:
          pass
      elif f == "max_limit" and v == "S":
        try:
          val = int(self.anchor_buffer)
          if val < 1: val = 1
          o.max_limit = val
        except Exception:
          pass
    self._push_undo_now(before)
    self.anchor_focus = None
    self.anchor_buffer = ""
    self._mark_scene_dirty()

  def _bake_zone(self, s_anchor):
    # <STRANGE>#1471: bake a zone: N copies of its objects with IDs orig_N
    import json as _json
    from tkinter import filedialog as _fd
    import tkinter as _tk
    if s_anchor is None or getattr(s_anchor, "variant", "") != "S":
      return False
    pairs, free_s, assigned, zone_s = self._anchor_pairs()
    bnd = assigned.get(id(s_anchor))
    if bnd is None:
      return False
    s_ids = zone_s.get(bnd, [])
    if len(s_ids) > 1:
      try:
        from .messages import ERROR
        self.messages.toast_only(ERROR,
            "Cannot bake: zone has multiple S", 3.0)
      except Exception:
        pass
      return False
    A = B = None
    for b, a, b_ in pairs:
      if b == bnd:
        A = a
        B = b_
        break
    if A is None or B is None:
      return False
    l, r, bt, tt = self._anchor_zone_rect(A, B)
    inside = []
    for o in self.objects:
      if hasattr(o, "variant"):
        continue
      try:
        if o.intersects_rect(l, r, bt, tt):
          inside.append(o)
      except Exception:
        pass
    no_id = [o for o in inside if not getattr(o, "id", "")]
    if no_id:
      try:
        from .messages import ERROR
        self.messages.toast_only(ERROR,
            "Cannot bake: %d object(s) have no id" % len(no_id), 3.0)
      except Exception:
        pass
      return False
    before = self._snapshot()
    orig_ids = {}
    orig_states = {}
    for o in inside:
      orig_ids[id(o)] = o.id
      orig_states[id(o)] = self._obj_to_state(o)
    sx, sy = s_anchor.x, s_anchor.y
    rel = {}
    for o in inside:
      rel[id(o)] = (o.x - sx, o.y - sy)
    N = max(1, int(getattr(s_anchor, "max_limit", 1)))
    payload = {
      "version": 1,
      "zone": {
        "binding": str(bnd),
        "name": str(getattr(s_anchor, "name", "")),
        "weight": int(getattr(s_anchor, "weight", 1)),
        "max_limit": int(N),
        "size": [int(abs(B.x - A.x)), int(abs(B.y - A.y))],
        "instances": [],
      },
      "free_spawns": [],
    }
    for sf in free_s:
      payload["free_spawns"].append({"x": int(sf.x), "y": int(sf.y)})
    for n in range(1, N + 1):
      inst = {"n": n, "objects": []}
      for o in inside:
        dx, dy = rel[id(o)]
        inst["objects"].append({
          "id": orig_ids[id(o)] + ("_%d" % n),
          "dx": int(round(dx)),
          "dy": int(round(dy)),
        })
      payload["zone"]["instances"].append(inst)
    for o in inside:
      o.id = orig_ids[id(o)] + "_1"
    for n in range(2, N + 1):
      for o in inside:
        st = dict(orig_states[id(o)])
        st["id"] = orig_ids[id(o)] + ("_%d" % n)
        try:
          new_o = self._make_from_state(st)
        except Exception:
          new_o = None
        if new_o is not None:
          self.objects.append(new_o)
    remove_ids = set()
    remove_ids.add(id(A))
    remove_ids.add(id(B))
    remove_ids.add(id(s_anchor))
    for sid in s_ids:
      remove_ids.add(sid)
    self.objects = [o for o in self.objects if id(o) not in remove_ids]
    self._push_undo_now(before)
    self._mark_scene_dirty()
    # Offer to save JSON
    try:
      root = _tk.Tk()
      root.withdraw()
      path = _fd.asksaveasfilename(
          defaultextension=".json",
          initialdir="levels",
          initialfile="zone_%s.json" % bnd,
          filetypes=[("JSON", "*.json")],
      )
      root.destroy()
      self._flush_pygame_events()
      if path:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
          f.write(_json.dumps(payload, indent=2))
        try:
          from .messages import INFO
          self.messages.toast_only(INFO,
              "Baked %d copies, saved: %s" % (N, path), 3.5)
        except Exception:
          pass
    except Exception:
      pass
    return True

  def _anchor_field_key(self, e):
    # <STRANGE>#1474: keyboard for anchor fields
    if self.anchor_focus is None:
      return False
    if e.key == pygame.K_ESCAPE:
      self.anchor_focus = None
      self.anchor_buffer = ""
      return True
    if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
      self._anchor_field_commit()
      return True
    if e.key == pygame.K_BACKSPACE:
      self.anchor_buffer = self.anchor_buffer[:-1]
      return True
    if e.unicode and e.unicode.isprintable():
      if len(self.anchor_buffer) < 48:
        self.anchor_buffer += e.unicode
      return True
    return True

  @staticmethod
  def _anchor_zone_rect(a, b):
    # (l, r, bottom, top)
    l = min(a.x, b.x); r = max(a.x, b.x)
    bt = min(a.y, b.y); tt = max(a.y, b.y)
    return (l, r, bt, tt)

  @staticmethod
  def _zone_contains_strict(zr, s):
    # <STRANGE>#1442: strict inside; edges do NOT count
    l, r, bt, tt = zr
    return (l < s.x < r) and (bt < s.y < tt)

  @staticmethod
  def _rects_overlap(z1, z2):
    l1, r1, b1, t1 = z1
    l2, r2, b2, t2 = z2
    return not (r1 <= l2 or r2 <= l1 or t1 <= b2 or t2 <= b1)

  def _anchor_pairs(self):
    # <STRANGE>#1443: A/B without binding ignored; S auto-binds by geometry;
    # free S are those outside every zone.
    a_map = {}
    b_map = {}
    for o in self.objects:
      if not hasattr(o, "variant"):
        continue
      v = getattr(o, "variant", "")
      bnd = str(getattr(o, "binding", ""))
      if not bnd:
        continue
      if v == "A":
        a_map.setdefault(bnd, []).append(o)
      elif v == "B":
        b_map.setdefault(bnd, []).append(o)
    pairs = []
    for bnd in sorted(set(list(a_map.keys()) + list(b_map.keys()))):
      a = a_map.get(bnd, [])
      b = b_map.get(bnd, [])
      if a and b:
        pairs.append((bnd, a[0], b[0]))
    # S anchors
    s_all = [o for o in self.objects
             if getattr(o, "variant", "") == "S"]
    assigned = {}  # id(s) -> binding
    free_s = []
    for s in s_all:
      hit = None
      for bnd, a, b in pairs:
        zr = self._anchor_zone_rect(a, b)
        if self._zone_contains_strict(zr, s):
          hit = bnd
          break
      if hit is None:
        free_s.append(s)
      else:
        assigned[id(s)] = hit
    # zones with their S (or None)
    zone_s = {}
    for sid, bnd in assigned.items():
      zone_s.setdefault(bnd, []).append(sid)
    return pairs, free_s, assigned, zone_s

  # ---------- color picker + templates ----------
  def _color_edit_begin(self, owner, field):
    if owner is None:
      return
    try:
      if owner == "ambient":
        c = tuple(self.lighting_ambient)[:3]
      elif owner == "sun":
        c = tuple(self.sun_color)[:3]
      else:
        c = tuple(getattr(owner, field, (128, 128, 128)))[:3]
    except Exception:
      c = (128, 128, 128)
    r, g, b = c[0] / 255.0, c[1] / 255.0, c[2] / 255.0
    h, sat, v = colorsys.rgb_to_hsv(r, g, b)
    self._color_edit_owner = owner
    self._color_edit_field = field
    self._color_edit_orig_color = c
    self._color_edit_h = h
    self._color_edit_s = sat
    self._color_edit_v = v
    self._color_edit_before = self._snapshot()
    self._color_drag = None

  def _color_edit_apply(self):
    if self._color_edit_owner is None:
      return
    r, g, b = colorsys.hsv_to_rgb(self._color_edit_h, self._color_edit_s, self._color_edit_v)
    c = (int(r * 255), int(g * 255), int(b * 255))
    if self._color_edit_owner == "ambient":
      self.lighting_ambient = c
      if self.lighting is not None:
        self.lighting["ambient"] = list(c)
    elif self._color_edit_owner == "sun":
      self.sun_color = c
    else:
      try:
        setattr(self._color_edit_owner, self._color_edit_field, c)
      except Exception:
        pass
    self._mark_scene_dirty()

  def _color_edit_commit(self):
    if self._color_edit_owner is None:
      return
    before = self._color_edit_before
    self._color_edit_owner = None
    self._color_edit_field = None
    self._color_edit_before = None
    self._color_drag = None
    self._color_picker_geom = {}
    if before is not None:
      try:
        if self._snapshot() != before:
          self._push_undo_now(before)
      except Exception:
        pass
    self._mark_scene_dirty()

  def _color_edit_cancel(self):
    if self._color_edit_owner is None:
      return
    if self._color_edit_owner == "ambient":
      self.lighting_ambient = self._color_edit_orig_color
      if self.lighting is not None:
        self.lighting["ambient"] = list(self._color_edit_orig_color)
    elif self._color_edit_owner == "sun":
      self.sun_color = self._color_edit_orig_color
    else:
      try:
        setattr(self._color_edit_owner, self._color_edit_field,
                self._color_edit_orig_color)
      except Exception:
        pass
    self._color_edit_owner = None
    self._color_edit_field = None
    self._color_edit_before = None
    self._color_drag = None
    self._color_picker_geom = {}
    self._mark_scene_dirty()

  def _add_color_template_from_object(self, obj):
    from .objects import EditorPlatform, EditorBackground, EditorLight
    name = None
    try:
      import tkinter as _tk
      from tkinter import simpledialog as _sd
      root = _tk.Tk()
      root.withdraw()
      name = _sd.askstring("Template name", "Enter template name:", parent=root)
      root.destroy()
      self._flush_pygame_events()
    except Exception:
      name = None
    if not name:
      return
    if isinstance(obj, EditorPlatform):
      tmpl = {"name": str(name),
              "fill": list(tuple(obj.fill)),
              "edge": list(tuple(obj.edge))}
      self.color_templates.setdefault("platform", []).append(tmpl)
    elif isinstance(obj, EditorBackground):
      tmpl = {"name": str(name), "color": list(tuple(obj.fill))}
      self.color_templates.setdefault("background", []).append(tmpl)
    elif isinstance(obj, EditorLight):
      tmpl = {"name": str(name), "color": list(tuple(obj.color))}
      self.color_templates.setdefault("light", []).append(tmpl)
    else:
      return
    try:
      from .messages import INFO
      self.messages.toast_only(INFO, "Saved template: " + str(name), 2.5)
    except Exception:
      pass

  # ---------- sun (passive sky light) ----------
  def _set_sun_enabled(self, enabled):
    self.sun_enabled = bool(enabled)
    if self.sun_enabled and self.lighting is None:
      self._ensure_lighting()
    self._mark_scene_dirty()

  def _set_sun_channel(self, i, value):
    v = max(0, min(255, int(value)))
    c = list(self.sun_color)
    c[i] = v
    self.sun_color = tuple(c)
    self._mark_scene_dirty()

  def _set_sun_intensity(self, value):
    self.sun_intensity = max(0.0, min(2.0, float(value)))
    self._mark_scene_dirty()

  def _set_sun_shadow_length(self, value):
    self.sun_shadow_length = max(100.0, min(5000.0, float(value)))
    self._mark_scene_dirty()

  def _set_sun_gradient_length(self, value):
    self.sun_gradient_length = max(1.0, min(500.0, float(value)))
    self._mark_scene_dirty()

  def _set_sun_direction(self, which, value):
    v = max(-1.0, min(1.0, float(value)))
    d = list(self.sun_direction)
    d[0 if which == "x" else 1] = v
    self.sun_direction = (d[0], d[1])
    self._mark_scene_dirty()

  def _lights_for_output(self):
    from .objects import EditorLight
    lights = [o.to_json() for o in self.objects if isinstance(o, EditorLight)]
    if getattr(self, "sun_enabled", False):
      lights.append({
        "type": "sun", "id": "sun",
        "color": list(self.sun_color),
        "intensity": float(self.sun_intensity),
        "direction": list(self.sun_direction),
        "shadow_length": float(self.sun_shadow_length),
        "gradient_length": float(self.sun_gradient_length),
      })
    return lights

  # ---------- level settings ----------
  def _open_level_settings(self):
    self._level_settings_open = True

  def _close_level_settings(self):
    self._level_settings_open = False
    self._level_settings_drag = None
    self._level_settings_geom = {}
    self._mark_scene_dirty()

  def _ensure_lighting(self):
    if self.lighting is None:
      self.lighting = {"ambient": [int(self.lighting_ambient[0]),
                                     int(self.lighting_ambient[1]),
                                     int(self.lighting_ambient[2])],
                        "gain": float(self.lighting_gain)}

  def _set_lighting_ambient_channel(self, i, value):
    v = max(0, min(255, int(value)))
    a = list(self.lighting_ambient)
    a[i] = v
    self.lighting_ambient = tuple(a)
    if self.lighting is not None:
      self.lighting["ambient"] = list(self.lighting_ambient)
    self._mark_scene_dirty()

  def _set_lighting_gain(self, value):
    g = max(0.1, min(3.0, float(value)))
    self.lighting_gain = g
    if self.lighting is not None:
      self.lighting["gain"] = g
    self._mark_scene_dirty()

  def _commit_ls_focus(self):
    # <STRANGE>#2200: commit typed keyboard value for level settings
    f = getattr(self, "_ls_focus", None)
    if f is None:
      return
    try:
      val = float(self._ls_buffer)
    except Exception:
      self._ls_focus = None
      return
    if f == "r": self._set_lighting_ambient_channel(0, int(val))
    elif f == "g": self._set_lighting_ambient_channel(1, int(val))
    elif f == "b": self._set_lighting_ambient_channel(2, int(val))
    elif f == "gain": self._set_lighting_gain(val)
    elif f == "sun_r": self._set_sun_channel(0, int(val))
    elif f == "sun_g": self._set_sun_channel(1, int(val))
    elif f == "sun_b": self._set_sun_channel(2, int(val))
    elif f == "sun_int": self._set_sun_intensity(val)
    elif f == "sun_dx": self._set_sun_direction("x", val)
    elif f == "sun_dy": self._set_sun_direction("y", val)
    elif f == "sun_slen": self._set_sun_shadow_length(val)
    elif f == "sun_glen": self._set_sun_gradient_length(val)
    self._ls_focus = None
    self._ls_buffer = ""

  def _reset_level_setting(self, key):
    # <STRANGE>#2201: reset specific setting to default
    from .const import LIGHT_DEFAULT_AMBIENT, LIGHT_DEFAULT_GAIN, SUN_DEFAULT_COLOR, SUN_DEFAULT_INTENSITY, SUN_DEFAULT_DIRECTION, SUN_DEFAULT_SHADOW_LENGTH, SUN_DEFAULT_GRADIENT_LENGTH
    if key == 'ambient':
      self._set_lighting_ambient_channel(0, LIGHT_DEFAULT_AMBIENT[0])
      self._set_lighting_ambient_channel(1, LIGHT_DEFAULT_AMBIENT[1])
      self._set_lighting_ambient_channel(2, LIGHT_DEFAULT_AMBIENT[2])
    elif key == 'gain': self._set_lighting_gain(LIGHT_DEFAULT_GAIN)
    elif key == 'sun':
      self._set_sun_channel(0, SUN_DEFAULT_COLOR[0])
      self._set_sun_channel(1, SUN_DEFAULT_COLOR[1])
      self._set_sun_channel(2, SUN_DEFAULT_COLOR[2])
    elif key == 'sun_int': self._set_sun_intensity(SUN_DEFAULT_INTENSITY)
    elif key == 'sun_dx': self._set_sun_direction('x', SUN_DEFAULT_DIRECTION[0])
    elif key == 'sun_dy': self._set_sun_direction('y', SUN_DEFAULT_DIRECTION[1])
    elif key == 'sun_slen': self._set_sun_shadow_length(SUN_DEFAULT_SHADOW_LENGTH)
    elif key == 'sun_glen': self._set_sun_gradient_length(SUN_DEFAULT_GRADIENT_LENGTH)
    if getattr(self, "_ls_focus", None) == key:
      self._ls_focus = None

  def _reset_all_level_settings(self):
    # <STRANGE>#2202: reset all level settings
    for k in ('ambient', 'gain', 'sun', 'sun_int', 'sun_dx', 'sun_dy', 'sun_slen', 'sun_glen'):
      self._reset_level_setting(k)
    self._ls_focus = None

  # ---------- autosave / emergency save ----------
  def _collect_level_data(self):
    # shared between autosave, emergency save and manual save
    import json as _json
    from .objects import (EditorPeg, EditorPlatform, EditorBackground, EditorItem,
                          EditorSpawner, EditorArtifact, EditorTrigger, EditorButton,
                          EditorAnchor, EditorLight, EditorLabel)
    pegs = [o.to_json() for o in self.objects if isinstance(o, EditorPeg)]
    buttons = [o.to_json() for o in self.objects if isinstance(o, EditorButton)]
    platforms = [o.to_json() for o in self.objects if isinstance(o, EditorPlatform)]
    backgrounds = [o.to_json() for o in self.objects if isinstance(o, EditorBackground)]
    items = [o.to_json() for o in self.objects if isinstance(o, EditorItem)]
    spawners = [o.to_json() for o in self.objects if isinstance(o, EditorSpawner)]
    triggers = [o.to_json() for o in self.objects if isinstance(o, EditorTrigger)]
    lights = [o.to_json() for o in self.objects if isinstance(o, EditorLight)]
    labels = [o.to_json() for o in self.objects if isinstance(o, EditorLabel)]
    bag = None
    lantern = None
    for o in self.objects:
      if isinstance(o, EditorArtifact):
        if getattr(o, "artifact_type", "bag") == "lantern":
          lantern = o.to_json()
        else:
          bag = o.to_json()
    out = {"version": str(_game_version_read())}
    if getattr(self, "lighting", None) is not None or lights:
      cfg = getattr(self, "lighting", None) or {
        "ambient": list(getattr(self, "lighting_ambient", (0, 0, 0))),
        "gain": float(getattr(self, "lighting_gain", 1.0)),
      }
      out["lighting"] = dict(cfg)
      out["lights"] = lights
    out.update({
      "pegs": pegs, "platforms": platforms, "backgrounds": backgrounds,
      "items": items, "itemSpawners": spawners,
      "triggers": triggers, "buttons": buttons,
    })
    if bag is not None:
      out["bag"] = bag
    if lantern is not None:
      out["lantern"] = lantern
    meta = {"version": 1}
    anchors = [o.to_json() for o in self.objects if isinstance(o, EditorAnchor)]
    if anchors:
      meta["anchors"] = anchors
    if labels:
      meta["labels"] = labels
    try:
      pt = list(getattr(self, "color_templates", {}).get("platform", []))
      bt = list(getattr(self, "color_templates", {}).get("background", []))
      lt = list(getattr(self, "color_templates", {}).get("light", []))
      if pt: meta["platform_color_templates"] = pt
      if bt: meta["background_color_templates"] = bt
      if lt: meta["light_color_templates"] = lt
    except Exception:
      pass
    return out, meta

  def _autosave(self):
    import json as _json
    import os as _os
    base = _os.path.join(_os.path.dirname(__file__), "autosave")
    try:
      _os.makedirs(base, exist_ok=True)
    except Exception:
      return
    data, meta = self._collect_level_data()
    lv = _os.path.join(base, "level.json")
    mt = _os.path.join(base, "editor.json")
    with open(lv, "w", encoding="utf-8", newline="\n") as f:
      f.write(_json.dumps(data, indent=2))
    with open(mt, "w", encoding="utf-8", newline="\n") as f:
      f.write(_json.dumps(meta, indent=2))
    self._autosave_last_path = base

  def _emergency_save(self):
    import json as _json
    import os as _os
    base = _os.path.join(_os.path.dirname(__file__), "emergency")
    try:
      _os.makedirs(base, exist_ok=True)
    except Exception:
      return
    data, meta = self._collect_level_data()
    lv = _os.path.join(base, "level.json")
    mt = _os.path.join(base, "editor.json")
    with open(lv, "w", encoding="utf-8", newline="\n") as f:
      f.write(_json.dumps(data, indent=2))
    with open(mt, "w", encoding="utf-8", newline="\n") as f:
      f.write(_json.dumps(meta, indent=2))
    try:
      from .messages import INFO
      self.messages.toast_only(INFO, "Emergency save: " + base, 4.0)
    except Exception:
      pass

  def _check_autosave_on_start(self):
    import os as _os
    base = _os.path.join(_os.path.dirname(__file__), "autosave")
    lv = _os.path.join(base, "level.json")
    if _os.path.isfile(lv):
      try:
        from .messages import INFO
        self.messages.toast_only(
            INFO, "Autosave found: editor/autosave/level.json", 6.0)
      except Exception:
        pass

  # ---------- label modal ----------
  def _open_label_modal(self, label):
    if label is None:
      return
    self._label_modal_open = True
    self._label_modal_target = label
    self._label_modal_focus = None
    self._label_modal_buffer = ""
    self._label_modal_scroll = 0
    self._label_modal_cursor = 0.0

  def _close_label_modal(self, apply_changes=True):
    self._label_modal_open = False
    self._label_modal_target = None
    self._label_modal_geom = {}
    self._label_modal_buffer = ""
    self._label_modal_focus = None

  def _label_modal_commit_field(self):
    tgt = getattr(self, "_label_modal_target", None)
    f = getattr(self, "_label_modal_focus", None)
    if tgt is None or f is None:
      return
    buf = getattr(self, "_label_modal_buffer", "")
    before = self._snapshot()
    if f == "text":
      tgt.text = buf or "label"
    elif f == "target":
      tgt.target_trigger_id = buf
    self._push_undo_now(before)
    self._label_modal_focus = None
    self._label_modal_buffer = ""
    self._mark_scene_dirty()

  def _label_chip_new(self, kind):
    if kind == "toast":
      return {"kind": "toast", "params": {"msg": "hello", "dur": 2.0}}
    if kind == "sound":
      return {"kind": "sound", "params": {"name": "button_down", "volume": 1.0}}
    if kind == "text":
      return {"kind": "text", "params": {"msg": "!", "x": 0, "y": 200, "dur": 1.5, "size": 32}}
    if kind == "flash":
      return {"kind": "flash", "params": {"dur": 0.3, "color": [255, 255, 255], "alpha": 120}}
    if kind == "shake":
      return {"kind": "shake", "params": {"dur": 0.3, "amp": 8, "freq": 0.0}}
    if kind == "log":
      return {"kind": "log", "params": {"msg": "log"}}
    if kind == "move_to":
      return {"kind": "move_to", "params": {"oid": "", "dur": 0.5, "ease": "out"}}
    return {"kind": kind, "params": {}}

  def _generate_label_script(self, label=None):
    if label is None:
      label = getattr(self, "_label_modal_target", None)
    if label is None:
      return
    tid = str(getattr(label, "target_trigger_id", "")).strip()
    if not tid:
      try:
        from .messages import WARN
        self.messages.toast_only(WARN, "Label has no target trigger id", 3.0)
      except Exception:
        pass
      return
    trig = None
    from .objects import EditorTrigger
    for o in self.objects:
      if isinstance(o, EditorTrigger) and str(getattr(o, "id", "")) == tid:
        trig = o
        break
    if trig is None:
      try:
        from .messages import ERROR
        self.messages.toast_only(ERROR, "Trigger '%s' not found" % tid, 3.0)
      except Exception:
        pass
      return
    lines = ["# generated from label '%s'" % str(label.text), ""]
    on_enter = [c for c in label.chips if c.get("kind") in
                ("toast", "sound", "text", "flash", "shake", "log", "move_to")]
    if on_enter:
      lines.append("def on_enter(ctx):")
      for c in on_enter:
        k = c.get("kind", "")
        p = c.get("params", {})
        if k == "toast":
          msg = str(p.get("msg", ""))
          dur = float(p.get("dur", 2.0))
          lines.append("    ctx.toast(%r, dur=%.2f)" % (msg, dur))
        elif k == "sound":
          name = str(p.get("name", "button_down"))
          vol = float(p.get("volume", 1.0))
          lines.append("    ctx.sound(%r, volume=%.2f)" % (name, vol))
        elif k == "text":
          msg = str(p.get("msg", ""))
          x = float(p.get("x", 0)); y = float(p.get("y", 200))
          dur = float(p.get("dur", 1.5)); size = int(p.get("size", 32))
          lines.append("    ctx.text(%r, %.1f, %.1f, dur=%.2f, size=%d)" % (msg, x, y, dur, size))
        elif k == "flash":
          dur = float(p.get("dur", 0.3))
          col = p.get("color", [255, 255, 255])
          alpha = int(p.get("alpha", 120))
          lines.append("    ctx.flash(%.2f, color=(%d, %d, %d), alpha=%d)" % (dur, col[0], col[1], col[2], alpha))
        elif k == "shake":
          dur = float(p.get("dur", 0.3)); amp = float(p.get("amp", 8)); freq = float(p.get("freq", 0.0))
          lines.append("    ctx.shake(%.2f, %.1f, freq=%.2f)" % (dur, amp, freq))
        elif k == "log":
          msg = str(p.get("msg", "log"))
          lines.append("    ctx.log(%r)" % msg)
        elif k == "move_to":
          oid = str(p.get("oid", ""))
          dur = float(p.get("dur", 0.5)); ease = str(p.get("ease", "out"))
          if not oid:
            lines.append("    # move_to skipped: no oid")
          else:
            lines.append("    ctx.move_to(%r, dur=%.2f, ease=%r)" % (oid, dur, ease))
      lines.append("")
    text = "\n".join(lines)
    script_name = "scripts/label_%s.py" % tid
    self.embedded_files[script_name] = text.encode("utf-8")
    trig.script = script_name
    self._mark_scene_dirty()
    try:
      from .messages import INFO
      self.messages.toast_only(INFO, "Generated: %s -> trigger '%s'" % (script_name, tid), 3.0)
    except Exception:
      pass

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
    # <STRANGE>#1444: anchor warnings (binding duplicates, zone overlap,
    # missing S in a zone, missing id in a zone)
    try:
      pairs, free_s, assigned, zone_s = self._anchor_pairs()
      # binding duplicates (same binding on >1 A or >1 B)
      from collections import defaultdict
      bnds = defaultdict(lambda: {"A": [], "B": []})
      for o in self.objects:
        if getattr(o, "variant", "") in ("A", "B"):
          bnd = str(getattr(o, "binding", ""))
          if bnd:
            bnds[bnd][getattr(o, "variant", "")].append(o)
      dup_targets = []
      dup_names = []
      for bnd, d in bnds.items():
        if len(d["A"]) > 1 or len(d["B"]) > 1:
          dup_targets.extend(d["A"] + d["B"])
          dup_names.append(bnd)
      if dup_targets:
        self.messages.set("anchor_dup", WARN,
                          "Anchor binding duplicated: " + ", ".join(sorted(dup_names)),
                          dup_targets)
      else:
        self.messages.clear("anchor_dup")
      # zone overlap
      overlap_targets = []
      for i in range(len(pairs)):
        for j in range(i + 1, len(pairs)):
          z1 = self._anchor_zone_rect(pairs[i][1], pairs[i][2])
          z2 = self._anchor_zone_rect(pairs[j][1], pairs[j][2])
          if self._rects_overlap(z1, z2):
            overlap_targets.extend([pairs[i][1], pairs[i][2],
                                    pairs[j][1], pairs[j][2]])
      if overlap_targets:
        self.messages.set("anchor_overlap", ERROR,
                          "Anchor zones overlap", overlap_targets)
      else:
        self.messages.clear("anchor_overlap")
      # multiple S in one zone (ERROR: exactly one S per zone)
      multi_s = []
      multi_names = []
      for bnd, s_ids in zone_s.items():
        if len(s_ids) > 1:
          multi_names.append(bnd)
          for sid in s_ids:
            for o in self.objects:
              if id(o) == sid:
                multi_s.append(o)
                break
      if multi_s:
        self.messages.set("anchor_multi_s", ERROR,
                          "Zone has multiple S: " + ", ".join(sorted(multi_names)),
                          multi_s)
      else:
        self.messages.clear("anchor_multi_s")
      # multiple S in one zone (ERROR: exactly one S per zone)
      multi_s = []
      multi_names = []
      for bnd, s_ids in zone_s.items():
        if len(s_ids) > 1:
          multi_names.append(bnd)
          for sid in s_ids:
            for o in self.objects:
              if id(o) == sid:
                multi_s.append(o)
                break
      if multi_s:
        self.messages.set("anchor_multi_s", ERROR,
                          "Zone has multiple S: " + ", ".join(sorted(multi_names)),
                          multi_s)
      else:
        self.messages.clear("anchor_multi_s")
      # zone missing its S
      miss_targets = []
      for bnd, a, b in pairs:
        if bnd not in zone_s:
          miss_targets.extend([a, b])
      if miss_targets:
        self.messages.set("anchor_no_s", INFO,
                          "Zone without S: %d" % (len(miss_targets) // 2),
                          miss_targets)
      else:
        self.messages.clear("anchor_no_s")
      # no-id objects inside zones
      bad = []
      for bnd, a, b in pairs:
        l, r, bt, tt = self._anchor_zone_rect(a, b)
        for o in self.objects:
          if hasattr(o, "variant"):
            continue
          try:
            if not o.intersects_rect(l, r, bt, tt):
              continue
          except Exception:
            continue
          if not getattr(o, "id", ""):
            bad.append(o)
      if bad:
        self.messages.set("anchor_no_id", WARN,
                          "Anchor zone has %d object(s) without id" % len(bad),
                          bad)
      else:
        self.messages.clear("anchor_no_id")
    except Exception:
      pass

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
      self._tick_plan_preview(dt)
      self.plan_cursor_blink = (self.plan_cursor_blink + dt) % 1.0
      # <STRANGE>#1801: autosave tick (only if scene dirty)
      if self._scene_dirty:
        self._autosave_timer += dt
        if self._autosave_timer >= self._autosave_period:
          self._autosave_timer = 0.0
          try:
            self._autosave()
          except Exception as _ex:
            try:
              from .messages import WARN
              self.messages.toast_only(WARN, "Autosave failed: " + str(_ex)[:60], 3.0)
            except Exception:
              pass
      self.markup_cursor_blink = (self.markup_cursor_blink + dt) % 1.0
      self._label_modal_cursor = (getattr(self, "_label_modal_cursor", 0.0) + dt) % 1.0
      self.anchor_cursor_blink = (self.anchor_cursor_blink + dt) % 1.0
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
    # <STRANGE>#1305: clear text field focus when switching tools
    self.plan_focus = None
    self.plan_buffer = ""
    self.markup_focus = None
    self.markup_buffer = ""
    self.anchor_focus = None
    self.anchor_buffer = ""
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