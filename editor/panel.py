"""Р’РµСЂС…РЅСЏСЏ РїР°РЅРµР»СЊ СЂРµРґР°РєС‚РѕСЂР° РЅР° raylib."""
from raylib import DrawRectangle, DrawLine

from .const import (
  PANEL_HEADER_H, PANEL_BODY_H, PANEL_WIDGET_H,
  PANEL_BG, PANEL_BORDER, PANEL_TITLE,
)
from .helpers import C, draw_text
from .widgets import UIButton, UIToggleButton


class TopPanel:
  def __init__(self, editor):
    self.editor = editor
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

    sw, _ = editor.screen_size
    self.layout(sw)

  def height(self):
    return PANEL_HEADER_H + (PANEL_BODY_H if self.expanded else 0)

  def layout(self, screen_w):
    pad = 10
    tw, th = self.toggle_btn.rect[2], self.toggle_btn.rect[3]
    self.toggle_btn.rect = (screen_w - pad - tw,
                            (PANEL_HEADER_H - th) // 2, tw, th)
    x = pad
    y = PANEL_HEADER_H + (PANEL_BODY_H - PANEL_WIDGET_H) // 2
    for w in self.body_widgets:
      rw, rh = w.rect[2], w.rect[3]
      w.rect = (x, y, rw, rh)
      x += rw + pad

  def _toggle(self):
    self.expanded = not self.expanded
    self.toggle_btn.label = "Hide" if self.expanded else "Show"
    sw, _ = self.editor.screen_size
    self.layout(sw)

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
    return list(self.header_widgets) + (
      list(self.body_widgets) if self.expanded else [])

  def on_event(self, e_type, pos, button):
    consumed = False
    for w in self._active_widgets():
      if w.on_event(e_type, pos, button):
        consumed = True
    if e_type == "down" and pos[1] < self.height():
      return True
    return consumed

  def update(self, dt):
    for w in self._active_widgets():
      w.update(dt)

  def draw(self):
    sw, _ = self.editor.screen_size
    h = self.height()
    DrawRectangle(0, 0, sw, h, C(PANEL_BG))
    DrawLine(0, h - 1, sw, h - 1, C(PANEL_BORDER))
    draw_text("Level editor", 10, (PANEL_HEADER_H - 20) // 2, 20, C(PANEL_TITLE))
    for w in self.header_widgets:
      w.draw(20)
    if self.expanded:
      for w in self.body_widgets:
        w.draw(20)