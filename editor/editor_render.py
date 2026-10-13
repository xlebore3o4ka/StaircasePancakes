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
  BAG_FILL, BAG_EDGE, BAG_EDGE_W, BAG_STRAP,
  ARTIFACT_FILL,
  ARTIFACT_EDGE,
  ARTIFACT_EDGE_W,
  TRIGGER_FILL, TRIGGER_EDGE, TRIGGER_EDGE_W,
  BUTTON_R, BUTTON_FILL, BUTTON_EDGE,
  ARTIFACT_LETTER_FG,
)
from .const import (
  SMART_CENTER_COLOR, SMART_CORNER_COLOR, SMART_TOUCH_COLOR,
)
from .helpers import render_text, draw_lock_badge
from .objects import make_fake_item


def _clip_line(p1, p2, clip_rect):
  # Liang-Barsky segment clipping.
  x1, y1 = p1
  x2, y2 = p2
  dx = x2 - x1
  dy = y2 - y1
  t0, t1 = 0.0, 1.0
  for p, q in ((-dx, x1 - clip_rect.x),
               (dx, clip_rect.right - x1),
               (-dy, y1 - clip_rect.y),
               (dy, clip_rect.bottom - y1)):
    if p == 0:
      if q < 0:
        return
    else:
      r = q / p
      if p < 0:
        if r > t1: return
        if r > t0: t0 = r
      else:
        if r < t0: return
        if r < t1: t1 = r
  if t0 > t1:
    return
  ax = x1 + t0 * dx
  ay = y1 + t0 * dy
  bx = x1 + t1 * dx
  by = y1 + t1 * dy
  painter = getattr(_clip_line, "PAINTER", None)
  if painter is not None:
    painter((int(ax), int(ay)), (int(bx), int(by)))

def _make_painter(screen):
  def paint(p1, p2):
    pygame.draw.line(screen, (255, 60, 60), p1, p2, 2)
  return paint

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

      self._draw_id_labels()
      self._draw_problem_stripes()
      self._draw_world_markers()

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
    self._draw_messages()

  def _draw_ghosted(self, obj):
    # <STRANGE>#526: ???????????????????????????? ???????????? ?????? ???????????????? ?????? ???????????? ????????????
    from .objects import (
      EditorPeg, EditorPlatform, EditorBackground, EditorItem, EditorSpawner,
      EditorButton,
    )
    col = (255, 255, 255, 70)
    if isinstance(obj, (EditorPeg, EditorSpawner, EditorButton)):
      sx, sy = self.to_screen(obj.x, obj.y)
      r = max(1, int(obj.r * self.zoom))
      pygame.draw.circle(self.screen, col, (int(sx), int(sy)), r, 1)
      return
    if isinstance(obj, (EditorBackground, EditorPlatform)) \
       and getattr(obj, "polygon", False) and len(obj.points) >= 3:
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
    from .objects import EditorBackground, EditorPlatform
    import math as _m
    bg = self.selected
    if not isinstance(bg, (EditorBackground, EditorPlatform)):
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


  def _blit_id_label(self, surf, x, y):
    bg = pygame.Surface((surf.get_width() + 6, surf.get_height() + 2),
                        pygame.SRCALPHA)
    bg.fill((0, 0, 0, 160))
    self.screen.blit(bg, (int(x), int(y)))
    self.screen.blit(surf, (int(x) + 3, int(y) + 1))

  def _draw_world_markers(self):
    # <STRANGE>#1033: transient markers (info dots) in world space.
    for m in self.world_markers:
      try:
        sx, sy = self.to_screen(m["x"], m["y"])
      except Exception:
        continue
      kind = m.get("kind", "info_artifact")
      if kind == "info_artifact":
        col = (80, 160, 255)
        pygame.draw.circle(self.screen, (24, 26, 32), (int(sx), int(sy)), 12)
        pygame.draw.circle(self.screen, col, (int(sx), int(sy)), 10, 2)
        f = pygame.font.SysFont(None, 18, bold=True)
        t = f.render("i", True, col)
        self.screen.blit(t, t.get_rect(center=(int(sx), int(sy) + 1)))

  def _draw_id_labels(self):
    # <STRANGE>#1012: zoom-scaled font; peg id centered on the body.
    from .objects import EditorPeg, EditorSpawner, EditorArtifact, EditorButton
    fs = max(9, int(16 * self.zoom))
    font = pygame.font.SysFont(None, fs, bold=True)
    sw, sh = self.screen.get_size()
    for obj in self.objects:
      oid = getattr(obj, "id", "")
      if not oid:
        continue
      if not self._visible(obj, sw, sh):
        continue
      surf = font.render(str(oid), True, (240, 240, 240))
      if isinstance(obj, (EditorPeg, EditorButton)):
        sx, sy = self.to_screen(obj.x, obj.y)
        px = sx - surf.get_width() / 2
        py = sy - surf.get_height() / 2
        self._blit_id_label(surf, px, py)
      elif isinstance(obj, (EditorSpawner, EditorArtifact)):
        sx, sy = self.to_screen(obj.x, obj.y)
        px = sx - surf.get_width() / 2
        py = sy - surf.get_height() / 2
        self._blit_id_label(surf, px, py)
      else:
        try:
          l, r2, b, t = obj.world_rect()
        except Exception:
          continue
        x0, y0 = self.to_screen(l, t)
        self._blit_id_label(surf, x0 + 3, y0 + 3)

  def _draw_problem_stripes(self):
    # <STRANGE>#1013: animated diagonal ticks around objects with issues.
    store = getattr(self, "messages", None)
    if store is None:
      return
    from .messages import WARN, ERROR
    targets = set()
    for m in store.active.values():
      if m.kind in (WARN, ERROR):
        for t in m.targets:
          targets.add(id(t))
    if not targets:
      return
    phase = pygame.time.get_ticks() / 1000.0
    _clip_line.PAINTER = _make_painter(self.screen)
    from .objects import EditorPeg, EditorSpawner, EditorArtifact, EditorButton
    sw, sh = self.screen.get_size()
    for obj in self.objects:
      if id(obj) not in targets:
        continue
      if not self._visible(obj, sw, sh):
        continue
      if isinstance(obj, (EditorPeg, EditorSpawner, EditorArtifact, EditorButton)):
        sx, sy = self.to_screen(obj.x, obj.y)
        r = max(2, int(obj.r * self.zoom))
        rect = pygame.Rect(int(sx - r), int(sy - r), r * 2, r * 2)
      else:
        try:
          l, r2, b, t = obj.world_rect()
        except Exception:
          continue
        x0, y0 = self.to_screen(l, t)
        x1, y1 = self.to_screen(r2, b)
        rect = pygame.Rect(int(min(x0, x1)), int(min(y0, y1)),
                           int(abs(x1 - x0)), int(abs(y1 - y0)))
      self._draw_stripes_around(rect, phase)

  def _draw_stripes_around(self, rect, phase):
    # <STRANGE>#1015: diagonal ticks clipped to the rect border.
    if rect.w < 6 or rect.h < 6:
      return
    COLOR = (255, 60, 60)
    THICK = 5
    STEP = 9
    shift = int((phase * 40.0) % STEP)
    # we clip to the boundary band (THICK px thick)
    band_top = pygame.Rect(rect.x, rect.y, rect.w, THICK)
    band_bot = pygame.Rect(rect.x, rect.bottom - THICK, rect.w, THICK)
    band_lft = pygame.Rect(rect.x, rect.y, THICK, rect.h)
    band_rgt = pygame.Rect(rect.right - THICK, rect.y, THICK, rect.h)
    # top strip
    x = -STEP + shift
    while x < rect.w + STEP:
      p1 = (rect.x + x, rect.y + THICK)
      p2 = (rect.x + x + THICK, rect.y)
      _clip_line(p1, p2, band_top)
      x += STEP
    # bottom strip
    x = -STEP + shift
    while x < rect.w + STEP:
      p1 = (rect.x + x, rect.bottom)
      p2 = (rect.x + x + THICK, rect.bottom - THICK)
      _clip_line(p1, p2, band_bot)
      x += STEP
    # left strip
    y = -STEP + shift
    while y < rect.h + STEP:
      p1 = (rect.x, rect.y + y + THICK)
      p2 = (rect.x + THICK, rect.y + y)
      _clip_line(p1, p2, band_lft)
      y += STEP
    # right strip
    y = -STEP + shift
    while y < rect.h + STEP:
      p1 = (rect.right - THICK, rect.y + y)
      p2 = (rect.right, rect.y + y + THICK)
      _clip_line(p1, p2, band_rgt)
      y += STEP

  def _draw_messages(self):
    # <STRANGE>#1005: toasts on the right + corner widget with dropdown
    from .messages import draw_icon, level_color
    store = getattr(self, "messages", None)
    if store is None:
      return
    sw, sh = self.screen.get_size()
    font = getattr(self, "font", None)
    if font is None:
      return
    y = self.panel.height() + 56
    for t in store.toasts:
      tt = t["t"]
      total = t["max"]
      SLIDE = 0.30
      elapsed = total - tt
      if elapsed < SLIDE: p = elapsed / SLIDE
      elif tt < SLIDE: p = tt / SLIDE
      else: p = 1.0
      p = max(0.0, min(1.0, p))
      ease = 1.0 - (1.0 - p) ** 3
      text = t["text"]
      kind = t["kind"]
      col = level_color(kind)
      pad_x, pad_y, icon = 16, 12, 22
      label = font.render(text, True, col)
      pw = pad_x * 2 + icon + 10 + label.get_width()
      ph = max(pad_y * 2 + icon, pad_y * 2 + label.get_height())
      x_vis = 16
      x_hid = -pw - 4
      x = int(x_hid + (x_vis - x_hid) * ease)
      panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
      pygame.draw.rect(panel, (24, 26, 32, 210), panel.get_rect(), border_radius=8)
      pygame.draw.rect(panel, (90, 96, 110, 230), panel.get_rect(), 1, border_radius=8)
      icx = pad_x + icon // 2
      icy = ph // 2
      icon_layer = pygame.Surface((icon + 4, icon + 4), pygame.SRCALPHA)
      draw_icon(icon_layer, (icon + 4)//2, (icon + 4)//2, kind, r=9)
      panel.blit(icon_layer, (icx - (icon + 4)//2, icy - (icon + 4)//2))
      panel.blit(label, (pad_x + icon + 10, (ph - label.get_height()) // 2))
      self.screen.blit(panel, (x, y))
      y += ph + 6
    # corner widget
    top = store.top_level()
    if top is None and not store.open:
      return
    cw, ch = 40, 40
    cx = 14
    cy = self.panel.height() + 8
    widget = pygame.Surface((cw, ch), pygame.SRCALPHA)
    pygame.draw.rect(widget, (24, 26, 32, 220), widget.get_rect(), border_radius=8)
    pygame.draw.rect(widget, (90, 96, 110, 230), widget.get_rect(), 1, border_radius=8)
    if top is not None:
      draw_icon(widget, cw // 2, ch // 2, top.kind, r=10)
    n = store.count()
    if n > 1:
      f = pygame.font.SysFont(None, 16, bold=True)
      badge = f.render(str(n), True, (255, 255, 255))
      br = pygame.Rect(cw - 16, 0, 16, 14)
      pygame.draw.rect(widget, (60, 66, 78), br, border_radius=3)
      widget.blit(badge, badge.get_rect(center=br.center))
    self.screen.blit(widget, (cx, cy))
    if store.open and store.active:
      items = list(store.active.values())
      row_h = 24
      dh = len(items) * row_h + 8
      dy = cy + ch + 4
      dw = 260
      dx = 14
      drop = pygame.Surface((dw, dh), pygame.SRCALPHA)
      pygame.draw.rect(drop, (18, 20, 26, 240), drop.get_rect(), border_radius=6)
      pygame.draw.rect(drop, (90, 96, 110, 230), drop.get_rect(), 1, border_radius=6)
      mx, my = pygame.mouse.get_pos()
      hover_i = -1
      for i, m in enumerate(items):
        ry = 4 + i * row_h
        rr = pygame.Rect(4, ry, dw - 8, row_h)
        if pygame.Rect(dx, dy, dw, dh).collidepoint((mx, my)):
          local = (mx - dx, my - dy)
          if rr.collidepoint(local):
            hover_i = i
        if i == hover_i:
          pygame.draw.rect(drop, (56, 62, 74), rr, border_radius=3)
        draw_icon(drop, 4 + 12, ry + row_h // 2, m.kind, r=7)
        col = level_color(m.kind)
        ts = font.render(m.text[:36], True, col)
        drop.blit(ts, (4 + 26, ry + (row_h - ts.get_height()) // 2))
      self.screen.blit(drop, (dx, dy))
      self._msg_dropdown_rect = pygame.Rect(dx, dy, dw, dh)
    else:
      self._msg_dropdown_rect = None
    self._msg_widget_rect = pygame.Rect(cx, cy, cw, ch)

  def _handle_message_click(self, pos):
    # <STRANGE>#1006: widget click toggles dropdown; dropdown click jumps to target
    store = getattr(self, "messages", None)
    if store is None:
      return False
    wr = getattr(self, "_msg_widget_rect", None)
    if wr is not None and wr.collidepoint(pos):
      store.open = not store.open
      return True
    dr = getattr(self, "_msg_dropdown_rect", None)
    if dr is not None and dr.collidepoint(pos):
      items = list(store.active.values())
      row_h = 24
      i = (pos[1] - dr.y - 4) // row_h
      if 0 <= i < len(items):
        m = items[i]
        if m.targets:
          t = m.targets[m.target_idx % len(m.targets)]
          m.target_idx = (m.target_idx + 1) % len(m.targets)
          try:
            self.cam_x = t.x
            self.cam_y = t.y
          except Exception:
            pass
      return True
    return False

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
    self.draw_tab(self.tab_artifact_rect(), "artifact", self.tool == "artifact")
    self.draw_tab(self.tab_trigger_rect(), "trigger", self.tool == "trigger")
    self.draw_tab(self.tab_button_rect(), "button", self.tool == "button")

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
    elif name == "button":
      pygame.draw.circle(self.screen, BUTTON_FILL, (cx, cy), BUTTON_R + 3)
      pygame.draw.circle(self.screen, BUTTON_EDGE, (cx, cy), BUTTON_R + 3, 2)
    elif name == "trigger":
      rr = pygame.Rect(0, 0, 72, 44)
      rr.center = r.center
      ov = pygame.Surface(rr.size, pygame.SRCALPHA)
      ov.fill((80, 160, 255, 70))
      self.screen.blit(ov, rr.topleft)
      pygame.draw.rect(self.screen, (80, 160, 255), rr, 2)
    elif name == "artifact":
      # <STRANGE>#742: draw current artifact type; fallback to generic square
      cur = getattr(self, "current_artifact_type", "bag")
      game = make_fake_item(cur)
      if game is not None:
        self._draw_item_icon(self.screen, r, cur)
      else:
        # fallback: red square like BagItem, or generic letter circle
        box = pygame.Rect(0, 0, 30, 30)
        box.center = r.center
        if cur == "bag":
          pygame.draw.rect(self.screen, (200, 40, 40), box)
          pygame.draw.rect(self.screen, (255, 255, 255), box, 2)
        else:
          pygame.draw.circle(self.screen, ARTIFACT_FILL, box.center, 14)
          pygame.draw.circle(self.screen, ARTIFACT_EDGE, box.center, 14, 2)
          f = pygame.font.SysFont(None, 18, bold=True)
          letter = cur[:1].upper() if cur else "?"
          ts = f.render(letter, True, ARTIFACT_LETTER_FG)
          self.screen.blit(ts, ts.get_rect(center=box.center))
    elif name == "bag":
      rr = pygame.Rect(0, 0, 24, 24)
      rr.center = r.center
      pygame.draw.circle(self.screen, BAG_FILL, rr.center, 12)
      pygame.draw.circle(self.screen, BAG_EDGE, rr.center, 12, 2)
      pygame.draw.circle(self.screen, BAG_STRAP, rr.center, 4)
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
    return pygame.Rect(10, h - BOT_H + 6, 110, BOT_H - 12)

  def tab_eraser_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(130, h - BOT_H + 6, 110, BOT_H - 12)

  def tab_peg_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(250, h - BOT_H + 6, 110, BOT_H - 12)

  def tab_plat_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(370, h - BOT_H + 6, 110, BOT_H - 12)

  def tab_bg_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(490, h - BOT_H + 6, 110, BOT_H - 12)

  def tab_item_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(610, h - BOT_H + 6, 110, BOT_H - 12)

  def tab_spawner_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(730, h - BOT_H + 6, 110, BOT_H - 12)

  def tab_artifact_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(850, h - BOT_H + 6, 110, BOT_H - 12)

  def tab_trigger_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(970, h - BOT_H + 6, 110, BOT_H - 12)

  def tab_button_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(1090, h - BOT_H + 6, 110, BOT_H - 12)

 