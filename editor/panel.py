"""Верхняя панель с кнопками."""
import pygame
from .const import (
  PANEL_HEADER_H, PANEL_BODY_H, PANEL_WIDGET_H,
  PANEL_BG, PANEL_BORDER, PANEL_TITLE,
)
from .helpers import render_text
from .widgets import UIButton, UIToggleButton


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