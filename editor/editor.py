import json
import math
import pygame
import tkinter as tk
from tkinter import filedialog
from shared.const import (
  BODY_R, ARM_R, ARM_DX, JUMP_V, GRAVITY,
  PEG_R, PEG_FILL, PEG_EDGE,
  PLAT_FILL, PLAT_EDGE, PLAT_EDGE_W,
  BG_FILL,
)

# ---- layout ----
BOT_H = 70
BG = (50, 55, 65)
UI_BG = (30, 33, 40)
GOLD = (255, 215, 0)
GREY = (110, 110, 110)
GREEN = (60, 220, 100)
SEL_BLUE = (100, 200, 255)
PLAT_DEFAULT_W = 180
PLAT_DEFAULT_H = 72
RESIZE_ZONE = 8
MIN_SIZE = 20
PLAYER_R = BODY_R
GHOST_ALPHA = 110
JUMP_H = JUMP_V * JUMP_V / (2 * GRAVITY)
ARM_ALPHA = 90
JUMP_ALPHA = 70
BG_DEFAULT_COLOR = BG_FILL
GHOST_LERP = 0.15
GHOST_SNAP = 0.5
GHOST_RETURN_DELAY = 2.0
UNDO_LIMIT = 200
PASTE_OFFSET = 20
CLICK_THRESHOLD = 4

# ---- panel styling ----
PANEL_HEADER_H = 36
PANEL_BODY_H = 62
PANEL_WIDGET_H = 34
PANEL_BG = (24, 27, 33)
PANEL_BORDER = (60, 66, 78)
PANEL_TITLE = (205, 210, 220)
BTN_BG = (60, 66, 78)
BTN_BG_HOVER = (80, 88, 102)
BTN_BG_PRESS = (46, 52, 62)
BTN_BG_ACTIVE = (58, 128, 92)
BTN_BORDER = (105, 112, 126)
BTN_TEXT = (225, 230, 240)
BTN_TEXT_DIM = (130, 135, 145)
INPUT_BG = (16, 18, 22)
INPUT_BORDER = (85, 92, 106)
INPUT_BORDER_FOCUS = GOLD
INPUT_TEXT = (235, 238, 245)
INPUT_PLACEHOLDER = (110, 116, 128)


# =========================================================
# Lock badge helper
# =========================================================
def draw_lock_badge(screen, cx, cy, size=14):
  cx, cy = int(cx), int(cy)
  pygame.draw.circle(screen, (25, 28, 35), (cx, cy), size // 2 + 3)
  x = cx - size // 2
  y = cy - size // 2
  body = pygame.Rect(x, y + 4, size, size - 4)
  pygame.draw.arc(screen, GOLD, (x + 2, y - 1, size - 4, size - 1), 0, math.pi, 2)
  pygame.draw.rect(screen, GOLD, body, border_radius=2)
  pygame.draw.rect(screen, (20, 20, 20), body, 1, border_radius=2)
  pygame.draw.circle(screen, (20, 20, 20), (cx, body.y + body.h // 2 - 1), 2)


# =========================================================
# Scene objects
# =========================================================
class EditorPeg:
  def __init__(self, x, y):
    self.x, self.y = x, y
    self.r = PEG_R
    self.locked = False

  def hit(self, wx, wy):
    return (wx - self.x) ** 2 + (wy - self.y) ** 2 <= self.r ** 2

  def intersects_rect(self, l, r, b, t):
    nx = max(l, min(self.x, r))
    ny = max(b, min(self.y, t))
    return (self.x - nx) ** 2 + (self.y - ny) ** 2 <= self.r ** 2

  def to_json(self):
    if self.locked:
      return [int(self.x), int(self.y), 1]
    return [int(self.x), int(self.y)]

  def draw(self, screen, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    pygame.draw.circle(screen, PEG_FILL, (int(sx), int(sy)), self.r)
    pygame.draw.circle(screen, PEG_EDGE, (int(sx), int(sy)), self.r, 4)
    if self.locked:
      draw_lock_badge(screen, sx + self.r + 2, sy - self.r - 2)


class EditorPlatform:
  def __init__(self, x, y, w=PLAT_DEFAULT_W, h=PLAT_DEFAULT_H):
    self.x, self.y = x, y
    self.w, self.h = w, h
    self.fill = PLAT_FILL
    self.edge = PLAT_EDGE
    self.locked = False

  def world_rect(self):
    return (self.x - self.w / 2, self.x + self.w / 2,
            self.y - self.h / 2, self.y + self.h / 2)

  def hit(self, wx, wy):
    l, r, b, t = self.world_rect()
    return l <= wx <= r and b <= wy <= t

  def intersects_rect(self, l, r, b, t):
    ol, orr, ob, ot = self.world_rect()
    return not (orr < l or ol > r or ot < b or ob > t)

  def edge_hit(self, wx, wy):
    l, r, b, t = self.world_rect()
    in_x = l - RESIZE_ZONE <= wx <= r + RESIZE_ZONE
    in_y = b - RESIZE_ZONE <= wy <= t + RESIZE_ZONE
    if not (in_x and in_y):
      return None
    if abs(wx - l) <= RESIZE_ZONE:
      return "left"
    if abs(wx - r) <= RESIZE_ZONE:
      return "right"
    if abs(wy - t) <= RESIZE_ZONE:
      return "top"
    if abs(wy - b) <= RESIZE_ZONE:
      return "bottom"
    return None

  def to_json(self):
    return {
      "x": int(self.x), "y": int(self.y),
      "w": int(self.w), "h": int(self.h),
      "fill": list(self.fill), "edge": list(self.edge),
      "locked": bool(self.locked),
    }

  def draw(self, screen, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, y1 = ed.to_screen(r, b)
    rect = pygame.Rect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))
    pygame.draw.rect(screen, self.fill, rect)
    pygame.draw.rect(screen, self.edge, rect, PLAT_EDGE_W)
    if self.locked:
      draw_lock_badge(screen, rect.right - 12, rect.top + 12)


class EditorBackground:
  def __init__(self, x, y, w=PLAT_DEFAULT_W, h=PLAT_DEFAULT_H):
    self.x, self.y = x, y
    self.w, self.h = w, h
    self.fill = BG_DEFAULT_COLOR
    self.locked = False

  def world_rect(self):
    return (self.x - self.w / 2, self.x + self.w / 2,
            self.y - self.h / 2, self.y + self.h / 2)

  def hit(self, wx, wy):
    l, r, b, t = self.world_rect()
    return l <= wx <= r and b <= wy <= t

  def intersects_rect(self, l, r, b, t):
    ol, orr, ob, ot = self.world_rect()
    return not (orr < l or ol > r or ot < b or ob > t)

  def edge_hit(self, wx, wy):
    l, r, b, t = self.world_rect()
    in_x = l - RESIZE_ZONE <= wx <= r + RESIZE_ZONE
    in_y = b - RESIZE_ZONE <= wy <= t + RESIZE_ZONE
    if not (in_x and in_y):
      return None
    if abs(wx - l) <= RESIZE_ZONE:
      return "left"
    if abs(wx - r) <= RESIZE_ZONE:
      return "right"
    if abs(wy - t) <= RESIZE_ZONE:
      return "top"
    if abs(wy - b) <= RESIZE_ZONE:
      return "bottom"
    return None

  def to_json(self):
    return {
      "x": int(self.x), "y": int(self.y),
      "w": int(self.w), "h": int(self.h),
      "color": list(self.fill),
      "locked": bool(self.locked),
    }

  def draw(self, screen, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, y1 = ed.to_screen(r, b)
    rect = pygame.Rect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))
    pygame.draw.rect(screen, self.fill, rect)
    if self.locked:
      draw_lock_badge(screen, rect.right - 12, rect.top + 12)


# =========================================================
# UI widgets
# =========================================================
class Widget:
  def __init__(self, x, y, w, h):
    self.rect = pygame.Rect(int(x), int(y), int(w), int(h))
    self.visible = True
    self.enabled = True

  def draw(self, screen, font, origin=(0, 0)):
    pass

  def on_event(self, e, origin=(0, 0)):
    return False

  def update(self, dt):
    pass

  def screen_rect(self, origin=(0, 0)):
    return self.rect.move(origin)


class UIButton(Widget):
  def __init__(self, x, y, w, h, label, on_click=None):
    super().__init__(x, y, w, h)
    self.label = label
    self.on_click = on_click
    self.hover = False
    self.pressed = False

  def _colors(self):
    if not self.enabled:
      return (45, 48, 55), BTN_TEXT_DIM, BTN_BORDER
    if self.pressed:
      return BTN_BG_PRESS, BTN_TEXT, BTN_BORDER
    if self.hover:
      return BTN_BG_HOVER, BTN_TEXT, BTN_BORDER
    return BTN_BG, BTN_TEXT, BTN_BORDER

  def draw(self, screen, font, origin=(0, 0)):
    if not self.visible:
      return
    r = self.screen_rect(origin)
    bg, fg, border = self._colors()
    pygame.draw.rect(screen, bg, r, border_radius=4)
    pygame.draw.rect(screen, border, r, 1, border_radius=4)
    surf = font.render(self.label, True, fg)
    screen.blit(surf, surf.get_rect(center=r.center))

  def on_event(self, e, origin=(0, 0)):
    if not (self.visible and self.enabled):
      return False
    r = self.screen_rect(origin)
    if e.type == pygame.MOUSEMOTION:
      self.hover = r.collidepoint(e.pos)
    elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
      if r.collidepoint(e.pos):
        self.pressed = True
        return True
    elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
      was = self.pressed
      self.pressed = False
      if was:
        if r.collidepoint(e.pos) and self.on_click:
          self.on_click()
        return True
    return False


class UIToggleButton(UIButton):
  def __init__(self, x, y, w, h, label, on_toggle=None):
    super().__init__(x, y, w, h, label)
    self.active = False
    self.on_toggle = on_toggle

  def _colors(self):
    if not self.enabled:
      return (45, 48, 55), BTN_TEXT_DIM, BTN_BORDER
    if self.pressed:
      return BTN_BG_PRESS, BTN_TEXT, GOLD if self.active else BTN_BORDER
    if self.active:
      return BTN_BG_ACTIVE, BTN_TEXT, GOLD
    if self.hover:
      return BTN_BG_HOVER, BTN_TEXT, BTN_BORDER
    return BTN_BG, BTN_TEXT, BTN_BORDER

  def draw(self, screen, font, origin=(0, 0)):
    if not self.visible:
      return
    r = self.screen_rect(origin)
    bg, fg, border = self._colors()
    pygame.draw.rect(screen, bg, r, border_radius=4)
    pygame.draw.rect(screen, border, r, 2 if self.active else 1, border_radius=4)
    surf = font.render(self.label, True, fg)
    screen.blit(surf, surf.get_rect(center=r.center))

  def on_event(self, e, origin=(0, 0)):
    if not (self.visible and self.enabled):
      return False
    r = self.screen_rect(origin)
    if e.type == pygame.MOUSEMOTION:
      self.hover = r.collidepoint(e.pos)
    elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
      if r.collidepoint(e.pos):
        self.pressed = True
        return True
    elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
      was = self.pressed
      self.pressed = False
      if was and r.collidepoint(e.pos):
        self.active = not self.active
        if self.on_toggle:
          self.on_toggle(self.active)
        return True
    return False


class UITextInput(Widget):
  """Kept for future use; not instantiated in the current top panel."""

  def __init__(self, x, y, w, h, placeholder="", text=""):
    super().__init__(x, y, w, h)
    self.text = text
    self.placeholder = placeholder
    self.focused = False
    self.cursor_blink = 0.0

  def update(self, dt):
    self.cursor_blink = (self.cursor_blink + dt) % 1.0

  def draw(self, screen, font, origin=(0, 0)):
    if not self.visible:
      return
    r = self.screen_rect(origin)
    pygame.draw.rect(screen, INPUT_BG, r, border_radius=4)
    border = INPUT_BORDER_FOCUS if self.focused else INPUT_BORDER
    pygame.draw.rect(screen, border, r, 1, border_radius=4)
    pad = 8
    if self.text:
      surf = font.render(self.text, True, INPUT_TEXT)
    else:
      surf = font.render(self.placeholder, True, INPUT_PLACEHOLDER)
    screen.blit(surf, (r.x + pad, r.centery - surf.get_height() // 2))
    if self.focused and self.cursor_blink < 0.5:
      cx = r.x + pad + font.size(self.text)[0]
      pygame.draw.line(screen, INPUT_TEXT, (cx, r.y + 6), (cx, r.bottom - 6))

  def on_event(self, e, origin=(0, 0)):
    if not (self.visible and self.enabled):
      return False
    r = self.screen_rect(origin)
    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
      if r.collidepoint(e.pos):
        self.focused = True
        self.cursor_blink = 0.0
        return True
      if self.focused:
        self.focused = False
      return False
    if self.focused and e.type == pygame.KEYDOWN:
      if e.key == pygame.K_BACKSPACE:
        self.text = self.text[:-1]
        return True
      if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
        self.focused = False
        return True
      if e.unicode and e.unicode.isprintable():
        self.text += e.unicode
        return True
      return True
    return False


# =========================================================
# Top panel
# =========================================================
class TopPanel:
  def __init__(self, editor):
    self.editor = editor
    self.font_small = pygame.font.SysFont(None, 20)
    self.font_body = pygame.font.SysFont(None, 22)
    self.expanded = True

    self.header_widgets = []
    self.body_widgets = []

    self.toggle_btn = UIButton(0, 0, 84, PANEL_HEADER_H - 10,
                               "Hide", self._toggle)
    self.header_widgets.append(self.toggle_btn)

    self.lock_btn = UIToggleButton(0, 0, 120, PANEL_WIDGET_H,
                                   "Lock tool", self._on_lock_toggle)
    self.zone_unlock_btn = UIToggleButton(0, 0, 140, PANEL_WIDGET_H,
                                          "Zone unlock", self._on_zone_toggle)
    self.undo_btn = UIButton(0, 0, 80, PANEL_WIDGET_H, "Undo", editor.undo)
    self.redo_btn = UIButton(0, 0, 80, PANEL_WIDGET_H, "Redo", editor.redo)
    self.save_btn = UIButton(0, 0, 88, PANEL_WIDGET_H, "Save", editor.save)
    self.load_btn = UIButton(0, 0, 88, PANEL_WIDGET_H, "Load", editor.load)
    self.body_widgets.extend([self.lock_btn, self.zone_unlock_btn,
                              self.undo_btn, self.redo_btn,
                              self.save_btn, self.load_btn])

    self.layout(editor.screen.get_width())

  def height(self):
    return PANEL_HEADER_H + (PANEL_BODY_H if self.expanded else 0)

  def layout(self, screen_w):
    pad = 10
    tw, th = self.toggle_btn.rect.size
    self.toggle_btn.rect.topleft = (screen_w - pad - tw,
                                    (PANEL_HEADER_H - th) // 2)
    x = pad
    y = PANEL_HEADER_H + (PANEL_BODY_H - PANEL_WIDGET_H) // 2
    for w in self.body_widgets:
      w.rect.x = x
      w.rect.y = y
      x += w.rect.width + pad

  def _toggle(self):
    self.expanded = not self.expanded
    self.toggle_btn.label = "Hide" if self.expanded else "Show"
    self.layout(self.editor.screen.get_width())

  def _on_lock_toggle(self, active):
    if active:
      self.editor.set_tool("lock")
    else:
      if self.editor.tool == "lock":
        self.editor.set_tool("select")

  def _on_zone_toggle(self, active):
    if active:
      self.editor.set_tool("unlock_zone")
    else:
      if self.editor.tool == "unlock_zone":
        self.editor.set_tool("select")

  def sync_tool(self, name):
    self.lock_btn.active = (name == "lock")
    self.zone_unlock_btn.active = (name == "unlock_zone")

  def _active_widgets(self):
    return list(self.header_widgets) + (list(self.body_widgets) if self.expanded else [])

  def wants_keyboard(self):
    return any(getattr(w, "focused", False) for w in self._active_widgets())

  def on_event(self, e):
    consumed = False
    for w in self._active_widgets():
      if w.on_event(e, (0, 0)):
        consumed = True
    if e.type == pygame.MOUSEBUTTONDOWN and e.pos[1] < self.height():
      return True
    return consumed

  def update(self, dt):
    for w in self._active_widgets():
      w.update(dt)

  def draw(self, screen):
    h = self.height()
    pygame.draw.rect(screen, PANEL_BG, (0, 0, screen.get_width(), h))
    pygame.draw.line(screen, PANEL_BORDER,
                     (0, h - 1), (screen.get_width(), h - 1))
    title = self.font_small.render("Level editor", True, PANEL_TITLE)
    screen.blit(title, (10, (PANEL_HEADER_H - title.get_height()) // 2))
    for w in self.header_widgets:
      w.draw(screen, self.font_small, (0, 0))
    if self.expanded:
      for w in self.body_widgets:
        w.draw(screen, self.font_body, (0, 0))


# =========================================================
# Editor
# =========================================================
class Editor:
  def __init__(self):
    pygame.init()
    self.screen = pygame.display.set_mode((1280, 800))
    pygame.display.set_caption("level editor")
    self.clock = pygame.time.Clock()
    self.font = pygame.font.SysFont(None, 22)
    self.running = True
    self.tool = "select"
    self.objects = []
    # ---- selection ----
    self.selection = []
    self.selected = None
    # ---- drag ----
    self.drag = None
    self._move_data = []
    self._move_start = None
    self._resize_data = []
    # ---- camera ----
    self.cam_x = 0
    self.cam_y = 0
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
    self.cursor = None
    self._lock_cursor = self._make_lock_cursor()
    self.panel = TopPanel(self)

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
      return {"t": "peg", "x": o.x, "y": o.y, "locked": o.locked}
    if isinstance(o, EditorPlatform):
      return {"t": "plat", "x": o.x, "y": o.y, "w": o.w, "h": o.h,
              "fill": tuple(o.fill), "edge": tuple(o.edge), "locked": o.locked}
    if isinstance(o, EditorBackground):
      return {"t": "bg", "x": o.x, "y": o.y, "w": o.w, "h": o.h,
              "fill": tuple(o.fill), "locked": o.locked}
    return None

  def _make_from_state(self, s):
    t = s["t"]
    if t == "peg":
      o = EditorPeg(s["x"], s["y"])
    elif t == "plat":
      o = EditorPlatform(s["x"], s["y"], s["w"], s["h"])
      o.fill = tuple(s["fill"]); o.edge = tuple(s["edge"])
    else:
      o = EditorBackground(s["x"], s["y"], s["w"], s["h"])
      o.fill = tuple(s["fill"])
    o.locked = s["locked"]
    return o

  def _snapshot(self):
    return [self._obj_to_state(o) for o in self.objects]

  def _restore(self, snap):
    self.objects = [self._make_from_state(s) for s in snap]
    self._clear_selection()

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
    self._resize_data = []
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
      new.append(self._make_from_state(s2))
    self.objects.extend(new)
    self._set_selection(new)
    self._push_undo_now(before)

  def duplicate_selected(self):
    if not self.selection:
      return
    before = self._snapshot()
    new = []
    for obj in self.selection:
      s = self._obj_to_state(obj)
      s["x"] += PASTE_OFFSET
      s["y"] -= PASTE_OFFSET
      new.append(self._make_from_state(s))
    self.objects.extend(new)
    self._set_selection(new)
    self._push_undo_now(before)

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
    self.objects = keep
    if removed:
      self.selected = self.selection[-1] if self.selection else None

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
    if l == r and b == t:
      for obj in reversed(self.objects):
        if obj.hit(l, b):
          obj.locked = False
          return
      return
    for obj in self.objects:
      if obj.locked and obj.intersects_rect(l, r, b, t):
        obj.locked = False

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
  def _begin_move(self, wx, wy):
    self._move_data = [(obj, obj.x, obj.y) for obj in self.selection if not obj.locked]
    self._move_start = (wx, wy)
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

  # =========================================================
  # Coordinates
  # =========================================================
  def to_screen(self, wx, wy):
    sw, sh = self.screen.get_size()
    return wx - self.cam_x + sw / 2, sh / 2 - (wy - self.cam_y)

  def from_screen(self, sx, sy):
    sw, sh = self.screen.get_size()
    return sx - sw / 2 + self.cam_x, sh / 2 - sy + self.cam_y

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
    if self.panel.on_event(e):
      return
    if self.panel.wants_keyboard() and e.type == pygame.KEYDOWN \
       and e.key != pygame.K_ESCAPE:
      return

    if e.type == pygame.KEYDOWN:
      self._on_keydown(e)
      return

    if e.type == pygame.MOUSEBUTTONDOWN and e.button in (2, 3):
      self.panning = True
      self.pan_last = e.pos
    elif e.type == pygame.MOUSEBUTTONUP and e.button in (2, 3):
      self.panning = False
    elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
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
      self._resize_data = []
      self.commit_undo()
    elif e.type == pygame.MOUSEMOTION:
      if self.panning:
        dx = e.pos[0] - self.pan_last[0]
        dy = e.pos[1] - self.pan_last[1]
        self.cam_x -= dx
        self.cam_y += dy
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
      elif e.key == pygame.K_l:
        self.set_tool("select" if self.tool == "lock" else "lock")
      return

    if e.key == pygame.K_ESCAPE:
      self.running = False
    elif e.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
      self.delete_selected()
    elif e.key == pygame.K_SPACE:
      self.cam_x, self.cam_y = self.ghost[0], self.ghost[1]
    elif e.key == pygame.K_0:
      self.set_tool("select")
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
    elif e.key == pygame.K_l:
      self.set_tool("lock")
    elif e.key == pygame.K_u:
      self.set_tool("unlock_zone")

  # =========================================================
  # Mouse down
  # =========================================================
  def on_mouse_down(self, pos):
    x, y = pos
    sh = self.screen.get_height()
    if y >= sh - BOT_H:
      if self.tab_select_rect().collidepoint(pos):
        self.set_tool("select")
      elif self.tab_ghost_rect().collidepoint(pos):
        self.set_tool("ghost")
      elif self.tab_eraser_rect().collidepoint(pos):
        self.set_tool("eraser")
      elif self.tab_peg_rect().collidepoint(pos):
        self.set_tool("peg")
      elif self.tab_plat_rect().collidepoint(pos):
        self.set_tool("platform")
      elif self.tab_bg_rect().collidepoint(pos):
        self.set_tool("background")
      return

    wx, wy = self.from_screen(x, y)
    ctrl = bool(pygame.key.get_mods() & pygame.KMOD_CTRL)

    # --- zone unlock ---
    if self.tool == "unlock_zone":
      self.drag = ("zone_unlock", None)
      self.zone_start = (wx, wy)
      self.zone_now = (wx, wy)
      return

    # --- eraser ---
    if self.tool == "eraser":
      self.erasing = True
      self._erase_prev = (wx, wy)
      self._erase_at(wx, wy)
      return

    # --- lock ---
    if self.tool == "lock":
      for obj in reversed(self.objects):
        if obj.hit(wx, wy):
          obj.locked = not obj.locked
          if obj.locked and obj in self.selection:
            self.selection.remove(obj)
            self.selected = self.selection[-1] if self.selection else None
          return
      return

    # --- resize on selected object's edge (any tool, including select) ---
    if isinstance(self.selected, (EditorPlatform, EditorBackground)) \
       and not self.selected.locked:
      edge = self.selected.edge_hit(wx, wy)
      if edge:
        self._begin_resize(edge)
        return

    # --- pick object ---
    hit = None
    for obj in reversed(self.objects):
      if obj.locked:
        continue
      if obj.hit(wx, wy):
        hit = obj
        break

    if hit is not None:
      if self.tool == "select" and ctrl:
        self._toggle_selection(hit)
        return
      if hit not in self.selection:
        self._set_selection([hit])
      self._begin_move(wx, wy)
      return

    # --- select tool: rubber band on empty space ---
    if self.tool == "select":
      self._begin_select_rect(wx, wy)
      return

    # --- ghost ---
    gx, gy = self.ghost
    if (wx - gx) ** 2 + (wy - gy) ** 2 <= PLAYER_R ** 2:
      self.drag = ("ghost", (wx - gx, wy - gy))
      return
    if self.tool == "ghost":
      self.ghost_target = [wx, wy]
      return

    # --- create new object ---
    if self.tool == "peg":
      obj = EditorPeg(wx, wy)
      self.objects.append(obj)
      self._set_selection([obj])
      self._begin_move(wx, wy)
    elif self.tool in ("platform", "background"):
      if self.tool == "background":
        obj = EditorBackground(wx, wy, 1, 1)
      else:
        obj = EditorPlatform(wx, wy, 1, 1)
      self.objects.append(obj)
      self._set_selection([obj])
      self.drag = ("create", (wx, wy))

  # =========================================================
  # Mouse move
  # =========================================================
  def on_mouse_move(self, world):
    wx, wy = world
    if self.drag is None:
      return
    mode, data = self.drag

    if mode == "move":
      if not self._move_data or self._move_start is None:
        return
      sx, sy = self._move_start
      dx = wx - sx
      dy = wy - sy
      for obj, ox, oy in self._move_data:
        if obj.locked:
          continue
        obj.x = ox + dx
        obj.y = oy + dy
      return

    if mode == "ghost":
      dx, dy = data
      self.ghost[0] = wx - dx
      self.ghost[1] = wy - dy
      self.ghost_target = [self.ghost[0], self.ghost[1]]
      return

    if mode == "create":
      ox, oy = data
      l = min(ox, wx); r = max(ox, wx)
      b = min(oy, wy); t = max(oy, wy)
      obj = self.selected
      if obj is None:
        return
      obj.w = max(r - l, 1)
      obj.h = max(t - b, 1)
      obj.x = (l + r) / 2
      obj.y = (b + t) / 2
      return

    if mode == "resize":
      edge = data
      if not self._resize_data:
        return
      # find primary's original rect
      primary_orig = None
      for obj, r in self._resize_data:
        if obj is self.selected:
          primary_orig = r
          break
      if primary_orig is None:
        primary_orig = self._resize_data[0][1]
      pl, pr, pb, pt = primary_orig

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
      return

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
      edge = self.selected.edge_hit(wx, wy)
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
    self.screen.fill(BG)
    for obj in self.objects:
      if isinstance(obj, EditorBackground):
        obj.draw(self.screen, self)
    self.draw_floor_line()
    self.draw_ghost()
    for obj in self.objects:
      if not isinstance(obj, EditorBackground):
        obj.draw(self.screen, self)

    # selection markers
    for obj in self.selection:
      sx, sy = self.to_screen(obj.x, obj.y)
      pygame.draw.circle(self.screen, GREEN, (int(sx), int(sy)), 6)

    self.draw_zone_preview()
    self.draw_select_rect_preview()
    self.draw_bottom_bar()
    self.panel.draw(self.screen)

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
    self.draw_ghost_line(sx, sy)
    self.draw_ghost_arm(sx, sy, -ARM_DX)
    self.draw_ghost_arm(sx, sy, ARM_DX)
    surf = pygame.Surface((PLAYER_R * 2, PLAYER_R * 2), pygame.SRCALPHA)
    pygame.draw.circle(surf, (255, 255, 255, GHOST_ALPHA), (PLAYER_R, PLAYER_R), PLAYER_R)
    self.screen.blit(surf, (sx - PLAYER_R, sy - PLAYER_R))

  def draw_ghost_line(self, sx, sy):
    ex, ey = self.to_screen(self.ghost[0], self.ghost[1] + JUMP_H)
    surf = pygame.Surface((2, int(sy - ey)), pygame.SRCALPHA)
    surf.fill((255, 255, 255, JUMP_ALPHA))
    self.screen.blit(surf, (int(sx) - 1, int(ey)))
    cap = pygame.Surface((10, 2), pygame.SRCALPHA)
    cap.fill((255, 255, 255, JUMP_ALPHA))
    self.screen.blit(cap, (int(sx) - 5, int(ey) - 1))

  def draw_ghost_arm(self, sx, sy, dx):
    ax = sx + dx
    size = ARM_R * 2 + 4
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(surf, (255, 255, 255, ARM_ALPHA), (size // 2, size // 2), ARM_R)
    self.screen.blit(surf, (ax - size // 2, sy - size // 2))

  def draw_bottom_bar(self):
    h = self.screen.get_height()
    pygame.draw.rect(self.screen, UI_BG, (0, h - BOT_H, self.screen.get_width(), BOT_H))
    self.draw_tab(self.tab_select_rect(), "select", self.tool == "select")
    self.draw_tab(self.tab_ghost_rect(), "ghost", self.tool == "ghost")
    self.draw_tab(self.tab_eraser_rect(), "eraser", self.tool == "eraser")
    self.draw_tab(self.tab_peg_rect(), "peg", self.tool == "peg")
    self.draw_tab(self.tab_plat_rect(), "platform", self.tool == "platform")
    self.draw_tab(self.tab_bg_rect(), "background", self.tool == "background")

  def draw_tab(self, r, name, active):
    pygame.draw.rect(self.screen, (45, 50, 60), r)
    color = GOLD if active else GREY
    pygame.draw.rect(self.screen, color, r, 3 if active else 2)
    cx, cy = r.center
    if name == "select":
      rr = pygame.Rect(0, 0, 88, 32)
      rr.center = r.center
      for i in range(0, rr.w, 8):
        pygame.draw.line(self.screen, SEL_BLUE, (rr.x + i, rr.y),
                         (rr.x + min(i + 4, rr.w), rr.y), 2)
        pygame.draw.line(self.screen, SEL_BLUE, (rr.x + i, rr.bottom - 1),
                         (rr.x + min(i + 4, rr.w), rr.bottom - 1), 2)
      for i in range(0, rr.h, 8):
        pygame.draw.line(self.screen, SEL_BLUE, (rr.x, rr.y + i),
                         (rr.x, rr.y + min(i + 4, rr.h)), 2)
        pygame.draw.line(self.screen, SEL_BLUE, (rr.right - 1, rr.y + i),
                         (rr.right - 1, rr.y + min(i + 4, rr.h)), 2)
    elif name == "peg":
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
    else:
      rr = pygame.Rect(0, 0, 100, 40)
      rr.center = r.center
      pygame.draw.rect(self.screen, PLAT_FILL, rr)
      pygame.draw.rect(self.screen, PLAT_EDGE, rr, PLAT_EDGE_W)

  # =========================================================
  # Bottom tabs (select, ghost, eraser, peg, platform, background)
  # =========================================================
  def tab_select_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(10, h - BOT_H + 6, 120, BOT_H - 12)

  def tab_ghost_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(140, h - BOT_H + 6, 120, BOT_H - 12)

  def tab_eraser_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(270, h - BOT_H + 6, 120, BOT_H - 12)

  def tab_peg_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(400, h - BOT_H + 6, 120, BOT_H - 12)

  def tab_plat_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(530, h - BOT_H + 6, 120, BOT_H - 12)

  def tab_bg_rect(self):
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
    with open(path, "w") as f:
      json.dump({"pegs": pegs, "platforms": platforms, "backgrounds": backgrounds}, f, indent=2)

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
      self.objects.append(obj)
    for bd in data.get("backgrounds", []):
      obj = EditorBackground(bd["x"], bd["y"], bd.get("w", PLAT_DEFAULT_W), bd.get("h", PLAT_DEFAULT_H))
      obj.fill = tuple(bd.get("color", BG_DEFAULT_COLOR))
      obj.locked = bool(bd.get("locked", False))
      self.objects.append(obj)
    self._clear_selection()
    self._push_undo_now(before)