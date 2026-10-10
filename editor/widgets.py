"""Виджеты верхней панели и всплывающее контекстное меню."""
import pygame
from .const import (
  BTN_BG, BTN_BG_HOVER, BTN_BG_PRESS, BTN_BG_ACTIVE, BTN_BORDER,
  BTN_TEXT, BTN_TEXT_DIM, GOLD,
  INPUT_BG, INPUT_BORDER, INPUT_BORDER_FOCUS, INPUT_TEXT, INPUT_PLACEHOLDER,
  MENU_BG, MENU_BORDER, MENU_HOVER, MENU_TITLE_FG, MENU_SEP,
)
from .helpers import render_text


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


class UILabel(Widget):
  """???????????? ??????????. ???? ?????????? ??????????????, ?????????? ???????????? ?????? ?????????????? ?????????? ?? ??????????."""
  def __init__(self, text, w, h):
    super().__init__(0, 0, w, h)
    self.text = text
    self.align = "right"

  def draw(self, screen, font, origin=(0, 0)):
    if not self.visible:
      return
    r = self.screen_rect(origin)
    surf = render_text(font, self.text, BTN_TEXT)
    if self.align == "right":
      x = r.right - surf.get_width()
    elif self.align == "center":
      x = r.centerx - surf.get_width() // 2
    else:
      x = r.x
    y = r.centery - surf.get_height() // 2
    screen.blit(surf, (x, y))

  def on_event(self, e, origin=(0, 0)):
    return False


class UITextInput(Widget):
  def __init__(self, x, y, w, h, placeholder="", text="", on_commit=None):
    super().__init__(x, y, w, h)
    self.text = text
    self.placeholder = placeholder
    self.focused = False
    self.cursor_blink = 0.0
    self.on_commit = on_commit
    self._last_committed = text

  def _commit(self):
    if self.on_commit and self.text != self._last_committed:
      self._last_committed = self.text
      self.on_commit(self.text)

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
        self._commit()
      return False
    if self.focused and e.type == pygame.KEYDOWN:
      if e.key == pygame.K_BACKSPACE:
        self.text = self.text[:-1]
        return True
      if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
        self.focused = False
        self._commit()
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