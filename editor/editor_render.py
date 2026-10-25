"""Отрисовка мира, нижней панели, инспекторов, зон и превью."""
import pygame
import math

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
  ANCHOR_SIZE, ANCHOR_ZONE_EDGE,
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
    # <STRANGE>#1530: split world/UI; lighting preview applies only to world
    use_lighting = bool(getattr(self, "light_preview", False)
                        and getattr(self, "lighting", None) is not None)
    if use_lighting:
      real_screen = self.screen
      scene = pygame.Surface(real_screen.get_size())
      self.screen = scene
      self._draw_world()
      self.screen = real_screen
      self._apply_light_preview(scene)
      real_screen.blit(scene, (0, 0))
      self._draw_ui()
    else:
      self._draw_world()
      self._draw_ui()

  def _draw_world(self):
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
      self._draw_anchor_zones()
      self._draw_plan_ghost()

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


  def _draw_ui(self):
    self.draw_bottom_bar()
    self.panel.draw(self.screen)

    for p in self.inspector_stack:
      p.draw(self.screen)
    self._draw_plan_panel()
    self._draw_markup_panel()
    self._draw_anchor_panel()

    if self.polygon_edit is not None:
      self.draw_select_rect_preview()
      self.draw_polygon_edit()

    if self.context_menu is not None:
      self.context_menu.draw(self.screen)
    self._draw_messages()
    self._draw_level_settings()
    self._draw_color_picker()
    self._draw_label_modal()

  def _collect_occluders(self):
    from .objects import EditorPlatform
    out = []
    for o in self.objects:
        if not isinstance(o, EditorPlatform):
            continue
        try:
            if getattr(o, "polygon", False):
                pts = o.world_points()
                if len(pts) < 3:
                    continue
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                l = min(p[0] for p in pts)
                r = max(p[0] for p in pts)
                b = min(p[1] for p in pts)
                t = max(p[1] for p in pts)
                edges = []
                for i in range(len(pts)):
                    a = pts[i]
                    bb = pts[(i + 1) % len(pts)]
                    edges.append((a, bb, (cx, cy)))
                out.append({"edges": edges, "bbox": (l, r, b, t)})
            else:
                l, r, b, t = o.world_rect()
                cx = (l + r) / 2
                cy = (b + t) / 2
                edges = [
                    ((l, b), (r, b), (cx, cy)),
                    ((r, b), (r, t), (cx, cy)),
                    ((r, t), (l, t), (cx, cy)),
                    ((l, t), (l, b), (cx, cy)),
                ]
                out.append({"edges": edges, "bbox": (l, r, b, t)})
        except Exception:
            continue
    return out

  def _apply_light_preview(self, scene):
    import math as _m
    from .objects import EditorLight
    sw, sh = scene.get_size()
    cfg = self.lighting or {}
    ambient = tuple(int(c) for c in cfg.get("ambient", [0, 0, 0])[:3])
    gain = float(cfg.get("gain", 1.0))
    LS = 2
    lsw = max(1, sw // LS)
    lsh = max(1, sh // LS)
    light = pygame.Surface((lsw, lsh))
    light.fill(ambient)
    occluders = self._collect_occluders()

    def w2l(wx, wy):
        sx, sy = self.to_screen(wx, wy)
        return sx / LS, sy / LS

    # sun: uniform tint + gradient shadows, then MAX
    if getattr(self, "sun_enabled", False):
        sc = tuple(self.sun_color)[:3]
        si = float(self.sun_intensity)
        tint = (min(255, int(sc[0] * si)),
                min(255, int(sc[1] * si)),
                min(255, int(sc[2] * si)))
        sun_layer = pygame.Surface((lsw, lsh))
        sun_layer.fill(tint)
        shadow_mask = pygame.Surface((lsw, lsh), pygame.SRCALPHA)
        dxw, dyw = self.sun_direction
        nd = _m.hypot(dxw, dyw) or 1.0
        ndx, ndy = dxw / nd, dyw / nd
        # direction = ?????? ???????????? (?? ????????). ???????? ???????????? ?? -direction (?? ????????).
        # screen shadow: (-ndx, +ndy)
        shs_x = -ndx
        shs_y = ndy
        zoom = self.zoom
        gl = float(getattr(self, "sun_gradient_length", 60.0)) * zoom / LS
        sl = float(getattr(self, "sun_shadow_length", 2000.0)) * zoom / LS
        N = 6
        gstep = gl / N if N > 0 else gl
        for oc in occluders:
            for a_w, b_w, centroid in oc["edges"]:
                ax_w, ay_w = a_w
                bx_w, by_w = b_w
                nx = by_w - ay_w
                ny = -(bx_w - ax_w)
                nc_dot = nx * (centroid[0] - ax_w) + ny * (centroid[1] - ay_w)
                dot = nx * ndx + ny * ndy
                if dot * nc_dot > 0:
                    continue
                a_lx, a_ly = w2l(ax_w, ay_w)
                b_lx, b_ly = w2l(bx_w, by_w)
                for i in range(N):
                    d0 = i * gstep
                    alpha = int(255 * (1.0 - i / max(1, N)))
                    if alpha <= 0:
                        continue
                    d1 = gl
                    p1 = (a_lx + shs_x * d0, a_ly + shs_y * d0)
                    p2 = (b_lx + shs_x * d0, b_ly + shs_y * d0)
                    p3 = (b_lx + shs_x * d1, b_ly + shs_y * d1)
                    p4 = (a_lx + shs_x * d1, a_ly + shs_y * d1)
                    pygame.draw.polygon(shadow_mask, (0, 0, 0, alpha),
                                        [p1, p2, p3, p4])
                d0 = gl
                d1 = sl
                p1 = (a_lx + shs_x * d0, a_ly + shs_y * d0)
                p2 = (b_lx + shs_x * d0, b_ly + shs_y * d0)
                p3 = (b_lx + shs_x * d1, b_ly + shs_y * d1)
                p4 = (a_lx + shs_x * d1, a_ly + shs_y * d1)
                pygame.draw.polygon(shadow_mask, (0, 0, 0, 255),
                                    [p1, p2, p3, p4])
        sun_layer.blit(shadow_mask, (0, 0))
        light.blit(sun_layer, (0, 0), special_flags=pygame.BLEND_RGB_MAX)

    # lamps / spots: MAX blend
    for o in self.objects:
        if not isinstance(o, EditorLight):
            continue
        if getattr(o, "kind", "") == "sun":
            continue
        contrib = self._light_contrib(o, occluders, lsw, lsh, LS)
        if contrib is not None:
            light.blit(contrib, (0, 0), special_flags=pygame.BLEND_RGB_MAX)

    bw = max(1, lsw // 2)
    bh = max(1, lsh // 2)
    tiny = pygame.transform.smoothscale(light, (bw, bh))
    light = pygame.transform.smoothscale(tiny, (lsw, lsh))
    big = pygame.transform.smoothscale(light, (sw, sh))
    scene.blit(big, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    if abs(gain - 1.0) > 1e-3:
        g = int(max(0, min(255, round(gain * 255))))
        scene.fill((g, g, g), special_flags=pygame.BLEND_RGB_MULT)

  def _light_contrib(self, o, occluders, lsw, lsh, LS):
    import math as _m
    sx, sy = self.to_screen(o.x, o.y)
    lx = sx / LS
    ly = sy / LS
    if lx < -lsw or lx > lsw * 2 or ly < -lsh or ly > lsh * 2:
        return None
    contrib = pygame.Surface((lsw, lsh))
    contrib.fill((0, 0, 0))
    color = tuple(o.color)[:3]
    inten = float(o.intensity)
    if inten <= 0:
        return None
    if o.kind == "lamp":
        R = int(o.radius * self.zoom / LS)
        if R <= 0:
            return None
        if R > max(lsw, lsh) * 3:
            R = max(lsw, lsh) * 3
        step = max(1, R // 64)
        r = R
        while r > 0:
            t = 1.0 - (r / R) ** 2
            b_ = inten * t
            c = (min(255, int(color[0] * b_)),
                 min(255, int(color[1] * b_)),
                 min(255, int(color[2] * b_)))
            if c != (0, 0, 0):
                pygame.draw.circle(contrib, c, (int(lx), int(ly)), r)
            r -= step
        c_c = (min(255, int(color[0] * inten)),
               min(255, int(color[1] * inten)),
               min(255, int(color[2] * inten)))
        pygame.draw.circle(contrib, c_c, (int(lx), int(ly)), max(1, step))
    elif o.kind == "spot":
        L = int(o.length * self.zoom / LS)
        if L <= 0:
            return None
        if L > max(lsw, lsh) * 3:
            L = max(lsw, lsh) * 3
        a1 = o.angle - o.cone / 2
        a2 = o.angle + o.cone / 2
        step = max(1, L // 48)
        r = L
        while r > 0:
            t = 1.0 - (r / L) ** 2
            b_ = inten * t
            c = (min(255, int(color[0] * b_)),
                 min(255, int(color[1] * b_)),
                 min(255, int(color[2] * b_)))
            if c != (0, 0, 0):
                pts = [(int(lx), int(ly))]
                steps = 12
                for i in range(steps + 1):
                    a = a1 + (a2 - a1) * i / steps
                    pts.append((int(lx + _m.cos(a) * r),
                                int(ly - _m.sin(a) * r)))
                pygame.draw.polygon(contrib, c, pts)
            r -= step
    # hard shadows from occluders (bowtie fix: skip occluder if light inside bbox)
    for oc in occluders:
        bbox = oc["bbox"]
        if bbox[0] <= o.x <= bbox[1] and bbox[2] <= o.y <= bbox[3]:
            continue
        for a_w, b_w, centroid in oc["edges"]:
            ax_w, ay_w = a_w
            bx_w, by_w = b_w
            nx = by_w - ay_w
            ny = -(bx_w - ax_w)
            nc_dot = nx * (centroid[0] - ax_w) + ny * (centroid[1] - ay_w)
            tlx = o.x - ax_w
            tly = o.y - ay_w
            if (nx * tlx + ny * tly) * nc_dot >= 0:
                continue
            a_sx, a_sy = self.to_screen(ax_w, ay_w)
            b_sx, b_sy = self.to_screen(bx_w, by_w)
            a_lx, a_ly = a_sx / LS, a_sy / LS
            b_lx, b_ly = b_sx / LS, b_sy / LS
            def _ext(px, py):
                ddx = px - lx
                ddy = py - ly
                mag = _m.hypot(ddx, ddy) or 1.0
                return (px + ddx / mag * 5000.0, py + ddy / mag * 5000.0)
            f1 = _ext(a_lx, a_ly)
            f2 = _ext(b_lx, b_ly)
            pygame.draw.polygon(contrib, (0, 0, 0),
                                [(int(a_lx), int(a_ly)),
                                 (int(b_lx), int(b_ly)),
                                 (int(f2[0]), int(f2[1])),
                                 (int(f1[0]), int(f1[1]))])
    return contrib

  def _draw_ghosted(self, obj):
    # <STRANGE>#526: ???????????????????????????? ???????????? ?????? ???????????????? ?????? ???????????? ????????????
    from .objects import (
      EditorPeg, EditorPlatform, EditorBackground, EditorItem, EditorSpawner,
      EditorButton, EditorAnchor,
    )
    col = (255, 255, 255, 70)
    if isinstance(obj, EditorAnchor):
      sx, sy = self.to_screen(obj.x, obj.y)
      r = max(1, int((obj.size / 2) * self.zoom))
      rr = pygame.Rect(int(sx - r), int(sy - r), r * 2, r * 2)
      pygame.draw.rect(self.screen, col, rr, 1)
      return
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

  def _draw_anchor_zones(self):
    # <STRANGE>#1409: draw boundary-only rectangles between paired A/B
    if not hasattr(self, "_anchor_pairs"):
      return
    try:
      pairs, _free, _assigned, _zone_s = self._anchor_pairs()
    except Exception:
      return
    for bnd, a, b in pairs:
      l = min(a.x, b.x); r = max(a.x, b.x)
      bt = min(a.y, b.y); tt = max(a.y, b.y)
      x0, y0 = self.to_screen(l, tt)
      x1, y1 = self.to_screen(r, bt)
      rect = pygame.Rect(int(min(x0, x1)), int(min(y0, y1)),
                         int(abs(x1 - x0)), int(abs(y1 - y0)))
      if rect.w < 2 or rect.h < 2:
        continue
      pygame.draw.rect(self.screen, ANCHOR_ZONE_EDGE, rect, 2)

  def _draw_anchor_panel(self):
    # <STRANGE>#1472: A/B -> binding only. S -> name/weight/max_limit + objects + Bake
    if not getattr(self, "mind_mode", False):
      self._anchor_panel_pos = None
      return
    if self.tool != "anchor":
      self._anchor_panel_pos = None
      return
    sel = None
    for o in self.selection:
      if hasattr(o, "variant"):
        sel = o
        break
    if sel is None:
      self._anchor_panel_pos = None
      return
    variant = getattr(sel, "variant", "A")
    font = self.font
    font_small = pygame.font.SysFont(None, 18)
    font_title = pygame.font.SysFont(None, 22, bold=True)
    W = 300
    top = self.panel.height() + 8
    left = 10
    if variant in ("A", "B"):
      y_title = 10
      y_info = 42
      y_rows_start = 68
      row_h = 24
      H = y_rows_start + row_h + 16
      panel = pygame.Surface((W, H), pygame.SRCALPHA)
      panel.fill((24, 27, 33, 230))
      pygame.draw.rect(panel, (60, 66, 78), panel.get_rect(), 1, border_radius=6)
      panel.blit(font_title.render("ANCHOR " + variant,
                                   True, (225, 230, 240)), (12, y_title))
      panel.blit(font_small.render("pos %d, %d" % (int(sel.x), int(sel.y)),
                                   True, (170, 176, 188)), (12, y_info))
      row = pygame.Rect(left + 12, top + y_rows_start, W - 24, row_h)
      def _to_local_a(r):
        return pygame.Rect(r.x - left, r.y - top, r.w, r.h)
      self._draw_anchor_row(panel, _to_local_a(row), "binding",
                            getattr(sel, "binding", "") or "<empty>", "binding")
      self.screen.blit(panel, (left, top))
      self._anchor_panel_pos = {"rows": {"binding": row}, "buttons": []}
      return
    if variant != "S":
      self._anchor_panel_pos = None
      return
    pairs, free_s, assigned, zone_s = self._anchor_pairs()
    bnd = assigned.get(id(sel))
    if bnd is None:
      self._anchor_panel_pos = None
      return
    A = B = None
    for b, a, b_ in pairs:
      if b == bnd:
        A = a
        B = b_
        break
    if A is None or B is None:
      self._anchor_panel_pos = None
      return
    l, r_, bt, tt = self._anchor_zone_rect(A, B)
    inside = []
    for o in self.objects:
      if hasattr(o, "variant"):
        continue
      try:
        if o.intersects_rect(l, r_, bt, tt):
          inside.append(o)
      except Exception:
        pass
    MAX_OBJ = 5
    shown = inside[:MAX_OBJ]
    extra = max(0, len(inside) - MAX_OBJ)
    list_rows = len(shown) + (1 if extra > 0 else 0)
    if list_rows < 1:
      list_rows = 1
    y_title = 10
    y_info = 42
    y_rows_start = 68
    row_h = 24
    row_gap = 4
    y_objs_label = y_rows_start + 3 * (row_h + row_gap) + 8
    y_objs_start = y_objs_label + 20
    y_buttons = y_objs_start + list_rows * 20 + 8
    H = y_buttons + 26 + 12
    panel = pygame.Surface((W, H), pygame.SRCALPHA)
    panel.fill((24, 27, 33, 230))
    pygame.draw.rect(panel, (60, 66, 78), panel.get_rect(), 1, border_radius=6)
    panel.blit(font_title.render("ANCHOR S  " + str(bnd),
                                 True, (225, 230, 240)), (12, y_title))
    panel.blit(font_small.render("pos %d, %d" % (int(sel.x), int(sel.y)),
                                 True, (170, 176, 188)), (12, y_info))
    rows_screen = {
      "name":      pygame.Rect(left + 12, top + y_rows_start + (row_h + row_gap) * 0, W - 24, row_h),
      "weight":    pygame.Rect(left + 12, top + y_rows_start + (row_h + row_gap) * 1, W - 24, row_h),
      "max_limit": pygame.Rect(left + 12, top + y_rows_start + (row_h + row_gap) * 2, W - 24, row_h),
    }
    def _to_local_s(r):
      return pygame.Rect(r.x - left, r.y - top, r.w, r.h)
    self._draw_anchor_row(panel, _to_local_s(rows_screen["name"]),
                          "name", getattr(sel, "name", "") or "<empty>", "name")
    self._draw_anchor_row(panel, _to_local_s(rows_screen["weight"]),
                          "weight", str(int(getattr(sel, "weight", 1))), "weight")
    self._draw_anchor_row(panel, _to_local_s(rows_screen["max_limit"]),
                          "max_limit", str(int(getattr(sel, "max_limit", 1))), "max_limit")
    panel.blit(font_small.render("objects: %d" % len(inside),
                                 True, (170, 176, 188)), (12, y_objs_label))
    yy = y_objs_start
    if not inside:
      panel.blit(font_small.render("<empty>", True, (140, 146, 158)), (16, yy))
      yy += 20
    else:
      for o in shown:
        oid = getattr(o, "id", "") or "<no id>"
        dx = int(o.x - sel.x)
        dy = int(o.y - sel.y)
        panel.blit(font_small.render(oid, True, (220, 225, 235)), (16, yy))
        panel.blit(font_small.render("(%+d, %+d)" % (dx, dy),
                                     True, (140, 146, 158)), (W - 110, yy))
        yy += 20
      if extra > 0:
        panel.blit(font_small.render("... +%d more" % extra,
                                     True, (140, 146, 158)), (16, yy))
        yy += 20
    self.screen.blit(panel, (left, top))
    bw, bh = 120, 26
    bx = left + 12
    by = top + y_buttons
    btn_rect = pygame.Rect(bx, by, bw, bh)
    mx, my = pygame.mouse.get_pos()
    hov = btn_rect.collidepoint((mx, my))
    bg = (80, 88, 102) if hov else (60, 66, 78)
    from .const import GOLD
    pygame.draw.rect(self.screen, bg, btn_rect, border_radius=4)
    pygame.draw.rect(self.screen, GOLD if hov else (105, 112, 126),
                     btn_rect, 1, border_radius=4)
    ts = font.render("Bake zone", True, (225, 230, 240))
    self.screen.blit(ts, ts.get_rect(center=btn_rect.center))
    self._anchor_panel_pos = {"rows": rows_screen,
                              "buttons": [(btn_rect, "bake")]}

  def _draw_anchor_row(self, panel, local_rect, label, value, focus_key):
    font = self.font
    lr = pygame.Rect(int(local_rect.x), int(local_rect.y),
                     int(local_rect.w), int(local_rect.h))
    focused = (focus_key is not None and getattr(self, "anchor_focus", None) == focus_key)
    bg = (32, 46, 60) if focused else (42, 46, 56)
    pygame.draw.rect(panel, bg, lr, border_radius=3)
    edge = (255, 215, 0) if focused else (70, 76, 88)
    pygame.draw.rect(panel, edge, lr, 1, border_radius=3)
    panel.blit(font.render(label, True, (170, 176, 188)),
               (lr.x + 8, lr.y + (lr.h - font.get_height()) // 2))
    txt = str(value)
    if focused:
      txt = getattr(self, "anchor_buffer", "")
    ts = font.render(txt, True, (225, 230, 240))
    panel.blit(ts, (lr.right - ts.get_width() - 10,
                    lr.y + (lr.h - ts.get_height()) // 2))
    if focused and getattr(self, "anchor_cursor_blink", 0.0) < 0.5:
      cx = lr.right - 8
      pygame.draw.line(panel, (225, 230, 240),
                       (cx, lr.y + 5), (cx, lr.bottom - 5), 1)

  def _draw_micro_scene(self, rect):
    # <STRANGE>#2203: live lighting micro-preview
    surf = pygame.Surface(rect.size)
    surf.fill((50, 55, 65))
    
    p_rect = pygame.Rect(20, rect.h - 30, rect.w - 40, 15)
    pygame.draw.rect(surf, (150, 150, 150), p_rect)
    pygame.draw.circle(surf, (200, 200, 200), (rect.w // 2, rect.h - 40), 10)

    light = pygame.Surface(rect.size)
    light.fill(tuple(self.lighting_ambient))

    if getattr(self, "sun_enabled", False):
      sc = tuple(self.sun_color)
      si = float(self.sun_intensity)
      tint = (min(255, int(sc[0]*si)), min(255, int(sc[1]*si)), min(255, int(sc[2]*si)))
      sun = pygame.Surface(rect.size)
      sun.fill(tint)
      shadow = pygame.Surface(rect.size, pygame.SRCALPHA)
      
      dx, dy = self.sun_direction
      nd = math.hypot(dx, dy) or 1.0
      ndx, ndy = dx/nd, dy/nd
      shs_x = -ndx
      shs_y = ndy
      sl = 80
      
      # platform shadow
      p1 = (p_rect.x, p_rect.y)
      p2 = (p_rect.right, p_rect.y)
      p3 = (p_rect.right + shs_x * sl, p_rect.y + shs_y * sl)
      p4 = (p_rect.x + shs_x * sl, p_rect.y + shs_y * sl)
      pygame.draw.polygon(shadow, (0, 0, 0, 255), [p1, p2, p3, p4])
      
      # peg shadow
      cx, cy = rect.w // 2, rect.h - 40
      p1 = (cx - 10, cy)
      p2 = (cx + 10, cy)
      p3 = (cx + 10 + shs_x * sl, cy + shs_y * sl)
      p4 = (cx - 10 + shs_x * sl, cy + shs_y * sl)
      pygame.draw.polygon(shadow, (0, 0, 0, 255), [p1, p2, p3, p4])

      sun.blit(shadow, (0, 0))
      light.blit(sun, (0, 0), special_flags=pygame.BLEND_RGB_MAX)

    surf.blit(light, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    if abs(self.lighting_gain - 1.0) > 1e-3:
      g = int(max(0, min(255, round(self.lighting_gain * 255))))
      surf.fill((g, g, g), special_flags=pygame.BLEND_RGB_MULT)

    pygame.draw.rect(surf, (100, 100, 100), (0, 0, rect.w, rect.h), 1)
    self.screen.blit(surf, rect.topleft)

  def _draw_level_settings(self):
    if not getattr(self, "_level_settings_open", False):
      self._level_settings_geom = {}
      return
    sw, sh = self.screen.get_size()
    dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 160))
    self.screen.blit(dim, (0, 0))
    pw, ph = 540, 600
    px = (sw - pw) // 2
    py = (sh - ph) // 2
    panel = pygame.Rect(px, py, pw, ph)
    pygame.draw.rect(self.screen, (30, 34, 42), panel, border_radius=8)
    pygame.draw.rect(self.screen, (90, 96, 110), panel, 1, border_radius=8)
    font = self.font
    font_small = pygame.font.SysFont(None, 18)
    title = font.render("Level settings", True, (225, 230, 240))
    self.screen.blit(title, (px + 16, py + 12))

    def color_row(px_, py_, label, color, key):
      font_w = 130
      self.screen.blit(font.render(label, True, (170, 176, 188)),
                       (px_, py_ + 2))
      swatch = pygame.Rect(px_ + font_w, py_ + 2, 40, 20)
      pygame.draw.rect(self.screen, tuple(color)[:3], swatch)
      pygame.draw.rect(self.screen, (105, 112, 126), swatch, 1)
      
      rst_rect = pygame.Rect(swatch.right + 10, py_ + 1, 30, 22)
      pygame.draw.rect(self.screen, (58, 128, 92), rst_rect, border_radius=3)
      pygame.draw.rect(self.screen, (105, 112, 126), rst_rect, 1, border_radius=3)
      rs = font.render("R", True, (225, 230, 240))
      self.screen.blit(rs, rs.get_rect(center=rst_rect.center))
      
      geo["color_rects"][key] = swatch
      geo["reset_rects"][key] = rst_rect
      return swatch

    def slider_row(px_, py_, label, frac, text, key):
      font_w = 130
      self.screen.blit(font.render(label, True, (170, 176, 188)),
                       (px_, py_ + 2))
      r = pygame.Rect(px_ + font_w, py_ + 4, 200, 16)
      pygame.draw.rect(self.screen, (20, 22, 28), r, border_radius=4)
      fw = int(r.w * max(0.0, min(1.0, frac)))
      if fw > 0:
        pygame.draw.rect(self.screen, (58, 128, 92),
                         pygame.Rect(r.x, r.y, fw, r.h), border_radius=4)
      pygame.draw.rect(self.screen, (105, 112, 126), r, 1, border_radius=4)

      txt_rect = pygame.Rect(r.right + 8, py_ + 1, 60, 18)
      focused = (getattr(self, "_ls_focus", None) == key)
      bg_t = (32, 46, 60) if focused else (20, 22, 28)
      pygame.draw.rect(self.screen, bg_t, txt_rect, border_radius=3)
      pygame.draw.rect(self.screen, (255,215,0) if focused else (60,66,78), txt_rect, 1, border_radius=3)
      t_val = getattr(self, "_ls_buffer", "") if focused else text
      ks = font.render(t_val, True, (225, 230, 240))
      self.screen.blit(ks, (txt_rect.centerx - ks.get_width()//2, txt_rect.centery - ks.get_height()//2))

      rst_rect = pygame.Rect(txt_rect.right + 8, py_ + 1, 30, 18)
      pygame.draw.rect(self.screen, (58, 128, 92), rst_rect, border_radius=3)
      pygame.draw.rect(self.screen, (105, 112, 126), rst_rect, 1, border_radius=3)
      rs = font.render("R", True, (225, 230, 240))
      self.screen.blit(rs, rs.get_rect(center=rst_rect.center))

      geo["text_rects"][key] = txt_rect
      geo["reset_rects"][key] = rst_rect
      geo["values"][key] = text
      return r

    # ---- section 1: lighting ----
    enabled = self.lighting is not None
    cb = pygame.Rect(px + 16, py + 48, 18, 18)
    pygame.draw.rect(self.screen, (20, 22, 28), cb, border_radius=3)
    pygame.draw.rect(self.screen, (105, 112, 126), cb, 1, border_radius=3)
    if enabled:
      pygame.draw.rect(self.screen, (58, 128, 92), cb.inflate(-6, -6),
                       border_radius=2)
    self.screen.blit(font.render("Enable lighting", True, (200, 206, 218)),
                     (cb.right + 8, cb.y + 1))
    cb_rect = pygame.Rect(px + 12, py + 44, 260, 26)

    geo = {"sliders": {}, "text_rects": {}, "color_rects": {}, "reset_rects": {}, "values": {}}
    y = py + 84
    if enabled:
      color_row(px + 16, y, "Ambient Color", self.lighting_ambient, "ambient")
      y += 30
      geo["sliders"]["gain"] = slider_row(px + 16, y, "Gain", self.lighting_gain / 3.0,
                               "%.2f" % self.lighting_gain, "gain")
      y += 36
    else:
      y += 2 * 28

    # separator
    pygame.draw.line(self.screen, (60, 66, 78),
                     (px + 16, y), (px + pw - 16, y), 1)
    y += 10

    # ---- section 2: sun ----
    sun_on = bool(getattr(self, "sun_enabled", False))
    sun_cb = pygame.Rect(px + 16, y + 4, 18, 18)
    pygame.draw.rect(self.screen, (20, 22, 28), sun_cb, border_radius=3)
    pygame.draw.rect(self.screen, (105, 112, 126), sun_cb, 1, border_radius=3)
    if sun_on:
      pygame.draw.rect(self.screen, (58, 128, 92), sun_cb.inflate(-6, -6),
                       border_radius=2)
    self.screen.blit(font.render("Sun (passive sky light)", True, (200, 206, 218)),
                     (sun_cb.right + 8, sun_cb.y + 1))
    sun_cb_rect = pygame.Rect(px + 12, y, 260, 26)
    y += 32
    if sun_on:
      color_row(px + 16, y, "Sun Color", self.sun_color, "sun")
      y += 30
      geo["sliders"]["sun_int"] = slider_row(px + 16, y, "Sun intensity",
                                  self.sun_intensity / 2.0,
                                  "%.2f" % self.sun_intensity, "sun_int")
      y += 26
      dx_, dy_ = self.sun_direction
      geo["sliders"]["sun_dx"] = slider_row(px + 16, y, "Sun dir X",
                                 (dx_ + 1.0) / 2.0, "%.2f" % dx_, "sun_dx")
      y += 26
      geo["sliders"]["sun_dy"] = slider_row(px + 16, y, "Sun dir Y",
                                 (dy_ + 1.0) / 2.0, "%.2f" % dy_, "sun_dy")
      y += 26
      geo["sliders"]["sun_slen"] = slider_row(px + 16, y, "Shadow len",
                                    getattr(self, "sun_shadow_length", 2000.0) / 5000.0,
                                    "%.0f" % getattr(self, "sun_shadow_length", 2000.0), "sun_slen")
      y += 26
      geo["sliders"]["sun_glen"] = slider_row(px + 16, y, "Gradient len",
                                    getattr(self, "sun_gradient_length", 60.0) / 500.0,
                                    "%.0f" % getattr(self, "sun_gradient_length", 60.0), "sun_glen")
      y += 30

    # ---- micro scene & reset all ----
    if enabled or sun_on:
      micro_rect = pygame.Rect(px + 16, py + 440, 280, 120)
      self._draw_micro_scene(micro_rect)
      geo["micro_scene"] = micro_rect

      reset_all_rect = pygame.Rect(px + pw - 116, py + 490, 100, 30)
      pygame.draw.rect(self.screen, (60, 66, 78), reset_all_rect, border_radius=4)
      pygame.draw.rect(self.screen, (105, 112, 126), reset_all_rect, 1, border_radius=4)
      ts = font.render("Reset All", True, (225, 230, 240))
      self.screen.blit(ts, ts.get_rect(center=reset_all_rect.center))
      geo["reset_all"] = reset_all_rect

    # ---- buttons ----
    btn_y = py + ph - 46
    close_rect = pygame.Rect(px + pw - 100, btn_y, 80, 30)
    toggle_lbl = "Preview: ON" if getattr(self, "light_preview", False) else "Preview: OFF"
    toggle_rect = pygame.Rect(px + pw - 100 - 110 - 10, btn_y, 110, 30)
    for r_, label, is_on in ((toggle_rect, toggle_lbl,
                              getattr(self, "light_preview", False)),
                             (close_rect, "Close", False)):
      bg = (58, 128, 92) if is_on else (60, 66, 78)
      pygame.draw.rect(self.screen, bg, r_, border_radius=4)
      pygame.draw.rect(self.screen, (105, 112, 126), r_, 1, border_radius=4)
      ts = font.render(label, True, (225, 230, 240))
      self.screen.blit(ts, ts.get_rect(center=r_.center))

    self._level_settings_geom = {
      "panel": panel,
      "cb": cb_rect,
      "sun_cb": sun_cb_rect,
      "sliders": geo["sliders"],
      "text_rects": geo["text_rects"],
      "color_rects": geo["color_rects"],
      "reset_rects": geo["reset_rects"],
      "reset_all": geo.get("reset_all"),
      "values": geo["values"],
      "toggle": toggle_rect,
      "close": close_rect,
    }

  def _make_color_wheel(self, radius):
    import math as _m
    import colorsys as _cs
    d = radius * 2
    surf = pygame.Surface((d, d), pygame.SRCALPHA)
    for y in range(d):
      for x in range(d):
        dx = x - radius + 0.5
        dy = y - radius + 0.5
        dist = _m.hypot(dx, dy)
        if dist > radius:
          continue
        hue = (_m.atan2(dy, dx) / (2 * _m.pi)) % 1.0
        sat = min(1.0, dist / radius)
        r, g, b = _cs.hsv_to_rgb(hue, sat, 1.0)
        surf.set_at((x, y), (int(r * 255), int(g * 255), int(b * 255), 255))
    return surf

  def _draw_color_picker(self):
    if getattr(self, "_color_edit_owner", None) is None:
      return
    import math as _m
    import colorsys as _cs
    sw, sh = self.screen.get_size()
    dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 130))
    self.screen.blit(dim, (0, 0))
    pw, ph = 400, 340
    px = (sw - pw) // 2
    py = (sh - ph) // 2
    panel = pygame.Rect(px, py, pw, ph)
    pygame.draw.rect(self.screen, (30, 34, 42), panel, border_radius=8)
    pygame.draw.rect(self.screen, (90, 96, 110), panel, 1, border_radius=8)
    font = self.font
    title = font.render("Edit color", True, (225, 230, 240))
    self.screen.blit(title, (px + 16, py + 12))
    wheel_radius = 100
    wheel_cx = px + 24 + wheel_radius
    wheel_cy = py + 56 + wheel_radius
    wheel_rect = pygame.Rect(wheel_cx - wheel_radius, wheel_cy - wheel_radius,
                             wheel_radius * 2, wheel_radius * 2)
    if self._color_wheel_surface is None or \
       self._color_wheel_surface.get_width() != wheel_radius * 2:
      self._color_wheel_surface = self._make_color_wheel(wheel_radius)
    self.screen.blit(self._color_wheel_surface, wheel_rect.topleft)
    wx = wheel_cx + _m.cos(self._color_edit_h * 2 * _m.pi) * self._color_edit_s * wheel_radius
    wy = wheel_cy + _m.sin(self._color_edit_h * 2 * _m.pi) * self._color_edit_s * wheel_radius
    pygame.draw.circle(self.screen, (0, 0, 0), (int(wx), int(wy)), 8, 2)
    pygame.draw.circle(self.screen, (255, 255, 255), (int(wx), int(wy)), 6, 2)
    info_x = wheel_rect.right + 24
    info_w = pw - (info_x - px) - 16
    r, g, b = _cs.hsv_to_rgb(self._color_edit_h, self._color_edit_s, self._color_edit_v)
    r, g, b = int(r * 255), int(g * 255), int(b * 255)
    prev_rect = pygame.Rect(info_x, py + 56, info_w, 60)
    pygame.draw.rect(self.screen, (r, g, b), prev_rect, border_radius=4)
    pygame.draw.rect(self.screen, (90, 96, 110), prev_rect, 1, border_radius=4)
    rgb_lbl = font.render("RGB: %d, %d, %d" % (r, g, b), True, (200, 206, 218))
    self.screen.blit(rgb_lbl, (info_x, py + 124))
    val_lbl = font.render("Value", True, (170, 176, 188))
    self.screen.blit(val_lbl, (info_x, py + 152))
    val_rect = pygame.Rect(info_x, py + 174, info_w, 24)
    pygame.draw.rect(self.screen, (20, 22, 28), val_rect, border_radius=4)
    fill_w = int(val_rect.w * self._color_edit_v)
    if fill_w > 0:
      pygame.draw.rect(self.screen, (r, g, b),
                       pygame.Rect(val_rect.x, val_rect.y, fill_w, val_rect.h),
                       border_radius=4)
    pygame.draw.rect(self.screen, (90, 96, 110), val_rect, 1, border_radius=4)
    vp = font.render("%d%%" % int(self._color_edit_v * 100), True, (200, 206, 218))
    self.screen.blit(vp, (info_x, py + 202))
    btn_y = py + ph - 46
    cancel_rect = pygame.Rect(px + pw - 100, btn_y, 80, 30)
    ok_rect = pygame.Rect(px + pw - 190, btn_y, 80, 30)
    for r_, label, primary in ((ok_rect, "OK", True), (cancel_rect, "Cancel", False)):
      bg = (58, 128, 92) if primary else (60, 66, 78)
      pygame.draw.rect(self.screen, bg, r_, border_radius=4)
      pygame.draw.rect(self.screen, (105, 112, 126), r_, 1, border_radius=4)
      ts = font.render(label, True, (225, 230, 240))
      self.screen.blit(ts, ts.get_rect(center=r_.center))
    self._color_picker_geom = {
      "wheel_rect": wheel_rect,
      "val_rect": val_rect,
      "ok_rect": ok_rect,
      "cancel_rect": cancel_rect,
      "panel_rect": panel,
    }

  def _draw_label_modal(self):
    # <STRANGE>#2100: label modal overlay; safe no-op when closed.
    if not getattr(self, "_label_modal_open", False):
      self._label_modal_geom = {}
      return
    tgt = getattr(self, "_label_modal_target", None)
    if tgt is None:
      self._label_modal_open = False
      self._label_modal_geom = {}
      return
    sw, sh = self.screen.get_size()
    dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 150))
    self.screen.blit(dim, (0, 0))
    pw, ph = 560, 460
    px = (sw - pw) // 2
    py = (sh - ph) // 2
    panel = pygame.Rect(px, py, pw, ph)
    pygame.draw.rect(self.screen, (30, 34, 42), panel, border_radius=8)
    pygame.draw.rect(self.screen, (90, 96, 110), panel, 1, border_radius=8)
    font = self.font
    font_title = pygame.font.SysFont(None, 24, bold=True)
    font_small = pygame.font.SysFont(None, 18)
    title = font_title.render("Label", True, (225, 230, 240))
    self.screen.blit(title, (px + 16, py + 12))

    def draw_row(y, key, label, value):
      row = pygame.Rect(px + 16, y, pw - 32, 28)
      focused = (getattr(self, "_label_modal_focus", None) == key)
      pygame.draw.rect(self.screen, (42, 46, 56), row, border_radius=3)
      pygame.draw.rect(self.screen,
                       (255, 215, 0) if focused else (70, 76, 88),
                       row, 1, border_radius=3)
      self.screen.blit(font.render(label, True, (170, 176, 188)),
                       (row.x + 8, row.y + 6))
      txt = str(value)
      if focused:
        txt = getattr(self, "_label_modal_buffer", "")
      ts = font.render(txt, True, (225, 230, 240))
      self.screen.blit(ts, (row.right - ts.get_width() - 10, row.y + 6))
      return row

    y = py + 48
    text_row = draw_row(y, "text", "text",
                        str(getattr(tgt, "text", "label")))
    y += 34
    target_row = draw_row(y, "target", "target",
                          str(getattr(tgt, "target_trigger_id", "")))
    y += 40
    self.screen.blit(font_small.render(
        "chips: %d" % len(getattr(tgt, "chips", [])),
        True, (170, 176, 188)), (px + 16, y))
    y += 22
    for i, c in enumerate(getattr(tgt, "chips", [])):
      kind = c.get("kind", "?")
      cr = pygame.Rect(px + 16, y, pw - 32, 24)
      pygame.draw.rect(self.screen, (42, 46, 56), cr, border_radius=3)
      pygame.draw.rect(self.screen, (70, 76, 88), cr, 1, border_radius=3)
      self.screen.blit(font.render("%d: %s" % (i, kind),
                                    True, (225, 230, 240)),
                       (cr.x + 8, cr.y + 3))
      y += 28
    by = py + ph - 46
    close_r = pygame.Rect(px + pw - 100, by, 80, 30)
    gen_r = pygame.Rect(px + pw - 200, by, 90, 30)
    mx, my = pygame.mouse.get_pos()
    for r_, label in ((close_r, "Close"), (gen_r, "Generate")):
      hov = r_.collidepoint((mx, my))
      bg = (80, 88, 102) if hov else (60, 66, 78)
      pygame.draw.rect(self.screen, bg, r_, border_radius=4)
      pygame.draw.rect(self.screen, (105, 112, 126), r_, 1, border_radius=4)
      ts = font.render(label, True, (225, 230, 240))
      self.screen.blit(ts, ts.get_rect(center=r_.center))
    self._label_modal_geom = {
      "panel": panel,
      "text_row": text_row,
      "target_row": target_row,
      "close": close_r,
      "generate": gen_r,
    }

  def _draw_plan_ghost(self):
    # <STRANGE>#1174: silhouette shown whenever a plan exists;
    # uses live preview during a drag, otherwise the stored plan dx/dy.
    if self.tool != "planner":
      return
    dx = None
    dy = None
    dragging = False
    prev = getattr(self, "_plan_preview", None)
    if prev is not None:
      dx = prev.get("dx", 0.0)
      dy = prev.get("dy", 0.0)
      dragging = True
    else:
      p = getattr(self, "plan", None)
      if p is None:
        return
      dx = p.get("dx", 0.0)
      dy = p.get("dy", 0.0)
    from .objects import (EditorPeg, EditorSpawner, EditorArtifact,
                          EditorButton, EditorPlatform, EditorBackground,
                          EditorItem, EditorTrigger)
    col = (120, 220, 255)
    ghost = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
    # <STRANGE>#1210: fade ghost during preview as the object approaches
    fade = 255
    if (not dragging) and getattr(self, "plan_preview_active", False):
      _dur = float((self.plan or {}).get("dur", 0.5))
      _phase = getattr(self, "plan_preview_phase", "forward")
      _t = getattr(self, "plan_preview_t", 0.0)
      if _phase == "forward":
        _k = min(1.0, _t / max(0.001, _dur))
      elif _phase == "hold":
        _k = 1.0
      else:
        _k = 0.0
      fade = int(255 * max(0.0, 1.0 - _k))
    targets = self.selection if dragging else (self.plan or {}).get("objects", [])
    orig = {} if dragging else (self.plan or {}).get("orig_positions", {})
    for obj in targets:
      if dragging:
        base_x, base_y = obj.x, obj.y
      else:
        base_x, base_y = orig.get(id(obj), (obj.x, obj.y))
      if isinstance(obj, (EditorPeg, EditorSpawner, EditorArtifact, EditorButton)):
        sx, sy = self.to_screen(base_x + dx, base_y + dy)
        r = max(2, int(obj.r * self.zoom))
        pygame.draw.circle(ghost, (*col, 200), (int(sx), int(sy)), r)
        pygame.draw.circle(ghost, (*col, 255), (int(sx), int(sy)), r, 3)
      elif isinstance(obj, (EditorPlatform, EditorBackground)) and getattr(obj, "polygon", False):
        pts = [self.to_screen(base_x + (x - obj.x) + dx, base_y + (y - obj.y) + dy) for (x, y) in obj.world_points()]
        ipts = [(int(x), int(y)) for x, y in pts]
        if len(ipts) >= 3:
          pygame.draw.polygon(ghost, (*col, 200), ipts)
          pygame.draw.polygon(ghost, (*col, 255), ipts, 3)
      else:
        try:
          l, r, b, t = obj.world_rect()
        except Exception:
          continue
        x0, y0 = self.to_screen(base_x + (l - obj.x) + dx, base_y + (t - obj.y) + dy)
        x1, y1 = self.to_screen(base_x + (r - obj.x) + dx, base_y + (b - obj.y) + dy)
        rr = pygame.Rect(int(min(x0, x1)), int(min(y0, y1)),
                         int(abs(x1 - x0)), int(abs(y1 - y0)))
        ov = pygame.Surface((max(1, rr.w), max(1, rr.h)), pygame.SRCALPHA)
        ov.fill((*col, 200))
        ghost.blit(ov, rr.topleft)
        pygame.draw.rect(ghost, (*col, 255), rr, 3)
    # <STRANGE>#1175: during drag, draw a thin line from origin to target.
    if dragging:
      for obj in self.selection:
        try:
          ox, oy = self.to_screen(obj.x, obj.y)
          tx, ty = self.to_screen(obj.x + dx, obj.y + dy)
          pygame.draw.line(self.screen, (*col, 120),
                           (int(ox), int(oy)), (int(tx), int(ty)), 1)
        except Exception:
          pass
    if fade < 255:
      ghost.fill((255, 255, 255, fade), special_flags=pygame.BLEND_RGBA_MULT)
    self.screen.blit(ghost, (0, 0))

  def _draw_plan_panel(self):
    # <STRANGE>#1180: left panel; ALL hit rects stored in SCREEN coords
    if not getattr(self, "mind_mode", False):
      return
    if self.tool != "planner":
      return
    p = getattr(self, "plan", None)
    if p is None:
      self._plan_panel_pos = None
      return
    font = self.font
    font_small = pygame.font.SysFont(None, 18)
    font_title = pygame.font.SysFont(None, 22, bold=True)
    W = 300
    top = self.panel.height() + 8
    left = 10
    objs = p.get("objects", [])
    # <STRANGE>#1311: cap visible rows so plan panel never overflows
    MAX_ROWS = 8
    shown = objs[:MAX_ROWS]
    extra = max(0, len(objs) - MAX_ROWS)
    list_rows = len(shown) + (1 if extra > 0 else 0)
    # vertical layout (local to panel):
    y_title = 10
    y_objs_label = 42
    y_objs_start = 62
    y_rows_start = y_objs_start + list_rows * 22 + 8
    row_h = 24
    row_gap = 4
    y_buttons = y_rows_start + 4 * (row_h + row_gap) + 8
    H = y_buttons + 26 + 12
    panel = pygame.Surface((W, H), pygame.SRCALPHA)
    panel.fill((24, 27, 33, 230))
    pygame.draw.rect(panel, (60, 66, 78), panel.get_rect(), 1, border_radius=6)
    panel.blit(font_title.render("PLAN", True, (225, 230, 240)), (12, y_title))
    panel.blit(font_small.render("objects:", True, (170, 176, 188)), (12, y_objs_label))
    yy = y_objs_start
    for o in shown:
      oid = getattr(o, "id", "") or "<no id>"
      panel.blit(font_small.render(oid, True, (220, 225, 235)), (16, yy))
      panel.blit(font_small.render("(%d, %d)" % (int(o.x), int(o.y)),
                                   True, (140, 146, 158)),
                 (W - 110, yy))
      yy += 22
    if extra > 0:
      panel.blit(font_small.render("... +%d more" % extra,
                                   True, (140, 146, 158)), (16, yy))
      yy += 22
    # rows: local Y -> screen Y by adding `top`
    rows_screen = {
      "dx":  pygame.Rect(left + 12, top + y_rows_start + (row_h + row_gap) * 0, W - 24, row_h),
      "dy":  pygame.Rect(left + 12, top + y_rows_start + (row_h + row_gap) * 1, W - 24, row_h),
      "dur": pygame.Rect(left + 12, top + y_rows_start + (row_h + row_gap) * 2, W - 24, row_h),
      "ease":pygame.Rect(left + 12, top + y_rows_start + (row_h + row_gap) * 3, W - 24, row_h),
    }
    dx = p.get("dx", 0.0); dy = p.get("dy", 0.0)
    dur = p.get("dur", 0.5); ease = p.get("ease", "out")
    def _to_local(r):
      return pygame.Rect(r.x - left, r.y - top, r.w, r.h)
    self._draw_plan_row_local(panel, _to_local(rows_screen["dx"]),  "dx",  "%+d" % int(dx), "dx")
    self._draw_plan_row_local(panel, _to_local(rows_screen["dy"]),  "dy",  "%+d" % int(dy), "dy")
    self._draw_plan_row_local(panel, _to_local(rows_screen["dur"]), "dur", "%.2f" % dur,     "dur")
    self._draw_plan_row_local(panel, _to_local(rows_screen["ease"]),"ease", ease + "  >",    None)
    self.screen.blit(panel, (left, top))
    # buttons: absolute screen rects
    bw, bh, gap = 88, 26, 8
    bx = left + 12
    by = top + y_buttons
    buttons = []
    labels = [("Preview", "preview"), ("Copy text", "copy"), ("Clear", "clear")]
    mx, my = pygame.mouse.get_pos()
    from .const import GOLD
    for label, key in labels:
      r = pygame.Rect(bx, by, bw, bh)
      buttons.append((r, key))
      hov = r.collidepoint((mx, my))
      active = (key == "preview" and getattr(self, "plan_preview_active", False))
      bg = (58, 128, 92) if active else ((80, 88, 102) if hov else (60, 66, 78))
      pygame.draw.rect(self.screen, bg, r, border_radius=4)
      pygame.draw.rect(self.screen, GOLD if active else (105, 112, 126), r, 1, border_radius=4)
      ts = font.render(label, True, (225, 230, 240))
      self.screen.blit(ts, ts.get_rect(center=r.center))
      bx += bw + gap
    self._plan_panel_pos = {"rows": rows_screen, "buttons": buttons}

  def _draw_markup_panel(self):
    # <STRANGE>#1308: left panel for markup tool
    if not getattr(self, "mind_mode", False):
      self._markup_panel_pos = None
      return
    if self.tool != "markup":
      self._markup_panel_pos = None
      return
    font = self.font
    font_small = pygame.font.SysFont(None, 18)
    font_title = pygame.font.SysFont(None, 22, bold=True)
    W = 300
    top = self.panel.height() + 8
    left = 10
    objs = list(self.selection)
    # <STRANGE>#1310: cap visible object rows so panel never overflows
    MAX_ROWS = 6
    shown = objs[:MAX_ROWS]
    extra = max(0, len(objs) - MAX_ROWS)
    list_rows = max(1, len(shown) + (1 if extra > 0 else 0))
    y_title = 10
    y_objs_label = 42
    y_objs_start = 62
    y_rows_start = y_objs_start + list_rows * 22 + 8
    row_h = 24
    row_gap = 4
    y_buttons = y_rows_start + 4 * (row_h + row_gap) + 8
    H = y_buttons + 26 + 12
    panel = pygame.Surface((W, H), pygame.SRCALPHA)
    panel.fill((24, 27, 33, 230))
    pygame.draw.rect(panel, (60, 66, 78), panel.get_rect(), 1, border_radius=6)
    panel.blit(font_title.render("MARKUP", True, (225, 230, 240)), (12, y_title))
    panel.blit(font_small.render("objects: %d" % len(objs),
                                 True, (170, 176, 188)), (12, y_objs_label))
    yy = y_objs_start
    if not objs:
      panel.blit(font_small.render("<no selection>", True, (140, 146, 158)), (16, yy))
      yy += 22
    else:
      for o in shown:
        oid = getattr(o, "id", "") or "<no id>"
        panel.blit(font_small.render(oid, True, (220, 225, 235)), (16, yy))
        yy += 22
      if extra > 0:
        panel.blit(font_small.render("... +%d more" % extra,
                                     True, (140, 146, 158)), (16, yy))
        yy += 22
    rows_screen = {
      "prefix":  pygame.Rect(left + 12, top + y_rows_start + (row_h + row_gap) * 0, W - 24, row_h),
      "postfix": pygame.Rect(left + 12, top + y_rows_start + (row_h + row_gap) * 1, W - 24, row_h),
      "min":     pygame.Rect(left + 12, top + y_rows_start + (row_h + row_gap) * 2, W - 24, row_h),
      "sep":     pygame.Rect(left + 12, top + y_rows_start + (row_h + row_gap) * 3, W - 24, row_h),
    }
    def _to_local(r):
      return pygame.Rect(r.x - left, r.y - top, r.w, r.h)
    self._draw_markup_row(panel, _to_local(rows_screen["prefix"]),
                          "prefix",  self.markup.get("prefix", ""), "prefix")
    self._draw_markup_row(panel, _to_local(rows_screen["postfix"]),
                          "postfix", self.markup.get("postfix", ""), "postfix")
    self._draw_markup_row(panel, _to_local(rows_screen["min"]),
                          "min",     str(self.markup.get("min", 0)), "min")
    self._draw_markup_row(panel, _to_local(rows_screen["sep"]),
                          "sep",     self.markup.get("sep", "_"), "sep")
    self.screen.blit(panel, (left, top))
    bw, bh, gap = 88, 26, 8
    bx = left + 12
    by = top + y_buttons
    buttons = []
    from .const import GOLD
    mx, my = pygame.mouse.get_pos()
    for label, key in [("Apply", "apply"), ("Clear", "clear")]:
      r = pygame.Rect(bx, by, bw, bh)
      buttons.append((r, key))
      hov = r.collidepoint((mx, my))
      bg = (80, 88, 102) if hov else (60, 66, 78)
      pygame.draw.rect(self.screen, bg, r, border_radius=4)
      pygame.draw.rect(self.screen, (105, 112, 126), r, 1, border_radius=4)
      ts = font.render(label, True, (225, 230, 240))
      self.screen.blit(ts, ts.get_rect(center=r.center))
      bx += bw + gap
    self._markup_panel_pos = {"rows": rows_screen, "buttons": buttons}

  def _draw_markup_row(self, panel, local_rect, label, value, focus_key):
    # <STRANGE>#1309: one editable markup row (panel-local coords)
    font = self.font
    lr = pygame.Rect(int(local_rect.x), int(local_rect.y),
                     int(local_rect.w), int(local_rect.h))
    focused = (focus_key is not None and getattr(self, "markup_focus", None) == focus_key)
    bg = (32, 46, 60) if focused else (42, 46, 56)
    pygame.draw.rect(panel, bg, lr, border_radius=3)
    edge = (255, 215, 0) if focused else (70, 76, 88)
    pygame.draw.rect(panel, edge, lr, 1, border_radius=3)
    panel.blit(font.render(label, True, (170, 176, 188)),
               (lr.x + 8, lr.y + (lr.h - font.get_height()) // 2))
    txt = str(value)
    if focused:
      txt = getattr(self, "markup_buffer", "")
    ts = font.render(txt, True, (225, 230, 240))
    panel.blit(ts, (lr.right - ts.get_width() - 10,
                    lr.y + (lr.h - ts.get_height()) // 2))
    if focused and getattr(self, "markup_cursor_blink", 0.0) < 0.5:
      cx = lr.right - 8
      pygame.draw.line(panel, (225, 230, 240),
                       (cx, lr.y + 5), (cx, lr.bottom - 5), 1)

  def _draw_plan_row_local(self, panel, local_rect, label, value, focus_key):
    # <STRANGE>#1181: like _draw_plan_row but coordinates are panel-local
    font = self.font
    lr = pygame.Rect(int(local_rect.x), int(local_rect.y),
                     int(local_rect.w), int(local_rect.h))
    focused = (focus_key is not None and getattr(self, "plan_focus", None) == focus_key)
    bg = (32, 46, 60) if focused else (42, 46, 56)
    pygame.draw.rect(panel, bg, lr, border_radius=3)
    edge = (255, 215, 0) if focused else (70, 76, 88)
    pygame.draw.rect(panel, edge, lr, 1, border_radius=3)
    panel.blit(font.render(label, True, (170, 176, 188)),
               (lr.x + 8, lr.y + (lr.h - font.get_height()) // 2))
    txt = value
    if focused:
      buf = getattr(self, "plan_buffer", "")
      txt = buf if buf else ""
    ts = font.render(txt, True, (225, 230, 240))
    panel.blit(ts, (lr.right - ts.get_width() - 10,
                    lr.y + (lr.h - ts.get_height()) // 2))
    if focused and getattr(self, "plan_cursor_blink", 0.0) < 0.5:
      cx = lr.right - 8
      pygame.draw.line(panel, (225, 230, 240),
                       (cx, lr.y + 5), (cx, lr.bottom - 5), 1)

  def _draw_plan_row(self, panel, rect_abs, label, value, focus_key):
    # <STRANGE>#1177: one editable row; rect_abs is in screen coords,
    # convert to panel-local.
    if rect_abs is None:
      return
    font = self.font
    info = self._plan_panel_pos
    px, py = info[0], info[1]
    lr = pygame.Rect(rect_abs.x - px, rect_abs.y - py,
                     rect_abs.w, rect_abs.h)
    focused = (getattr(self, "plan_focus", None) == focus_key)
    bg = (32, 46, 60) if focused else (42, 46, 56)
    pygame.draw.rect(panel, bg, lr, border_radius=3)
    edge = (255, 215, 0) if focused else (70, 76, 88)
    pygame.draw.rect(panel, edge, lr, 1, border_radius=3)
    panel.blit(font.render(label, True, (170, 176, 188)),
               (lr.x + 8, lr.y + (lr.h - font.get_height()) // 2))
    txt = value
    if focused:
      buf = getattr(self, "plan_buffer", "")
      txt = buf if buf else ""
    ts = font.render(txt, True, (225, 230, 240))
    panel.blit(ts, (lr.right - ts.get_width() - 10,
                    lr.y + (lr.h - ts.get_height()) // 2))
    if focused and getattr(self, "plan_cursor_blink", 0.0) < 0.5:
      cx = lr.right - 8
      pygame.draw.line(panel, (225, 230, 240),
                       (cx, lr.y + 5), (cx, lr.bottom - 5), 1)


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
    from .objects import (EditorPeg, EditorSpawner, EditorArtifact, EditorButton,
                          EditorAnchor)
    sw, sh = self.screen.get_size()
    for obj in self.objects:
      if id(obj) not in targets:
        continue
      if not self._visible(obj, sw, sh):
        continue
      if isinstance(obj, EditorAnchor):
        sx, sy = self.to_screen(obj.x, obj.y)
        r = max(2, int((obj.size / 2) * self.zoom))
        rect = pygame.Rect(int(sx - r), int(sy - r), r * 2, r * 2)
      elif isinstance(obj, (EditorPeg, EditorSpawner, EditorArtifact, EditorButton)):
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
    # <STRANGE>#1146: mind mode replaces the entire bottom tool set.
    if getattr(self, "mind_mode", False):
      self.draw_tab(self.tab_planner_rect(), "planner", self.tool == "planner")
      self.draw_tab(self.tab_markup_rect(), "markup", self.tool == "markup")
      self.draw_tab(self.tab_anchor_rect(), "anchor", self.tool == "anchor")
      self.draw_tab(self.tab_label_rect(), "label", self.tool == "label")
      self.draw_tab(self.tab_back_rect(), "back", False)
    else:
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
      self.draw_tab(self.tab_light_rect(), "light", self.tool == "light")

    z = f"{int(self.zoom * 100)}%"
    surf = render_text(self.font, z, GOLD)
    zx = self.screen.get_width() - surf.get_width() - 14
    self.screen.blit(surf, (zx, h - BOT_H + (BOT_H - surf.get_height()) // 2))
    # <STRANGE>#1540: lighting preview indicator + toggle hint
    if getattr(self, "lighting", None) is not None:
      active = bool(getattr(self, "light_preview", False))
      lbl = "LIGHT ON" if active else "F: light"
      col = (255, 215, 0) if active else (140, 146, 158)
      ls = render_text(self.font, lbl, col)
      self.screen.blit(ls, (zx - ls.get_width() - 16,
                            h - BOT_H + (BOT_H - ls.get_height()) // 2))

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
    elif name == "markup":
      f = pygame.font.SysFont(None, 28, bold=True)
      ts = f.render("M", True, (255, 215, 0))
      self.screen.blit(ts, ts.get_rect(center=(cx, cy)))
    elif name == "planner":
      f = pygame.font.SysFont(None, 28, bold=True)
      ts = f.render("P", True, (255, 215, 0))
      self.screen.blit(ts, ts.get_rect(center=(cx, cy)))
    elif name == "back":
      f = pygame.font.SysFont(None, 28, bold=True)
      ts = f.render("<", True, (220, 220, 220))
      self.screen.blit(ts, ts.get_rect(center=(cx, cy)))
    elif name == "light":
      pygame.draw.circle(self.screen, (255, 215, 0), (cx, cy), 12)
      pygame.draw.circle(self.screen, (60, 60, 60), (cx, cy), 12, 2)
      f = pygame.font.SysFont(None, 20, bold=True)
      ts = f.render("L", True, (30, 20, 0))
      self.screen.blit(ts, ts.get_rect(center=(cx, cy)))
    elif name == "button":
      pygame.draw.circle(self.screen, BUTTON_FILL, (cx, cy), BUTTON_R + 3)
      pygame.draw.circle(self.screen, BUTTON_EDGE, (cx, cy), BUTTON_R + 3, 2)
    elif name == "anchor":
      f = pygame.font.SysFont(None, 28, bold=True)
      ts = f.render("A", True, (255, 215, 0))
      self.screen.blit(ts, ts.get_rect(center=(cx, cy)))
    elif name == "label":
      f = pygame.font.SysFont(None, 22, bold=True)
      ts = f.render("Lb", True, (255, 215, 0))
      self.screen.blit(ts, ts.get_rect(center=(cx, cy)))
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
    from .objects import GLAdapter
    try:
      game.draw_at(GLAdapter(screen), cam, (0, 0), 0.0, 255, 1.0)
    except Exception:
      ir = pygame.Rect(0, 0, 40, 24)
      ir.center = r.center
      pygame.draw.rect(screen, (200, 180, 120), ir)
      pygame.draw.rect(screen, (80, 70, 50), ir, 2)

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

  def tab_light_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(1210, h - BOT_H + 6, 110, BOT_H - 12)

  def tab_anchor_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(250, h - BOT_H + 6, 110, BOT_H - 12)

  def tab_label_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(370, h - BOT_H + 6, 110, BOT_H - 12)

  def tab_planner_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(10, h - BOT_H + 6, 110, BOT_H - 12)

  def tab_back_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(490, h - BOT_H + 6, 110, BOT_H - 12)

  def tab_markup_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(130, h - BOT_H + 6, 110, BOT_H - 12)

 