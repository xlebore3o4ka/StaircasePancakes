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
  ITEM_TYPES,
  SODA_W, SODA_H, SODA_BLUE, SODA_WHITE,
  CUBE_FILL, CUBE_EDGE, CUBE_EDGE_W,
  LAYER_BG, LAYER_FLOOR, LAYER_PLATFORM, LAYER_PEG, LAYER_ITEM, LAYER_PLAYER,
)

# ---- layout ----
BOT_H = 70
BG = (50, 55, 65)
UI_BG = (30, 33, 40)
GOLD = (255, 215, 0)
GREY = (110, 110, 110)
GREEN = (60, 220, 100)
SEL_BLUE = (100, 200, 255)
SNAP_COLOR = (255, 90, 200)
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
SNAP_DIST = 6.0

# ghost рисуется чуть выше пола и всегда под платформами, если у объектов дефолтные слои
GHOST_LAYER = LAYER_FLOOR + 1

# ---- zoom ----
ZOOM_MIN = 0.25
ZOOM_MAX = 4.0
ZOOM_STEP = 1.15

# ---- lock overlays ----
STRIPE_COLOR = (255, 215, 0, 60)
STRIPE_STEP = 16
STRIPE_WIDTH = 3

# ---- items ----
ITEM_SIZE_MAP = {
  "cube": (30, 30),
  "soda": (SODA_W, SODA_H),
}
DEFAULT_ITEM_SIZE = (30, 30)
DEFAULT_ITEM_TYPE = ITEM_TYPES[0] if ITEM_TYPES else "cube"


def item_size(t):
  return ITEM_SIZE_MAP.get(t, DEFAULT_ITEM_SIZE)


def default_layer_for(obj):
  if isinstance(obj, EditorBackground):
    return LAYER_BG
  if isinstance(obj, EditorPlatform):
    return LAYER_PLATFORM
  if isinstance(obj, EditorPeg):
    return LAYER_PEG
  if isinstance(obj, EditorItem):
    return LAYER_ITEM
  return 0


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

# ---- context menu ----
MENU_BG = (35, 38, 45)
MENU_BORDER = (90, 96, 110)
MENU_HOVER = (60, 66, 78)
MENU_TITLE_FG = (180, 185, 195)
MENU_SEP = (70, 76, 88)


# =========================================================
# Text cache
# =========================================================
_TEXT_CACHE = {}


def render_text(font, text, color):
  key = (id(font), text, color)
  surf = _TEXT_CACHE.get(key)
  if surf is None:
    surf = font.render(text, True, color)
    _TEXT_CACHE[key] = surf
  return surf


# =========================================================
# Lock overlay helpers
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


_STRIPE_RECT_CACHE = {}
_STRIPE_CIRCLE_CACHE = {}
_CACHE_LIMIT = 64


def make_stripe_surface(w, h):
  w = max(1, int(w))
  h = max(1, int(h))
  key = (w, h)
  surf = _STRIPE_RECT_CACHE.get(key)
  if surf is not None:
    return surf
  surf = pygame.Surface((w, h), pygame.SRCALPHA)
  for offset in range(-h, w + 1, STRIPE_STEP):
    pygame.draw.line(surf, STRIPE_COLOR,
                     (offset, h), (offset + h, 0), STRIPE_WIDTH)
  if len(_STRIPE_RECT_CACHE) > _CACHE_LIMIT:
    _STRIPE_RECT_CACHE.clear()
  _STRIPE_RECT_CACHE[key] = surf
  return surf


def make_circle_stripe_surface(r):
  r = max(1, int(r))
  key = r
  surf = _STRIPE_CIRCLE_CACHE.get(key)
  if surf is not None:
    return surf
  d = r * 2
  surf = pygame.Surface((d, d), pygame.SRCALPHA)
  for offset in range(-d, d + 1, STRIPE_STEP):
    pygame.draw.line(surf, STRIPE_COLOR,
                     (offset, d), (offset + d, 0), STRIPE_WIDTH)
  mask = pygame.Surface((d, d), pygame.SRCALPHA)
  pygame.draw.circle(mask, (255, 255, 255, 255), (r, r), r)
  surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
  if len(_STRIPE_CIRCLE_CACHE) > _CACHE_LIMIT:
    _STRIPE_CIRCLE_CACHE.clear()
  _STRIPE_CIRCLE_CACHE[key] = surf
  return surf


# =========================================================
# Scene objects
# =========================================================
class EditorPeg:
  def __init__(self, x, y):
    self.x, self.y = x, y
    self.r = PEG_R
    self.locked = False
    self.layer = None

  def hit(self, wx, wy):
    return (wx - self.x) ** 2 + (wy - self.y) ** 2 <= self.r ** 2

  def intersects_rect(self, l, r, b, t):
    nx = max(l, min(self.x, r))
    ny = max(b, min(self.y, t))
    return (self.x - nx) ** 2 + (self.y - ny) ** 2 <= self.r ** 2

  def to_json(self):
    return [int(self.x), int(self.y)]

  def badge_screen_pos(self, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    r = self.r * ed.zoom
    return sx + r + 2, sy - r - 2

  def draw(self, screen, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    r = max(1, int(self.r * ed.zoom))
    pygame.draw.circle(screen, PEG_FILL, (int(sx), int(sy)), r)
    edge_w = max(1, int(4 * ed.zoom))
    pygame.draw.circle(screen, PEG_EDGE, (int(sx), int(sy)), r, edge_w)
    if self.locked:
      screen.blit(make_circle_stripe_surface(r),
                  (int(sx) - r, int(sy) - r))


class EditorPlatform:
  def __init__(self, x, y, w=PLAT_DEFAULT_W, h=PLAT_DEFAULT_H):
    self.x, self.y = x, y
    self.w, self.h = w, h
    self.fill = PLAT_FILL
    self.edge = PLAT_EDGE
    self.locked = False
    self.layer = None

  def world_rect(self):
    return (self.x - self.w / 2, self.x + self.w / 2,
            self.y - self.h / 2, self.y + self.h / 2)

  def hit(self, wx, wy):
    l, r, b, t = self.world_rect()
    return l <= wx <= r and b <= wy <= t

  def intersects_rect(self, l, r, b, t):
    ol, orr, ob, ot = self.world_rect()
    return not (orr < l or ol > r or ot < b or ob > t)

  def edge_hit(self, wx, wy, zone=RESIZE_ZONE):
    l, r, b, t = self.world_rect()
    in_x = l - zone <= wx <= r + zone
    in_y = b - zone <= wy <= t + zone
    if not (in_x and in_y):
      return None
    if abs(wx - l) <= zone:
      return "left"
    if abs(wx - r) <= zone:
      return "right"
    if abs(wy - t) <= zone:
      return "top"
    if abs(wy - b) <= zone:
      return "bottom"
    return None

  def to_json(self):
    d = {
      "x": int(self.x), "y": int(self.y),
      "w": int(self.w), "h": int(self.h),
      "fill": list(self.fill), "edge": list(self.edge),
      "locked": bool(self.locked),
    }
    if self.layer is not None:
      d["layer"] = int(self.layer)
    return d

  def badge_screen_pos(self, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, _ = ed.to_screen(r, t)
    return x1 - 12, y0 + 12

  def draw(self, screen, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, y1 = ed.to_screen(r, b)
    rect = pygame.Rect(int(min(x0, x1)), int(min(y0, y1)),
                       int(abs(x1 - x0)), int(abs(y1 - y0)))
    pygame.draw.rect(screen, self.fill, rect)
    pygame.draw.rect(screen, self.edge, rect, PLAT_EDGE_W)
    if self.locked:
      screen.blit(make_stripe_surface(rect.w, rect.h), rect.topleft)


class EditorBackground:
  def __init__(self, x, y, w=PLAT_DEFAULT_W, h=PLAT_DEFAULT_H):
    self.x, self.y = x, y
    self.w, self.h = w, h
    self.fill = BG_DEFAULT_COLOR
    self.locked = False
    self.layer = None

  def world_rect(self):
    return (self.x - self.w / 2, self.x + self.w / 2,
            self.y - self.h / 2, self.y + self.h / 2)

  def hit(self, wx, wy):
    l, r, b, t = self.world_rect()
    return l <= wx <= r and b <= wy <= t

  def intersects_rect(self, l, r, b, t):
    ol, orr, ob, ot = self.world_rect()
    return not (orr < l or ol > r or ot < b or ob > t)

  def edge_hit(self, wx, wy, zone=RESIZE_ZONE):
    l, r, b, t = self.world_rect()
    in_x = l - zone <= wx <= r + zone
    in_y = b - zone <= wy <= t + zone
    if not (in_x and in_y):
      return None
    if abs(wx - l) <= zone:
      return "left"
    if abs(wx - r) <= zone:
      return "right"
    if abs(wy - t) <= zone:
      return "top"
    if abs(wy - b) <= zone:
      return "bottom"
    return None

  def to_json(self):
    d = {
      "x": int(self.x), "y": int(self.y),
      "w": int(self.w), "h": int(self.h),
      "color": list(self.fill),
      "locked": bool(self.locked),
    }
    if self.layer is not None:
      d["layer"] = int(self.layer)
    return d

  def badge_screen_pos(self, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, _ = ed.to_screen(r, t)
    return x1 - 12, y0 + 12

  def draw(self, screen, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, y1 = ed.to_screen(r, b)
    rect = pygame.Rect(int(min(x0, x1)), int(min(y0, y1)),
                       int(abs(x1 - x0)), int(abs(y1 - y0)))
    pygame.draw.rect(screen, self.fill, rect)
    if self.locked:
      screen.blit(make_stripe_surface(rect.w, rect.h), rect.topleft)


class EditorItem:
  def __init__(self, x, y, item_type=DEFAULT_ITEM_TYPE):
    self.x, self.y = x, y
    self.item_type = item_type
    self.w, self.h = item_size(item_type)
    self.locked = False
    self.layer = None

  def set_type(self, t):
    self.item_type = t
    self.w, self.h = item_size(t)

  def world_rect(self):
    return (self.x - self.w / 2, self.x + self.w / 2,
            self.y - self.h / 2, self.y + self.h / 2)

  def hit(self, wx, wy):
    l, r, b, t = self.world_rect()
    return l <= wx <= r and b <= wy <= t

  def intersects_rect(self, l, r, b, t):
    ol, orr, ob, ot = self.world_rect()
    return not (orr < l or ol > r or ot < b or ob > t)

  def badge_screen_pos(self, ed):
    l, r, b, t = self.world_rect()
    _, y0 = ed.to_screen(l, t)
    x1, _ = ed.to_screen(r, t)
    return x1 - 12, y0 + 12

  def to_json(self):
    d = {
      "x": int(self.x), "y": int(self.y),
      "type": self.item_type,
      "locked": bool(self.locked),
    }
    if self.layer is not None:
      d["layer"] = int(self.layer)
    return d

  def draw(self, screen, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, y1 = ed.to_screen(r, b)
    rect = pygame.Rect(int(min(x0, x1)), int(min(y0, y1)),
                       int(abs(x1 - x0)), int(abs(y1 - y0)))

    if self.item_type == "cube":
      pygame.draw.rect(screen, CUBE_FILL, rect)
      pygame.draw.rect(screen, CUBE_EDGE, rect, CUBE_EDGE_W)
    elif self.item_type == "soda":
      q = max(1, rect.h // 4)
      top = pygame.Rect(rect.x, rect.y, rect.w, q)
      mid = pygame.Rect(rect.x, rect.y + q, rect.w, rect.h - 2 * q)
      bot = pygame.Rect(rect.x, rect.y + q + (rect.h - 2 * q), rect.w, q)
      pygame.draw.rect(screen, SODA_BLUE, top)
      pygame.draw.rect(screen, SODA_WHITE, mid)
      pygame.draw.rect(screen, SODA_BLUE, bot)
      pygame.draw.rect(screen, (20, 20, 20), rect, 2)
    else:
      pygame.draw.rect(screen, (200, 180, 120), rect)
      pygame.draw.rect(screen, (80, 70, 50), rect, 2)

    if self.locked:
      screen.blit(make_stripe_surface(rect.w, rect.h), rect.topleft)


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
    surf = render_text(font, self.label, fg)
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
    surf = render_text(font, self.label, fg)
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
      surf = render_text(font, self.text, INPUT_TEXT)
    else:
      surf = render_text(font, self.placeholder, INPUT_PLACEHOLDER)
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


class ContextMenu:
  ITEM_H = 26
  HEADER_H = 24
  SEP_H = 8
  PAD_X = 12

  def __init__(self, screen_size, options, pos, on_select, title=None):
    # options: list of (label, value) tuples; None entries are separators
    self.options = list(options)
    self.on_select = on_select
    self.title = title
    self.font = pygame.font.SysFont(None, 22)
    self.font_small = pygame.font.SysFont(None, 18)

    max_w = 80
    for opt in self.options:
      if opt is None:
        continue
      label, _ = opt
      w = self.font.size(label)[0]
      if w > max_w:
        max_w = w
    if title:
      tw = self.font_small.size(title)[0]
      if tw + self.PAD_X * 2 > max_w:
        max_w = tw + self.PAD_X * 2
    self.width = max_w + self.PAD_X * 2
    self.header_h = self.HEADER_H if title else 0

    h = self.header_h
    for opt in self.options:
      h += self.SEP_H if opt is None else self.ITEM_H
    self.height = h

    sw, sh = screen_size
    x = max(0, min(pos[0], sw - self.width))
    y = max(0, min(pos[1], sh - self.height))
    self.rect = pygame.Rect(x, y, self.width, self.height)
    self.hover = -1

  def hover_index(self, pos):
    if not self.rect.collidepoint(pos):
      self.hover = -1
      return -1
    if pos[1] < self.rect.y + self.header_h:
      self.hover = -1
      return -1
    y = self.rect.y + self.header_h
    for i, opt in enumerate(self.options):
      h = self.SEP_H if opt is None else self.ITEM_H
      r = pygame.Rect(self.rect.x, y, self.rect.width, h)
      if r.collidepoint(pos):
        if opt is None:
          self.hover = -1
          return -1
        self.hover = i
        return i
      y += h
    self.hover = -1
    return -1

  def draw(self, screen):
    pygame.draw.rect(screen, MENU_BG, self.rect)
    pygame.draw.rect(screen, MENU_BORDER, self.rect, 1)
    if self.title:
      surf = render_text(self.font_small, self.title, MENU_TITLE_FG)
      screen.blit(surf, (self.rect.x + self.PAD_X,
                         self.rect.y + (self.header_h - surf.get_height()) // 2))
      sep_y = self.rect.y + self.header_h - 1
      pygame.draw.line(screen, MENU_SEP,
                       (self.rect.x + 4, sep_y),
                       (self.rect.right - 4, sep_y), 1)

    y = self.rect.y + self.header_h
    for i, opt in enumerate(self.options):
      if opt is None:
        my = y + self.SEP_H // 2
        pygame.draw.line(screen, MENU_SEP,
                         (self.rect.x + 6, my),
                         (self.rect.right - 6, my), 1)
        y += self.SEP_H
        continue
      label, _ = opt
      r = pygame.Rect(self.rect.x, y, self.rect.width, self.ITEM_H)
      if i == self.hover:
        pygame.draw.rect(screen, MENU_HOVER, r)
      color = GOLD if i == self.hover else BTN_TEXT
      surf = render_text(self.font, label, color)
      screen.blit(surf, (r.x + self.PAD_X,
                         r.y + (r.height - surf.get_height()) // 2))
      y += self.ITEM_H


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
    self.snap_btn = UIToggleButton(0, 0, 80, PANEL_WIDGET_H,
                                   "Snap", self._on_snap_toggle)
    self.snap_btn.active = editor.snap_enabled
    self.undo_btn = UIButton(0, 0, 80, PANEL_WIDGET_H, "Undo", editor.undo)
    self.redo_btn = UIButton(0, 0, 80, PANEL_WIDGET_H, "Redo", editor.redo)
    self.save_btn = UIButton(0, 0, 88, PANEL_WIDGET_H, "Save", editor.save)
    self.load_btn = UIButton(0, 0, 88, PANEL_WIDGET_H, "Load", editor.load)
    self.body_widgets.extend([self.lock_btn, self.zone_unlock_btn,
                              self.snap_btn, self.undo_btn, self.redo_btn,
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
        self.editor.set_tool("peg")

  def _on_zone_toggle(self, active):
    if active:
      self.editor.set_tool("unlock_zone")
    else:
      if self.editor.tool == "unlock_zone":
        self.editor.set_tool("peg")

  def _on_snap_toggle(self, active):
    self.editor.snap_enabled = active

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
    title = render_text(self.font_small, "Level editor", PANEL_TITLE)
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
    refs = []
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

    # Context menu is modal
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
        # reset zoom
        self.zoom = 1.0
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
    options.append(None)  # separator
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

    # ---- Shift: selection mode ----
    if shift:
      # allow resize on selected edges
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

    # ---- normal tools ----
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

    # jump line
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

    # zoom indicator
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
    iw, ih = 60, 32
    ir = pygame.Rect(0, 0, iw, ih)
    ir.center = r.center
    if item_type == "cube":
      pygame.draw.rect(screen, CUBE_FILL, ir)
      pygame.draw.rect(screen, CUBE_EDGE, ir, CUBE_EDGE_W)
    elif item_type == "soda":
      q = ir.h // 4
      pygame.draw.rect(screen, SODA_BLUE,
                       pygame.Rect(ir.x, ir.y, ir.w, q))
      pygame.draw.rect(screen, SODA_WHITE,
                       pygame.Rect(ir.x, ir.y + q, ir.w, ir.h - 2 * q))
      pygame.draw.rect(screen, SODA_BLUE,
                       pygame.Rect(ir.x, ir.y + q + (ir.h - 2 * q), ir.w, q))
      pygame.draw.rect(screen, (20, 20, 20), ir, 2)
    else:
      pygame.draw.rect(screen, (200, 180, 120), ir)
      pygame.draw.rect(screen, (80, 70, 50), ir, 2)

  # =========================================================
  # Bottom tabs (ghost, eraser, peg, platform, background, item)
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