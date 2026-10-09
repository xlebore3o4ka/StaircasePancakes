"""РћС‚СЂРёСЃРѕРІРєР° РјРёСЂР°, РЅРёР¶РЅРµР№ РїР°РЅРµР»Рё, РёРЅСЃРїРµРєС‚РѕСЂРѕРІ, Р·РѕРЅ Рё РїСЂРµРІСЊСЋ."""
from raylib import (
  DrawRectangle, DrawRectangleLines, DrawCircle, DrawCircleLines,
  DrawLine,
)
from .const import (
  BG, GOLD, GREEN, SEL_BLUE, SNAP_COLOR, UI_BG, GREY,
  BOT_H, JUMP_H, JUMP_ALPHA,
  PEG_FILL, PEG_EDGE, PEG_R,
  PLAT_FILL, PLAT_EDGE, PLAT_EDGE_W,
  BG_DEFAULT_COLOR,
  ARM_R, PLAYER_R, GHOST_ALPHA, ARM_ALPHA,
  CUBE_FILL, CUBE_EDGE, CUBE_EDGE_W, SODA_BLUE, SODA_WHITE,
)
from .helpers import C, draw_text, text_width, draw_lock_badge
from .objects import EditorItem


class RenderMixin:
  def draw(self):
    if self._scene_dirty:
      self._rebuild_scene_lists()
    sw, sh = self.screen_size

    for _layer, _order, kind, obj in self._render_order:
      if kind == "floor":
        self.draw_floor_line()
      elif kind == "ghost":
        self.draw_ghost()
      else:
        if self._visible(obj, sw, sh):
          obj.draw(self)

    for obj in self.selection:
      sx, sy = self.to_screen(obj.x, obj.y)
      DrawCircle(int(sx), int(sy), 6, C(GREEN))

    self.draw_zone_preview()
    self.draw_select_rect_preview()
    self.draw_snap_guides()

    for obj in self._locked_list:
      bx, by = obj.badge_screen_pos(self)
      draw_lock_badge(int(bx), int(by))

    self.draw_bottom_bar()
    self.panel.draw()

    for p in self.inspector_stack:
      p.draw()

    if self.context_menu is not None:
      self.context_menu.draw()

  def draw_snap_guides(self):
    sw, sh = self.screen_size
    col = C(SNAP_COLOR)
    for gx in self.snap_guides_x:
      sx, _ = self.to_screen(gx, 0)
      DrawLine(int(sx), 0, int(sx), sh, col)
    for gy in self.snap_guides_y:
      _, sy = self.to_screen(0, gy)
      DrawLine(0, int(sy), sw, int(sy), col)

  def draw_zone_preview(self):
    rect = self._zone_rect()
    if rect is None: return
    l, r, b, t = rect
    x0, y0 = self.to_screen(l, t)
    x1, y1 = self.to_screen(r, b)
    rx, ry = int(min(x0, x1)), int(min(y0, y1))
    rw, rh = int(abs(x1 - x0)), int(abs(y1 - y0))
    if rw <= 0 or rh <= 0:
      DrawCircle(rx, ry, 3, C(GOLD)); return
    DrawRectangle(rx, ry, rw, rh, (255, 215, 0, 40))
    DrawRectangleLines(rx, ry, rw, rh, C(GOLD))

  def draw_select_rect_preview(self):
    rect = self._select_rect()
    if rect is None: return
    l, r, b, t = rect
    x0, y0 = self.to_screen(l, t)
    x1, y1 = self.to_screen(r, b)
    rx, ry = int(min(x0, x1)), int(min(y0, y1))
    rw, rh = int(abs(x1 - x0)), int(abs(y1 - y0))
    if rw <= 0 or rh <= 0: return
    DrawRectangle(rx, ry, rw, rh, (100, 200, 255, 50))
    DrawRectangleLines(rx, ry, rw, rh, C(SEL_BLUE))

  def draw_floor_line(self):
    _, y = self.to_screen(0, 0)
    sw, _ = self.screen_size
    DrawRectangle(0, int(y) - 1, sw, 2, (255, 255, 255, 90))

  def draw_ghost(self):
    gx, gy = self.ghost
    sx, sy = self.to_screen(gx, gy)

    _, ey = self.to_screen(gx, gy + JUMP_H)
    col = (255, 255, 255, JUMP_ALPHA)
    DrawLine(int(sx), int(ey), int(sx), int(sy), col)
    DrawLine(int(sx) - 5, int(ey), int(sx) + 5, int(ey), col)

    body_r = max(1, int(PLAYER_R * self.zoom))
    arm_r = max(1, int(ARM_R * self.zoom))
    arm_dx = self._ghost_arm_dx
    DrawCircle(int(sx - arm_dx), int(sy), arm_r, (255, 255, 255, ARM_ALPHA))
    DrawCircle(int(sx + arm_dx), int(sy), arm_r, (255, 255, 255, ARM_ALPHA))
    DrawCircle(int(sx), int(sy), body_r, (255, 255, 255, GHOST_ALPHA))

  def draw_bottom_bar(self):
    sw, sh = self.screen_size
    DrawRectangle(0, sh - BOT_H, sw, BOT_H, C(UI_BG))
    self.draw_tab(self.tab_ghost_rect(), "ghost", self.tool == "ghost")
    self.draw_tab(self.tab_eraser_rect(), "eraser", self.tool == "eraser")
    self.draw_tab(self.tab_peg_rect(), "peg", self.tool == "peg")
    self.draw_tab(self.tab_plat_rect(), "platform", self.tool == "platform")
    self.draw_tab(self.tab_bg_rect(), "background", self.tool == "background")
    self.draw_tab(self.tab_item_rect(), "item", self.tool == "item")
    self.draw_tab(self.tab_spawner_rect(), "spawner", self.tool == "spawner")

    z = f"{int(self.zoom * 100)}%"
    tw = text_width(z, 20)
    draw_text(z, sw - tw - 14, sh - BOT_H + (BOT_H - 20) // 2, 20, C(GOLD))

  def draw_tab(self, r, name, active):
    x, y, w, h = r
    DrawRectangle(x, y, w, h, (45, 50, 60, 255))
    col = GOLD if active else GREY
    DrawRectangleLines(x, y, w, h, C(col))
    cx, cy = x + w // 2, y + h // 2
    if name == "peg":
      DrawCircle(cx, cy, PEG_R, C(PEG_FILL))
      DrawCircleLines(cx, cy, PEG_R, C(PEG_EDGE))
      DrawCircleLines(cx, cy, PEG_R - 1, C(PEG_EDGE))
    elif name == "background":
      DrawRectangle(cx - 50, cy - 20, 100, 40, C(BG_DEFAULT_COLOR))
    elif name == "ghost":
      ar = max(4, ARM_R // 2); br = max(6, PLAYER_R // 2)
      DrawCircle(cx - br - ar - 1, cy, ar, (255, 255, 255, 255))
      DrawCircle(cx + br + ar + 1, cy, ar, (255, 255, 255, 255))
      DrawCircle(cx, cy, br, (255, 255, 255, 255))
    elif name == "eraser":
      DrawRectangle(cx - 42, cy - 16, 84, 32, (240, 150, 170, 255))
      DrawRectangle(cx - 42, cy - 4, 84, 8, (200, 90, 120, 255))
      DrawRectangleLines(cx - 42, cy - 16, 84, 32, (60, 60, 70, 255))
    elif name == "item":
      sz = EditorItem.SIZE_MAP.get(self.current_item_type, (30, 30))
      box = min(60 / max(1, sz[0]), 40 / max(1, sz[1]))
      iw = int(sz[0] * box); ih = int(sz[1] * box)
      ix = cx - iw // 2; iy = cy - ih // 2
      if self.current_item_type == "cube":
        DrawRectangle(ix, iy, iw, ih, C(CUBE_FILL))
        DrawRectangleLines(ix, iy, iw, ih, C(CUBE_EDGE))
      elif self.current_item_type == "soda":
        q = max(1, ih // 4)
        DrawRectangle(ix, iy, iw, q, C(SODA_BLUE))
        DrawRectangle(ix, iy + q, iw, ih - 2 * q, C(SODA_WHITE))
        DrawRectangle(ix, iy + q + (ih - 2 * q), iw, q, C(SODA_BLUE))
        DrawRectangleLines(ix, iy, iw, ih, (20, 20, 20, 255))
      else:
        DrawRectangle(ix, iy, iw, ih, (200, 180, 120, 255))
        DrawRectangleLines(ix, iy, iw, ih, (80, 70, 50, 255))
    elif name == "spawner":
      DrawCircle(cx, cy, 13, (150, 80, 200, 255))
      DrawCircleLines(cx, cy, 13, (245, 245, 255, 255))
      tw = text_width("S", 20)
      draw_text("S", cx - tw // 2, cy - 10, 20, (255, 255, 255, 255))
    else:
      DrawRectangle(cx - 50, cy - 20, 100, 40, C(PLAT_FILL))
      DrawRectangleLines(cx - 50, cy - 20, 100, 40, C(PLAT_EDGE))

  def tab_ghost_rect(self):
    _, sh = self.screen_size
    return (10, sh - BOT_H + 6, 120, BOT_H - 12)

  def tab_eraser_rect(self):
    _, sh = self.screen_size
    return (140, sh - BOT_H + 6, 120, BOT_H - 12)

  def tab_peg_rect(self):
    _, sh = self.screen_size
    return (270, sh - BOT_H + 6, 120, BOT_H - 12)

  def tab_plat_rect(self):
    _, sh = self.screen_size
    return (400, sh - BOT_H + 6, 120, BOT_H - 12)

  def tab_bg_rect(self):
    _, sh = self.screen_size
    return (530, sh - BOT_H + 6, 120, BOT_H - 12)

  def tab_item_rect(self):
    _, sh = self.screen_size
    return (660, sh - BOT_H + 6, 120, BOT_H - 12)

  def tab_spawner_rect(self):
    _, sh = self.screen_size
    return (790, sh - BOT_H + 6, 120, BOT_H - 12)