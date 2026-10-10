"""Отрисовка мира, нижней панели, инспекторов, зон и превью."""
import pygame

from .const import (
  SMART_CENTER_COLOR, SMART_CORNER_COLOR, SMART_TOUCH_COLOR,
  ROTATE_ARC_R, ROTATE_ARC_OFF, ROTATE_ARC_THICK,
  ROTATE_ARC_FILL, ROTATE_ARC_HOVER, ROTATE_ARC_SHADOW,

  BG, GOLD, GREEN, SEL_BLUE, SNAP_COLOR, SMART_MIRROR_COLOR, UI_BG, GREY,
  BOT_H, JUMP_H, JUMP_ALPHA,
  PEG_FILL, PEG_EDGE, PEG_R,
  PLAT_FILL, PLAT_EDGE, PLAT_EDGE_W,
  BG_DEFAULT_COLOR,
  ARM_R, PLAYER_R,
  POLY_VERTEX_R, POLY_VERTEX_FILL, POLY_VERTEX_EDGE,
  POLY_ACTIVE_FILL, POLY_EDGE_HINT,
)
from .const import (
  SMART_CENTER_COLOR, SMART_CORNER_COLOR, SMART_TOUCH_COLOR,
)
from .helpers import render_text, draw_lock_badge
from .objects import make_fake_item


class _IconCam:
  def __init__(self, center, scale):
    self._cx, self._cy = center
    self.scale = scale

  def to_screen(self, wx, wy):
    return (self._cx + wx * self.scale,
            self._cy - wy * self.scale)


class RenderMixin:
  def draw(self):
    if self._scene_dirty:
      self._rebuild_scene_lists()
    sw, sh = self.screen.get_size()

    self.screen.fill(BG)

    if self.polygon_edit is not None:
      # <STRANGE>#525: ghosted-?????????? ??? ?????? ??????????????, ?????????? ????????????????????????????, ????????????????
      for _layer, _order, kind, obj in self._render_order:
        if kind == "floor":
          self.draw_floor_line()
        elif kind == "ghost":
          continue
        else:
          if not self._visible(obj, sw, sh):
            continue
          if obj is self.polygon_edit:
            obj.draw(self.screen, self)
          else:
            self._draw_ghosted(obj)
    else:
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
      self._draw_rotate_arcs()

      for obj in self._locked_list:
        bx, by = obj.badge_screen_pos(self)
        draw_lock_badge(self.screen, bx, by)

    self.draw_bottom_bar()
    self.panel.draw(self.screen)

    for p in self.inspector_stack:
      p.draw(self.screen)

    if self.polygon_edit is not None:
      self.draw_select_rect_preview()
      self.draw_polygon_edit()

    if self.context_menu is not None:
      self.context_menu.draw(self.screen)

  def _draw_ghosted(self, obj):
    # <STRANGE>#526: ???????????????????????????? ???????????? ?????? ???????????????? ?????? ???????????? ????????????
    from .objects import (
      EditorPeg, EditorPlatform, EditorBackground, EditorItem, EditorSpawner,
    )
    col = (255, 255, 255, 70)
    if isinstance(obj, (EditorPeg, EditorSpawner)):
      sx, sy = self.to_screen(obj.x, obj.y)
      r = max(1, int(obj.r * self.zoom))
      pygame.draw.circle(self.screen, col, (int(sx), int(sy)), r, 1)
      return
    if isinstance(obj, EditorBackground) and obj.polygon and len(obj.points) >= 3:
      pts = [self.to_screen(*wp) for wp in obj.world_points()]
      ipts = [(int(x), int(y)) for x, y in pts]
      pygame.draw.polygon(self.screen, col, ipts, 1)
      return
    l, r, b, t = obj.world_rect()
    x0, y0 = self.to_screen(l, t)
    x1, y1 = self.to_screen(r, b)
    rr = pygame.Rect(int(min(x0, x1)), int(min(y0, y1)),
                     int(abs(x1 - x0)), int(abs(y1 - y0)))
    pygame.draw.rect(self.screen, col, rr, 1)

  def draw_polygon_edit(self):
    bg = self.polygon_edit
    if bg is None:
      return
    wpts = bg.world_points()
    n = len(wpts)
    for i in range(n):
      x0, y0 = self.to_screen(*wpts[i])
      x1, y1 = self.to_screen(*wpts[(i + 1) % n])
      pygame.draw.line(self.screen, POLY_EDGE_HINT,
                       (int(x0), int(y0)), (int(x1), int(y1)), 2)
    for i, (wx, wy) in enumerate(wpts):
      sx, sy = self.to_screen(wx, wy)
      col = POLY_ACTIVE_FILL if i in bg.active_points else POLY_VERTEX_FILL
      pygame.draw.circle(self.screen, col, (int(sx), int(sy)), POLY_VERTEX_R)
      pygame.draw.circle(self.screen, POLY_VERTEX_EDGE,
                         (int(sx), int(sy)), POLY_VERTEX_R, 2)

  def _draw_rotate_arcs(self):
    from .objects import EditorBackground
    import math as _m
    bg = self.selected
    if not isinstance(bg, EditorBackground):
      return
    if bg.locked or self.polygon_edit is not None:
      return
    c_tl, c_br, rr = self._rotate_arc_centers(bg)
    mx, my = pygame.mouse.get_pos()

    # <STRANGE>#610: ???????? ??? ?????????? ?????????? ?????????????? ?? ????????.
    # ???????????? ?????? ????????, ???????????? ???????? ???????? ?? ??????????????.
    for key, c in (("tl", c_tl), ("br", c_br)):
      hover = (mx - c[0]) ** 2 + (my - c[1]) ** 2 <= rr * rr
      col = ROTATE_ARC_HOVER if hover else ROTATE_ARC_FILL

      # ???????? ???? ???????????? ???????? ???? ???????? ??????????????
      ang_to_corner = _m.atan2(0 - c[1], 0 - c[0])
      # ?????????????? ???????????? ??????????????
      gap = _m.radians(80)
      # ???????? ???????????????? ?? ??????????????, ?????????????????????????????? ?????????????????????? ???? ????????
      a_start = ang_to_corner + gap / 2
      a_end = ang_to_corner + (2 * _m.pi - gap / 2)

      steps = 32
      pts = []
      for i in range(steps + 1):
        a = a_start + (a_end - a_start) * i / steps
        pts.append((c[0] + _m.cos(a) * rr, c[1] + _m.sin(a) * rr))

      if len(pts) >= 2:
        pygame.draw.lines(self.screen, col, False,
                          [(int(x), int(y)) for x, y in pts],
                          ROTATE_ARC_THICK)

      # ?????????????? ???? ?????????? ???????????? ???????? ??? ???????????????????? ?????????????????????? ????????????????
      for idx, other in ((0, 1), (-1, -2)):
        end = pts[idx]
        prev = pts[other]
        ang = _m.atan2(end[1] - prev[1], end[0] - prev[0])
        ah = 7
        for side in (-1, 1):
          ea = ang + side * _m.radians(150)
          ex = end[0] + _m.cos(ea) * ah
          ey = end[1] + _m.sin(ea) * ah
          pygame.draw.line(self.screen, col, (int(end[0]), int(end[1])),
                           (int(ex), int(ey)), ROTATE_ARC_THICK)


  def draw_snap_guides(self):
    sw, sh = self.screen.get_size()
    for gx in self.snap_guides_x:
      sx, _ = self.to_screen(gx, 0)
      pygame.draw.line(self.screen, SNAP_COLOR, (int(sx), 0), (int(sx), sh), 1)
    for gy in self.snap_guides_y:
      _, sy = self.to_screen(0, gy)
      pygame.draw.line(self.screen, SNAP_COLOR, (0, int(sy)), (sw, int(sy)), 1)
    # <STRANGE>#591: smart-?????????????????? ??? ?????????? ?????? ?? ???????????????? snap, ???? ???????????? ????????????
    for kind, wx, wy, text in self.smart_guides:
      sx, sy = self.to_screen(wx, wy)
      if kind.startswith("mirror"):
        col = SMART_MIRROR_COLOR
      elif kind.startswith("center"):
        col = SMART_CENTER_COLOR
      elif kind == "corner":
        col = SMART_CORNER_COLOR
      else:
        col = SMART_TOUCH_COLOR
      # ?????????? ?????????? ???????? ??????????
      if kind.endswith("_x"):
        pygame.draw.line(self.screen, col, (int(sx), 0), (int(sx), sh), 1)
      elif kind.endswith("_y"):
        pygame.draw.line(self.screen, col, (0, int(sy)), (sw, int(sy)), 1)
      # ???????????? ?? ??????????????
      pygame.draw.circle(self.screen, col, (int(sx), int(sy)), 5, 2)
      surf = render_text(self.font, text, col)
      self.screen.blit(surf, (int(sx) + 8,
                              int(sy) - surf.get_height() // 2))

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
    self.screen.blit(self._ghost_arm,
                     (int(sx - arm_dx) - aw // 2, int(sy) - ah // 2))
    self.screen.blit(self._ghost_arm,
                     (int(sx + arm_dx) - aw // 2, int(sy) - ah // 2))
    body_r = self._ghost_body_r
    self.screen.blit(self._ghost_body,
                     (int(sx) - body_r, int(sy) - body_r))

  def draw_bottom_bar(self):
    h = self.screen.get_height()
    pygame.draw.rect(self.screen, UI_BG,
                     (0, h - BOT_H, self.screen.get_width(), BOT_H))
    self.draw_tab(self.tab_ghost_rect(), "ghost", self.tool == "ghost")
    self.draw_tab(self.tab_eraser_rect(), "eraser", self.tool == "eraser")
    self.draw_tab(self.tab_peg_rect(), "peg", self.tool == "peg")
    self.draw_tab(self.tab_plat_rect(), "platform", self.tool == "platform")
    self.draw_tab(self.tab_bg_rect(), "background", self.tool == "background")
    self.draw_tab(self.tab_item_rect(), "item", self.tool == "item")
    self.draw_tab(self.tab_spawner_rect(), "spawner", self.tool == "spawner")

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
    elif name == "spawner":
      rr = pygame.Rect(0, 0, 26, 26)
      rr.center = r.center
      pygame.draw.circle(self.screen, (150, 80, 200), rr.center, 13)
      pygame.draw.circle(self.screen, (245, 245, 255), rr.center, 13, 2)
      f = pygame.font.SysFont(None, 20, bold=True)
      ts = f.render("S", True, (255, 255, 255))
      self.screen.blit(ts, ts.get_rect(center=rr.center))
    else:
      rr = pygame.Rect(0, 0, 100, 40)
      rr.center = r.center
      pygame.draw.rect(self.screen, PLAT_FILL, rr)
      pygame.draw.rect(self.screen, PLAT_EDGE, rr, PLAT_EDGE_W)

  def _draw_item_icon(self, screen, r, item_type):
    game = make_fake_item(item_type)
    if game is None:
      ir = pygame.Rect(0, 0, 60, 32)
      ir.center = r.center
      pygame.draw.rect(screen, (200, 180, 120), ir)
      pygame.draw.rect(screen, (80, 70, 50), ir, 2)
      return

    box_w, box_h = 60, 40
    sx = box_w / max(1, game.w)
    sy = box_h / max(1, game.h)
    scale = min(sx, sy)
    cam = _IconCam(r.center, scale)
    game.draw_at(screen, cam, (0, 0), 0.0, 255, 1.0)

  # ---------- tab rects ----------
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

  def tab_spawner_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(790, h - BOT_H + 6, 120, BOT_H - 12)