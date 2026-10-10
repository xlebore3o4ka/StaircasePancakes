"""Р’РµСЂС…РЅСЏСЏ РїР°РЅРµР»СЊ СЃ РІРєР»Р°РґРєР°РјРё."""
import pygame
from .const import (
  PANEL_HEADER_H, PANEL_BODY_H, PANEL_WIDGET_H,
  PANEL_BG, PANEL_BORDER, PANEL_TITLE,
  PANEL_TAB_H, PANEL_TAB_W, PANEL_TAB_BG, PANEL_TAB_ACTIVE_BG,
  PANEL_TAB_HOVER_BG, PANEL_TAB_BORDER, PANEL_TAB_TEXT,
  PANEL_TAB_ACTIVE_TEXT,
)
from .helpers import render_text
from .widgets import UIButton, UIToggleButton, UITextInput, UILabel


class TopPanel:
  TABS = ("Main", "Tools", "Grid")

  def __init__(self, editor):
    self.editor = editor
    self.font_small = pygame.font.SysFont(None, 20)
    self.font_body = pygame.font.SysFont(None, 22)
    self.expanded = True
    self.active_tab = 0

    self.toggle_btn = UIButton(0, 0, 84, PANEL_HEADER_H - 10,
                               "Hide", self._toggle)

    self.tab_widgets = []
    for i, name in enumerate(self.TABS):
      btn = UIButton(0, 0, PANEL_TAB_W, PANEL_TAB_H, name,
                     (lambda idx=i: (lambda: self._select_tab(idx)))())
      self.tab_widgets.append(btn)

    self.body_widgets = [[], [], []]

    # --- MAIN ---
    self.undo_btn = UIButton(0, 0, 76, PANEL_WIDGET_H, "Undo", editor.undo)
    self.redo_btn = UIButton(0, 0, 76, PANEL_WIDGET_H, "Redo", editor.redo)
    self.copy_btn = UIButton(0, 0, 72, PANEL_WIDGET_H, "Copy", editor.copy_selected)
    self.paste_btn = UIButton(0, 0, 72, PANEL_WIDGET_H, "Paste", editor.paste)
    self.dup_btn = UIButton(0, 0, 64, PANEL_WIDGET_H, "Dup", editor.duplicate_selected)
    self.all_btn = UIButton(0, 0, 64, PANEL_WIDGET_H, "All", editor._select_all)
    self.del_btn = UIButton(0, 0, 64, PANEL_WIDGET_H, "Del", editor.delete_selected)
    self.body_widgets[0].extend([self.undo_btn, self.redo_btn,
                                  self.copy_btn, self.paste_btn,
                                  self.dup_btn, self.all_btn, self.del_btn])

    # --- TOOLS ---
    self.lock_btn = UIToggleButton(0, 0, 110, PANEL_WIDGET_H,
                                   "Lock tool", self._on_lock_toggle)
    self.zone_unlock_btn = UIToggleButton(0, 0, 130, PANEL_WIDGET_H,
                                          "Zone unlock", self._on_zone_toggle)
    self.snap_btn = UIToggleButton(0, 0, 80, PANEL_WIDGET_H,
                                   "Snap", self._on_snap_toggle)
    self.snap_btn.active = editor.snap_enabled
    self.poly_btn = UIButton(0, 0, 72, PANEL_WIDGET_H, "Poly",
                             editor.toggle_polygon_edit)
    self.body_widgets[1].extend([self.lock_btn, self.zone_unlock_btn,
                                  self.snap_btn, self.poly_btn])

    # --- GRID ---
    self.grid_btn = UIToggleButton(0, 0, 80, PANEL_WIDGET_H,
                                   "Grid", self._on_grid_toggle)
    self.grid_btn.active = getattr(editor, "grid_enabled", False)
    # <STRANGE>#573: ?????????????? ?? ?????????? ??? ?????????? ??????????, ?????? ???????????????? ???????????? ??????????
    self.grid_xy_lbl = UILabel("XY:", 60, PANEL_WIDGET_H)
    self.grid_step_input = UITextInput(
      0, 0, 60, PANEL_WIDGET_H, placeholder="xy",
      text=str(getattr(editor, "grid_step", 10)),
      on_commit=self._on_grid_step)
    self.grid_deg_lbl = UILabel("DEG:", 60, PANEL_WIDGET_H)
    self.grid_angle_input = UITextInput(
      0, 0, 60, PANEL_WIDGET_H, placeholder="deg",
      text=str(getattr(editor, "grid_step_angle", 15)),
      on_commit=self._on_grid_angle)
    # <STRANGE>#574: Save/Load ??? ???????????????????? ???????????? ?????????? ?? ??????????????, ???? ?? ????????????????
    self.save_btn = UIButton(0, 0, 80, PANEL_HEADER_H - 10, "Save", editor.save)
    self.load_btn = UIButton(0, 0, 80, PANEL_HEADER_H - 10, "Load", editor.load)
    self.header_widgets = [self.toggle_btn, self.save_btn, self.load_btn]
    self.body_widgets[2].extend([self.grid_btn,
                                  self.grid_xy_lbl,
                                  self.grid_step_input,
                                  self.grid_deg_lbl,
                                  self.grid_angle_input])

    self.layout(editor.screen.get_width())

  def _select_tab(self, idx):
    self.active_tab = idx
    # <STRANGE>#570: ?????????????????????? layout ??? ?????????? ?? ?????????? ?????????????? ?????? ?????????????? ?? (0,0)
    sw, _ = self.editor.screen.get_size()
    self.layout(sw)

  def _on_grid_toggle(self, active):
    self.editor.grid_enabled = active

  def _on_grid_step(self, txt):
    try:
      v = int(txt)
      if v < 1:
        v = 1
    except Exception:
      v = 10
    self.editor.grid_step = v
    self.grid_step_input.text = str(v)
    self.grid_step_input._last_committed = str(v)

  def _on_grid_angle(self, txt):
    # <STRANGE>#572: ???????? ???????????????? ?? ????????????????, ???????????? 1..360
    try:
      v = int(txt)
      if v < 1:
        v = 1
      if v > 360:
        v = 360
    except Exception:
      v = 15
    self.editor.grid_step_angle = v
    self.grid_angle_input.text = str(v)
    self.grid_angle_input._last_committed = str(v)

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

  def height(self):
    return PANEL_HEADER_H + (PANEL_BODY_H if self.expanded else 0)

  def layout(self, screen_w):
    pad = 10
    # Hide ??? ????????????
    tw, th = self.toggle_btn.rect.size
    self.toggle_btn.rect.topleft = (screen_w - pad - tw,
                                    (PANEL_HEADER_H - th) // 2)
    # Save/Load ??? ?????????? ?????????? ???????????? "Level editor"
    cx = 130
    cy = (PANEL_HEADER_H - self.save_btn.rect.h) // 2
    self.save_btn.rect.topleft = (cx, cy)
    cx += self.save_btn.rect.w + 4
    self.load_btn.rect.topleft = (cx, cy)
    cx += self.load_btn.rect.w + 20
    # Tabs ??? ?????????? Save/Load
    tx = cx
    ty = (PANEL_HEADER_H - PANEL_TAB_H) // 2
    for btn in self.tab_widgets:
      btn.rect.topleft = (tx, ty)
      tx += PANEL_TAB_W + 4
    # body
    y = PANEL_HEADER_H + (PANEL_BODY_H - PANEL_WIDGET_H) // 2
    for tab_widgets in self.body_widgets:
      x = pad
      for w in tab_widgets:
        w.rect.x = x
        w.rect.y = y
        x += w.rect.width + pad

  def _toggle(self):
    self.expanded = not self.expanded
    self.toggle_btn.label = "Hide" if self.expanded else "Show"
    self.layout(self.editor.screen.get_width())

  def sync_tool(self, name):
    self.lock_btn.active = (name == "lock")
    self.zone_unlock_btn.active = (name == "unlock_zone")

  def _active_widgets(self):
    # <STRANGE>#575: header (Hide/Save/Load) ?????????????? ????????????
    active = list(self.header_widgets) + list(self.tab_widgets)
    if self.expanded:
      active += list(self.body_widgets[self.active_tab])
    return active

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
    for i, btn in enumerate(self.tab_widgets):
      r = btn.rect
      active = (i == self.active_tab)
      bg = PANEL_TAB_ACTIVE_BG if active else (
        PANEL_TAB_HOVER_BG if btn.hover else PANEL_TAB_BG)
      fg = PANEL_TAB_ACTIVE_TEXT if active else PANEL_TAB_TEXT
      pygame.draw.rect(screen, bg, r, border_radius=4)
      pygame.draw.rect(screen, PANEL_TAB_BORDER, r, 1, border_radius=4)
      surf = render_text(self.font_small, btn.label, fg)
      screen.blit(surf, surf.get_rect(center=r.center))
    # <STRANGE>#576: header-?????????????? (Hide/Save/Load)
    for w in self.header_widgets:
      w.draw(screen, self.font_small, (0, 0))
    if self.expanded:
      for w in self.body_widgets[self.active_tab]:
        w.draw(screen, self.font_body, (0, 0))