"""Р’РёРґР¶РµС‚С‹ РІРµСЂС…РЅРµР№ РїР°РЅРµР»Рё Рё РєРѕРЅС‚РµРєСЃС‚РЅРѕРµ РјРµРЅСЋ РЅР° raylib."""
from raylib import (
  DrawRectangle, DrawRectangleLines, DrawLine,
)

from .const import (
  BTN_BG, BTN_BG_HOVER, BTN_BG_PRESS, BTN_BG_ACTIVE, BTN_BORDER,
  BTN_TEXT, BTN_TEXT_DIM, GOLD,
  INPUT_BG, INPUT_BORDER, INPUT_BORDER_FOCUS, INPUT_TEXT, INPUT_PLACEHOLDER,
  MENU_BG, MENU_BORDER, MENU_HOVER, MENU_TITLE_FG, MENU_SEP,
)
from .helpers import C, draw_text, text_width


def _hit(r, p):
  return r[0] <= p[0] < r[0] + r[2] and r[1] <= p[1] < r[1] + r[3]


class Widget:
  def __init__(self, x, y, w, h):
    self.rect = (int(x), int(y), int(w), int(h))
    self.visible = True
    self.enabled = True

  def draw(self, size=20):
    pass

  def on_event(self, e_type, pos, button):
    return False

  def update(self, dt):
    pass


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

  def draw(self, size=20):
    if not self.visible:
      return
    bg, fg, border = self._colors()
    x, y, w, h = self.rect
    DrawRectangle(x, y, w, h, C(bg))
    DrawRectangleLines(x, y, w, h, C(border))
    tw = text_width(self.label, size)
    draw_text(self.label, x + (w - tw) // 2, y + (h - size) // 2, size, C(fg))

  def on_event(self, e_type, pos, button):
    if not (self.visible and self.enabled):
      return False
    h = _hit(self.rect, pos)
    if e_type == "move":
      self.hover = h
    elif e_type == "down" and button == 0:
      if h:
        self.pressed = True
        return True
    elif e_type == "up" and button == 0:
      was = self.pressed
      self.pressed = False
      if was and h and self.on_click:
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

  def draw(self, size=20):
    if not self.visible:
      return
    bg, fg, border = self._colors()
    x, y, w, h = self.rect
    DrawRectangle(x, y, w, h, C(bg))
    DrawRectangleLines(x, y, w, h, C(border))
    tw = text_width(self.label, size)
    draw_text(self.label, x + (w - tw) // 2, y + (h - size) // 2, size, C(fg))

  def on_event(self, e_type, pos, button):
    if not (self.visible and self.enabled):
      return False
    h = _hit(self.rect, pos)
    if e_type == "move":
      self.hover = h
    elif e_type == "down" and button == 0:
      if h:
        self.pressed = True
        return True
    elif e_type == "up" and button == 0:
      was = self.pressed
      self.pressed = False
      if was and h:
        self.active = not self.active
        if self.on_toggle:
          self.on_toggle(self.active)
        return True
    return False


class ContextMenu:
  ITEM_H = 26
  HEADER_H = 24
  SEP_H = 8
  PAD_X = 12

  def __init__(self, screen_size, options, pos, on_select, title=None):
    self.options = list(options)
    self.on_select = on_select
    self.title = title

    max_w = 80
    for opt in self.options:
      if opt is None:
        continue
      w = text_width(opt[0], 22)
      if w > max_w:
        max_w = w
    if title:
      tw = text_width(title, 18)
      if tw + self.PAD_X * 2 > max_w:
        max_w = tw + self.PAD_X * 2
    self.width = max_w + self.PAD_X * 2
    self.header_h = self.HEADER_H if title else 0

    h = self.header_h
    for opt in self.options:
      h += self.SEP_H if opt is None else self.ITEM_H
    self.height = h

    sw, sh = screen_size
    x = max(0, min(int(pos[0]), sw - self.width))
    y = max(0, min(int(pos[1]), sh - self.height))
    self.rect = (x, y, self.width, self.height)
    self.hover = -1

  def hover_index(self, pos):
    x, y, w, h = self.rect
    if not (x <= pos[0] < x + w and y <= pos[1] < y + h):
      self.hover = -1
      return -1
    if pos[1] < y + self.header_h:
      self.hover = -1
      return -1
    yy = y + self.header_h
    for i, opt in enumerate(self.options):
      hh = self.SEP_H if opt is None else self.ITEM_H
      if yy <= pos[1] < yy + hh:
        if opt is None:
          self.hover = -1
          return -1
        self.hover = i
        return i
      yy += hh
    self.hover = -1
    return -1

  def draw(self):
    x, y, w, h = self.rect
    DrawRectangle(x, y, w, h, C(MENU_BG))
    DrawRectangleLines(x, y, w, h, C(MENU_BORDER))
    if self.title:
      draw_text(self.title, x + self.PAD_X, y + 4, 18, C(MENU_TITLE_FG))
      sep_y = y + self.header_h - 1
      DrawLine(x + 4, sep_y, x + w - 4, sep_y, C(MENU_SEP))

    yy = y + self.header_h
    for i, opt in enumerate(self.options):
      if opt is None:
        my = yy + self.SEP_H // 2
        DrawLine(x + 6, my, x + w - 6, my, C(MENU_SEP))
        yy += self.SEP_H
        continue
      label, _ = opt
      if i == self.hover:
        DrawRectangle(x, yy, w, self.ITEM_H, C(MENU_HOVER))
      fg = GOLD if i == self.hover else BTN_TEXT
      draw_text(label, x + self.PAD_X, yy + (self.ITEM_H - 20) // 2, 20, C(fg))
      yy += self.ITEM_H