"""Объекты сцены редактора: пеги, платформы, фоны, предметы, спавнеры.

Предметы делегируют отрисовку и размеры игровым классам — так редактор
автоматически видит новые типы, добавленные в игру.
"""
import math
import pymunk
import pygame

from .const import (
  PEG_R, PEG_FILL, PEG_EDGE,
  PLAT_FILL, PLAT_EDGE, PLAT_EDGE_W,
  PLAT_DEFAULT_W, PLAT_DEFAULT_H,
  RESIZE_ZONE, BG_DEFAULT_COLOR,
  LAYER_BG, LAYER_PLATFORM, LAYER_PEG, LAYER_ITEM,
  DEFAULT_ITEM_TYPE,
  SPAWNER_R, SPAWNER_FILL, SPAWNER_EDGE, SPAWNER_EDGE_W, SPAWNER_TEXT_COLOR,
  BAG_R, BAG_FILL, BAG_EDGE, BAG_EDGE_W, BAG_STRAP,
  ARTIFACT_R,
  ARTIFACT_FILL,
  ARTIFACT_EDGE,
  ARTIFACT_EDGE_W,
  ARTIFACT_LETTER_FG,
  DEFAULT_ARTIFACT_TYPE,
  TRIGGER_FILL, TRIGGER_EDGE, TRIGGER_EDGE_W, TRIGGER_LABEL_COLOR,
  TRIGGER_DEFAULT_W, TRIGGER_DEFAULT_H,
  BUTTON_R, BUTTON_FILL, BUTTON_EDGE,
  ANCHOR_SIZE, ANCHOR_A_FILL, ANCHOR_A_EDGE,
  ANCHOR_B_FILL, ANCHOR_B_EDGE, ANCHOR_S_FILL, ANCHOR_S_EDGE,
  ANCHOR_ZONE_EDGE, ANCHOR_VARIANTS, DEFAULT_ANCHOR_VARIANT,
  LIGHT_TYPES, DEFAULT_LIGHT_TYPE, LIGHT_GIZMO_R, LIGHT_GIZMO_EDGE, LIGHT_GIZMO_FILL,
  LIGHT_DEFAULTS, LIGHT_DEFAULT_AMBIENT, LIGHT_DEFAULT_GAIN,
  LABEL_PAD, LABEL_FONT_SIZE, LABEL_BG, LABEL_EDGE, LABEL_TEXT,
  LABEL_GHOST_ALPHA, LABEL_CHIP_TYPES,
)
from .helpers import make_stripe_surface, make_circle_stripe_surface
from . import settings

try:
  from game.entities.item import (
    CubeItem as GameCubeItem,
    SodaItem as GameSodaItem,
    make_item as game_make_item,
      BagItem as GameBagItem,
)
  _GAME_ITEM_AVAILABLE = True
except Exception:
  GameCubeItem = None
  GameSodaItem = None
  game_make_item = None
  _GAME_ITEM_AVAILABLE = False

_FAKE_SPACE = pymunk.Space()

GAME_ITEM_CLASSES = {}
if GameCubeItem is not None:
  GAME_ITEM_CLASSES["cube"] = GameCubeItem
if GameSodaItem is not None:
  GAME_ITEM_CLASSES["soda"] = GameSodaItem
if GameBagItem is not None:
  GAME_ITEM_CLASSES["bag"] = GameBagItem


def make_fake_item(item_type):
  cls = GAME_ITEM_CLASSES.get(item_type)
  if cls is not None:
    try:
      obj = cls(_FAKE_SPACE, (0, 0))
    except Exception:
      obj = None
    if obj is not None:
      try:
        obj.destroy()
      except Exception:
        pass
      return obj

  if game_make_item is not None:
    try:
      obj = game_make_item(_FAKE_SPACE, {"type": item_type, "x": 0, "y": 0})
    except Exception:
      obj = None
    if obj is not None:
      try:
        obj.destroy()
      except Exception:
        pass
      return obj
  return None



# <STRANGE>#2000: GLAdapter - acts as both a pygame.Surface and a GLRenderer.
# Needed because game items call draw_at(screen_or_gl, ...) with different
# first-arg semantics (CubeItem wants GLRenderer, BagItem wants Surface).
class GLAdapter:
  def __init__(self, surface):
    self.surface = surface

  # -- GLRenderer-like primitives (draw into the underlying Surface) --
  def tri(self, p0, p1, p2, color):
    try:
      pygame.draw.polygon(self.surface, color,
                          [(int(p0[0]), int(p0[1])),
                           (int(p1[0]), int(p1[1])),
                           (int(p2[0]), int(p2[1]))])
    except Exception:
      pass

  def rect(self, x, y, w, h, color):
    try:
      pygame.draw.rect(self.surface, color,
                       pygame.Rect(int(x), int(y), int(w), int(h)))
    except Exception:
      pass

  def circle(self, cx, cy, r, color, segments=None):
    try:
      r_i = int(r)
      if r_i <= 0:
        return
      pygame.draw.circle(self.surface, color, (int(cx), int(cy)), r_i)
    except Exception:
      pass

  def ring(self, cx, cy, r, width, color, segments=None):
    try:
      r_i = int(r)
      w_i = max(1, int(width))
      if r_i <= 0:
        return
      pygame.draw.circle(self.surface, color,
                         (int(cx), int(cy)), r_i, w_i)
    except Exception:
      pass

  def polygon(self, points, color):
    try:
      if len(points) < 3:
        return
      ipts = [(int(p[0]), int(p[1])) for p in points]
      pygame.draw.polygon(self.surface, color, ipts)
    except Exception:
      pass

  def polyline(self, points, color, width=1.0):
    try:
      if len(points) < 2:
        return
      ipts = [(int(p[0]), int(p[1])) for p in points]
      pygame.draw.lines(self.surface, color, False, ipts,
                        max(1, int(width)))
    except Exception:
      pass

  # -- anything else: delegate to the underlying Surface --
  def __getattr__(self, name):
    return getattr(self.surface, name)

def _point_in_poly(px, py, poly):
  # <STRANGE>#507: even-odd ray casting
  inside = False
  n = len(poly)
  j = n - 1
  for i in range(n):
    xi, yi = poly[i]
    xj, yj = poly[j]
    if ((yi > py) != (yj > py)) and \
       (px < (xj - xi) * (py - yi) / ((yj - yi) or 1e-9) + xi):
      inside = not inside
    j = i
  return inside


def default_layer_for(obj):
  if isinstance(obj, EditorBackground):
    return LAYER_BG
  if isinstance(obj, EditorPlatform):
    return LAYER_PLATFORM
  if isinstance(obj, (EditorPeg, EditorButton)):
    return LAYER_PEG
  if isinstance(obj, (EditorItem, EditorSpawner, EditorArtifact)):
    return LAYER_ITEM
  if isinstance(obj, EditorTrigger):
    return LAYER_ITEM
  if isinstance(obj, EditorAnchor):
    return LAYER_ITEM
  if isinstance(obj, EditorLight):
    return LAYER_ITEM
  if isinstance(obj, EditorLabel):
    return LAYER_ITEM
  return 0


# =========================================================
# Peg
# =========================================================
class EditorPeg:
  def __init__(self, x, y):
    self.x, self.y = x, y
    self.r = PEG_R
    self.locked = False
    # <STRANGE>#701: ?????????????? ???????? ???????? ??? 5
    self.layer = 5
    self.id = ""
    self.id = ""
    self.id = ""

  def hit(self, wx, wy):
    return (wx - self.x) ** 2 + (wy - self.y) ** 2 <= self.r ** 2

  def intersects_rect(self, l, r, b, t):
    nx = max(l, min(self.x, r))
    ny = max(b, min(self.y, t))
    return (self.x - nx) ** 2 + (self.y - ny) ** 2 <= self.r ** 2

  def to_json(self):
    # <STRANGE>#702: ?????????? ?????? dict, ?????????? ?????????????????? layer/locked
    d = {"x": int(self.x), "y": int(self.y), "layer": int(self.layer)}
    if getattr(self, "id", ""):
      d["id"] = str(self.id)
    if self.locked:
      d["locked"] = True
    return d

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


# =========================================================
# Platform
# =========================================================
class EditorPlatform:
  def __init__(self, x, y, w=None, h=None):
    self.x, self.y = x, y
    # <STRANGE>#402: ???????????? ??? ???? ???????????????? ?????????????????? (settings.json), ?????????? ??????????????
    if w is None or h is None:
      saved = settings.get_panel_size("platform")
      if saved is not None:
        w, h = saved
      else:
        w, h = PLAT_DEFAULT_W, PLAT_DEFAULT_H
    self.w, self.h = w, h
    self.fill = PLAT_FILL
    self.edge = PLAT_EDGE
    self.absorption = 0.5
    self.locked = False
    self.layer = None
    self.id = ""
    self.id = ""
    self.id = ""
    # platform polygon mode
    self.polygon = False
    self.points = []
    self.active_points = set()

  def world_rect(self):
    if self.polygon and len(self.points) >= 1:
      xs = [p[0] for p in self.points]
      ys = [p[1] for p in self.points]
      return (self.x + min(xs), self.x + max(xs),
              self.y + min(ys), self.y + max(ys))
    return (self.x - self.w / 2, self.x + self.w / 2,
            self.y - self.h / 2, self.y + self.h / 2)

  def world_points(self):
    return [(self.x + p[0], self.y + p[1]) for p in self.points]

  def to_polygon(self):
    if self.polygon:
      return
    l = self.x - self.w / 2
    r = self.x + self.w / 2
    b = self.y - self.h / 2
    t = self.y + self.h / 2
    self.points = [
      [int(l - self.x), int(b - self.y)],
      [int(r - self.x), int(b - self.y)],
      [int(r - self.x), int(t - self.y)],
      [int(l - self.x), int(t - self.y)],
    ]
    self.polygon = True
    self.active_points = set()

  def to_rect(self):
    if not self.polygon or not self.points:
      self.polygon = False
      self.points = []
      return
    xs = [p[0] for p in self.points]
    ys = [p[1] for p in self.points]
    l, r = min(xs), max(xs)
    b, t = min(ys), max(ys)
    self.w = max(1, int(r - l))
    self.h = max(1, int(t - b))
    self.x = self.x + (l + r) / 2
    self.y = self.y + (b + t) / 2
    self.polygon = False
    self.points = []
    self.active_points = set()

  def rotate_around_center(self, degrees):
    import math as _m
    if not self.polygon:
      self.to_polygon()
    rad = _m.radians(degrees)
    c, sn = _m.cos(rad), _m.sin(rad)
    for p in self.points:
      x, y = p[0], p[1]
      p[0] = x * c - y * sn
      p[1] = x * sn + y * c

  def hit(self, wx, wy):
    if self.polygon and len(self.points) >= 3:
      return _point_in_poly(wx, wy, self.world_points())
    l, r, b, t = self.world_rect()
    return l <= wx <= r and b <= wy <= t

  def intersects_rect(self, l, r, b, t):
    ol, orr, ob, ot = self.world_rect()
    return not (orr < l or ol > r or ot < b or ob > t)

  def edge_hit(self, wx, wy, zone=RESIZE_ZONE):
    if self.polygon:
      return None
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
      "fill": list(self.fill), "edge": list(self.edge),
      "locked": bool(self.locked),
    }
    if self.layer is not None:
      d["layer"] = int(self.layer)
    if getattr(self, "id", ""):
      d["id"] = str(self.id)
    if getattr(self, "absorption", 0.5) != 0.5:
      d["absorption"] = float(self.absorption)
    if self.polygon and len(self.points) >= 3:
      d["polygon"] = True
      pts = [[int(p[0]), int(p[1])] for p in self.points]
      n = len(pts)
      area2 = sum(pts[i][0]*pts[(i+1)%n][1] - pts[(i+1)%n][0]*pts[i][1] for i in range(n))
      if area2 < 0:
        pts.reverse()
      d["points"] = pts
    else:
      d["w"] = int(self.w)
      d["h"] = int(self.h)
    return d

  def badge_screen_pos(self, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, _ = ed.to_screen(r, t)
    return x1 - 12, y0 + 12

  def draw(self, screen, ed):
    if self.polygon and len(self.points) >= 3:
      pts = [ed.to_screen(wx, wy) for wx, wy in self.world_points()]
      ipts = [(int(sx), int(sy)) for sx, sy in pts]
      pygame.draw.polygon(screen, self.fill, ipts)
      pygame.draw.polygon(screen, self.edge, ipts, PLAT_EDGE_W)
      if self.locked:
        xs = [p[0] for p in ipts]
        ys = [p[1] for p in ipts]
        bx0, by0 = min(xs), min(ys)
        bx1, by1 = max(xs), max(ys)
        w, h = bx1 - bx0, by1 - by0
        if w > 0 and h > 0:
          local = [(px - bx0, py - by0) for px, py in ipts]
          stripes = make_stripe_surface(w, h).copy()
          mask = pygame.Surface((w, h), pygame.SRCALPHA)
          pygame.draw.polygon(mask, (255, 255, 255, 255), local)
          stripes.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
          screen.blit(stripes, (bx0, by0))
      return
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, y1 = ed.to_screen(r, b)
    rect = pygame.Rect(int(min(x0, x1)), int(min(y0, y1)),
                       int(abs(x1 - x0)), int(abs(y1 - y0)))
    pygame.draw.rect(screen, self.fill, rect)
    pygame.draw.rect(screen, self.edge, rect, PLAT_EDGE_W)
    if self.locked:
      screen.blit(make_stripe_surface(rect.w, rect.h), rect.topleft)


# =========================================================
# Background
# =========================================================
class EditorBackground:
  def __init__(self, x, y, w=None, h=None):
    self.x, self.y = x, y
    if w is None or h is None:
      saved = settings.get_panel_size("background")
      if saved is not None:
        w, h = saved
      else:
        w, h = PLAT_DEFAULT_W, PLAT_DEFAULT_H
    self.w, self.h = w, h
    self.fill = BG_DEFAULT_COLOR
    self.locked = False
    self.layer = None
    self.id = ""
    self.id = ""
    self.id = ""
    # <STRANGE>#500: polygon-?????????? ????????. ?????????? ??? ???????????????????????? ???????????? (x,y).
    self.polygon = False
    self.points = []          # [[dx, dy], ...]
    self.active_points = set()

  # <STRANGE>#501: bbox ?????????????? ???? ???????????? ?? polygon-????????????
  def world_rect(self):
    if self.polygon and len(self.points) >= 1:
      xs = [p[0] for p in self.points]
      ys = [p[1] for p in self.points]
      return (self.x + min(xs), self.x + max(xs),
              self.y + min(ys), self.y + max(ys))
    return (self.x - self.w / 2, self.x + self.w / 2,
            self.y - self.h / 2, self.y + self.h / 2)

  # <STRANGE>#502: ?????????????? ???????????????????? ?????????? ????????????????
  def world_points(self):
    return [(self.x + p[0], self.y + p[1]) for p in self.points]

  # <STRANGE>#503: ???????????????????? ?????????????????????????? ?? 4-???????????????? ??????????????
  def to_polygon(self):
    if self.polygon:
      return
    l = self.x - self.w / 2
    r = self.x + self.w / 2
    b = self.y - self.h / 2
    t = self.y + self.h / 2
    self.points = [
      [int(l - self.x), int(b - self.y)],
      [int(r - self.x), int(b - self.y)],
      [int(r - self.x), int(t - self.y)],
      [int(l - self.x), int(t - self.y)],
    ]
    self.polygon = True
    self.active_points = set()

  # <STRANGE>#504: ???????????????? ?????????????? ?? ?????????????????????????? ???? bbox
  def to_rect(self):
    if not self.polygon or not self.points:
      self.polygon = False
      self.points = []
      return
    xs = [p[0] for p in self.points]
    ys = [p[1] for p in self.points]
    l, r = min(xs), max(xs)
    b, t = min(ys), max(ys)
    self.w = max(1, int(r - l))
    self.h = max(1, int(t - b))
    self.x = self.x + (l + r) / 2
    self.y = self.y + (b + t) / 2
    self.polygon = False
    self.points = []
    self.active_points = set()


  def rotate_around_center(self, degrees):
    # <STRANGE>#600: ?????????????? ???????????????????????? ????????????.
    # ?????????????????????????? ???????????????????????? ?? ?????????????? ?????? ???????????? ????????????????.
    import math as _m
    if not self.polygon:
      self.to_polygon()
    rad = _m.radians(degrees)
    c, sn = _m.cos(rad), _m.sin(rad)
    for p in self.points:
      x, y = p[0], p[1]
      p[0] = x * c - y * sn
      p[1] = x * sn + y * c
  def hit(self, wx, wy):
    if self.polygon and len(self.points) >= 3:
      return _point_in_poly(wx, wy, self.world_points())
    l, r, b, t = self.world_rect()
    return l <= wx <= r and b <= wy <= t

  def intersects_rect(self, l, r, b, t):
    ol, orr, ob, ot = self.world_rect()
    return not (orr < l or ol > r or ot < b or ob > t)

  def edge_hit(self, wx, wy, zone=RESIZE_ZONE):
    # <STRANGE>#505: ?????????????? ???? ???????????????????? ???? ???????? ??? ???????????? ???????????????????????????? ????????????
    if self.polygon:
      return None
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
      "color": list(self.fill),
      "locked": bool(self.locked),
    }
    if self.layer is not None:
      d["layer"] = int(self.layer)
    if getattr(self, "id", ""):
      d["id"] = str(self.id)
    if self.polygon and len(self.points) >= 3:
      d["polygon"] = True
      pts = [[int(p[0]), int(p[1])] for p in self.points]
      n = len(pts)
      area2 = sum(pts[i][0]*pts[(i+1)%n][1] - pts[(i+1)%n][0]*pts[i][1] for i in range(n))
      if area2 < 0:
        pts.reverse()
      d["points"] = pts
    else:
      d["w"] = int(self.w)
      d["h"] = int(self.h)
    return d

  def badge_screen_pos(self, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, _ = ed.to_screen(r, t)
    return x1 - 12, y0 + 12

  def draw(self, screen, ed):
    if self.polygon and len(self.points) >= 3:
      pts = [ed.to_screen(wx, wy) for wx, wy in self.world_points()]
      ipts = [(int(sx), int(sy)) for sx, sy in pts]
      pygame.draw.polygon(screen, self.fill, ipts)
      if self.locked:
        # <STRANGE>#565: ???????????? ?????????? ??????????, ???????????????????? ???? ????????????????
        xs = [p[0] for p in ipts]
        ys = [p[1] for p in ipts]
        x0, y0 = min(xs), min(ys)
        x1, y1 = max(xs), max(ys)
        w, h = x1 - x0, y1 - y0
        if w > 0 and h > 0:
          local = [(px - x0, py - y0) for px, py in ipts]
          stripes = make_stripe_surface(w, h).copy()
          mask = pygame.Surface((w, h), pygame.SRCALPHA)
          pygame.draw.polygon(mask, (255, 255, 255, 255), local)
          stripes.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
          screen.blit(stripes, (x0, y0))
      return
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, y1 = ed.to_screen(r, b)
    rect = pygame.Rect(int(min(x0, x1)), int(min(y0, y1)),
                       int(abs(x1 - x0)), int(abs(y1 - y0)))
    pygame.draw.rect(screen, self.fill, rect)
    if self.locked:
      screen.blit(make_stripe_surface(rect.w, rect.h), rect.topleft)


# =========================================================
# Item — delegate to game, supports recursive contents
# =========================================================

class EditorNote:
  def __init__(self, x, y, text="", title="Note"):
    self.x, self.y = x, y
    self.w, self.h = 30, 40
    self.text = str(text)
    self.title = str(title)
    self.locked = False
    self.layer = None
    self.id = ""

  def world_rect(self):
    return (self.x - self.w / 2, self.x + self.w / 2,
            self.y - self.h / 2, self.y + self.h / 2)

  def hit(self, wx, wy):
    l, r, b, t = self.world_rect()
    return l <= wx <= r and b <= wy <= t

  def intersects_rect(self, l, r, b, t):
    ol, orr, ob, ot = self.world_rect()
    return not (orr < l or ol > r or ot < b or ob > t)

  def to_json(self):
    d = {"x": int(self.x), "y": int(self.y), "type": "note",
         "title": self.title, "text": self.text}
    if self.locked: d["locked"] = True
    if self.layer is not None: d["layer"] = int(self.layer)
    if self.id: d["id"] = self.id
    return d

  def badge_screen_pos(self, ed):
    l, r, b, t = self.world_rect()
    x1, y0 = ed.to_screen(r, t)
    return x1 - 12, y0 + 12

  def draw(self, screen, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, y1 = ed.to_screen(r, b)
    rect = pygame.Rect(int(min(x0, x1)), int(min(y0, y1)),
                       int(abs(x1 - x0)), int(abs(y1 - y0)))
    pygame.draw.rect(screen, (255, 255, 255), rect)
    pygame.draw.rect(screen, (180, 180, 180), rect, 2)
    # ???????? ?????????? ????????????
    for i in range(1, 4):
      ly = y0 + i * (y1 - y0) / 5
      pygame.draw.line(screen, (180, 180, 180), (x0 + 4, ly), (x1 - 4, ly), 1)
    if self.locked:
      screen.blit(make_stripe_surface(rect.w, rect.h), rect.topleft)


class EditorItem:
  """Превью игрового предмета. Отрисовка и размеры — из игрового класса.

  Для `type == "cube"` дополнительно ведём `contents` — список взвешенных
  записей той же формы, что и у спавнера:
    [{"type": "soda", "count": 2}, {"type": "nothing", "count": 1}, ...]
  У вложенных коробок запись сама может иметь ключ "contents".
  """

  def __init__(self, x, y, item_type=DEFAULT_ITEM_TYPE, contents=None):
    self.x, self.y = x, y
    self.item_type = item_type
    self.locked = False
    self.layer = None
    self.id = ""
    self.contents = []
    if item_type == "cube" and contents:
      self.contents = [self._clean_entry(e) for e in contents]
    self._refresh()

  @staticmethod
  def _clean_entry(e):
    d = {"type": e.get("type", "nothing"),
         "count": int(e.get("count", 1))}
    if d["type"] == "cube" and e.get("contents"):
      d["contents"] = [EditorItem._clean_entry(x)
                       for x in e["contents"]]
    return d

  def _refresh(self):
    self._game = make_fake_item(self.item_type)
    if self._game is not None:
      self.w = self._game.w
      self.h = self._game.h
    else:
      self.w, self.h = 30, 30

  def set_type(self, t):
    self.item_type = t
    if t != "cube":
      self.contents = []
    self._refresh()

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
    if getattr(self, "id", ""):
      d["id"] = str(self.id)
    if self.item_type == "cube" and self.contents:
      d["contents"] = [dict(e) for e in self.contents]
    return d

  def draw(self, screen, ed):
    if self._game is None:
      l, r, b, t = self.world_rect()
      x0, y0 = ed.to_screen(l, t)
      x1, y1 = ed.to_screen(r, b)
      rect = pygame.Rect(int(min(x0, x1)), int(min(y0, y1)),
                         int(abs(x1 - x0)), int(abs(y1 - y0)))
      pygame.draw.rect(screen, (200, 180, 120), rect)
      pygame.draw.rect(screen, (80, 70, 50), rect, 2)
      if self.locked:
        screen.blit(make_stripe_surface(rect.w, rect.h), rect.topleft)
      return

    self._game.draw_at(GLAdapter(screen), ed, (self.x, self.y), 0.0, 255, 1.0)

    if self.locked:
      l, r, b, t = self.world_rect()
      x0, y0 = ed.to_screen(l, t)
      x1, y1 = ed.to_screen(r, b)
      rect = pygame.Rect(int(min(x0, x1)), int(min(y0, y1)),
                         int(abs(x1 - x0)), int(abs(y1 - y0)))
      screen.blit(make_stripe_surface(rect.w, rect.h), rect.topleft)


# =========================================================
# Spawner
# =========================================================
class EditorSpawner:
  """Точка, которая при загрузке уровня одноразово спавнит предмет."""

  def __init__(self, x, y):
    self.x, self.y = x, y
    self.r = SPAWNER_R
    self.locked = False
    self.layer = None
    self.items = []  # [{"type": str, "count": int}]

  def hit(self, wx, wy):
    return (wx - self.x) ** 2 + (wy - self.y) ** 2 <= self.r ** 2

  def intersects_rect(self, l, r, b, t):
    nx = max(l, min(self.x, r))
    ny = max(b, min(self.y, t))
    return (self.x - nx) ** 2 + (self.y - ny) ** 2 <= self.r ** 2

  def to_json(self):
    d = {
      "x": int(self.x), "y": int(self.y),
      "items": [{"type": e.get("type", "nothing"),
                 "count": int(e.get("count", 1))} for e in self.items],
    }
    if self.locked:
      d["locked"] = True
    if self.layer is not None:
      d["layer"] = int(self.layer)
    return d

  def badge_screen_pos(self, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    r = self.r * ed.zoom
    return sx + r + 2, sy - r - 2

  def draw(self, screen, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    r = max(1, int(self.r * ed.zoom))
    cx, cy = int(sx), int(sy)
    pygame.draw.circle(screen, SPAWNER_FILL, (cx, cy), r)
    edge_w = max(1, int(SPAWNER_EDGE_W * ed.zoom))
    pygame.draw.circle(screen, SPAWNER_EDGE, (cx, cy), r, edge_w)

    font_size = max(10, int(r * 1.1))
    f = pygame.font.SysFont(None, font_size, bold=True)
    surf = f.render("S", True, SPAWNER_TEXT_COLOR)
    screen.blit(surf, surf.get_rect(center=(cx, cy)))

    if self.locked:
      screen.blit(make_circle_stripe_surface(r), (cx - r, cy - r))

# =========================================================
# Bag ??? ???????????????????????? ?????????? ???????????? ????????????
# =========================================================


# =========================================================
# Artifact - special single-instance objects
# =========================================================
class EditorArtifact:
  def __init__(self, x, y, artifact_type=DEFAULT_ARTIFACT_TYPE):
    self.x, self.y = x, y
    self.artifact_type = artifact_type
    self.r = ARTIFACT_R
    self.locked = False
    self.layer = None
    self.id = ""
    self.id = ""
    self.id = ""

  def hit(self, wx, wy):
    return (wx - self.x) ** 2 + (wy - self.y) ** 2 <= self.r ** 2

  def intersects_rect(self, l, r, b, t):
    nx = max(l, min(self.x, r))
    ny = max(b, min(self.y, t))
    return (self.x - nx) ** 2 + (self.y - ny) ** 2 <= self.r ** 2

  def to_json(self):
    # <STRANGE>#1001: bag is now a dict, old [x, y] migrates on load
    d = {"x": int(self.x), "y": int(self.y)}
    if getattr(self, "id", ""):
      d["id"] = str(self.id)
    return d

  def badge_screen_pos(self, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    r = self.r * ed.zoom
    return sx + r + 2, sy - r - 2

  def draw(self, screen, ed):
    # <STRANGE>#1501: lantern has no game item class, draw manually
    if self.artifact_type == "lantern":
      sx, sy = ed.to_screen(self.x, self.y)
      r = max(4, int(self.r * ed.zoom))
      cx, cy = int(sx), int(sy)
      # barrel-style lantern icon: body + handle + glass
      body = pygame.Rect(cx - r, cy - r // 2, r * 2, int(r * 1.4))
      pygame.draw.rect(screen, (60, 50, 40), body, border_radius=2)
      pygame.draw.rect(screen, (200, 180, 100), body, 2, border_radius=2)
      glass = pygame.Rect(cx - int(r * 0.6), cy - r // 4,
                          int(r * 1.2), int(r * 0.8))
      pygame.draw.rect(screen, (255, 230, 120), glass)
      pygame.draw.rect(screen, (120, 100, 40), glass, 1)
      # handle arc on top
      pygame.draw.arc(screen, (200, 180, 100),
                      (cx - int(r * 0.5), cy - r - 2, int(r), int(r * 0.8)),
                      0, 3.14159, 2)
      if self.locked:
        surf_w = body.w; surf_h = body.h
        screen.blit(make_stripe_surface(surf_w, surf_h), body.topleft)
      return
    # <STRANGE>#740: prefer game draw_at so artifact looks exactly like in-game
    game = make_fake_item(self.artifact_type)
    if game is not None:
      try:
        game.draw_at(GLAdapter(screen), ed, (self.x, self.y), 0.0, 255, 1.0)
        if self.locked:
          sx, sy = ed.to_screen(self.x, self.y)
          r = max(1, int(self.r * ed.zoom))
          screen.blit(make_circle_stripe_surface(r),
                      (int(sx) - r, int(sy) - r))
        return
      except Exception:
        pass
    sx, sy = ed.to_screen(self.x, self.y)

# =========================================================
# Trigger - axis-aligned invisible-in-game zone
# =========================================================
class EditorTrigger:
  def __init__(self, x, y, w=None, h=None):
    self.x, self.y = x, y
    if w is None: w = TRIGGER_DEFAULT_W
    if h is None: h = TRIGGER_DEFAULT_H
    self.w, self.h = w, h
    self.id = ""
    self.script = ""
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
    if abs(wx - l) <= zone: return "left"
    if abs(wx - r) <= zone: return "right"
    if abs(wy - t) <= zone: return "top"
    if abs(wy - b) <= zone: return "bottom"
    return None

  def to_json(self):
    d = {"x": int(self.x), "y": int(self.y),
         "w": int(self.w), "h": int(self.h)}
    if self.id: d["id"] = str(self.id)
    if self.script: d["script"] = str(self.script)
    if self.locked: d["locked"] = True
    if self.layer is not None: d["layer"] = int(self.layer)
    return d

  def badge_screen_pos(self, ed):
    l, r, b, t = self.world_rect()
    x1, y0 = ed.to_screen(r, t)
    return x1 - 12, y0 + 12

  def draw(self, screen, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, y1 = ed.to_screen(r, b)
    rect = pygame.Rect(int(min(x0, x1)), int(min(y0, y1)),
                       int(abs(x1 - x0)), int(abs(y1 - y0)))
    ov = pygame.Surface((max(1, rect.w), max(1, rect.h)), pygame.SRCALPHA)
    ov.fill(TRIGGER_FILL)
    screen.blit(ov, rect.topleft)
    pygame.draw.rect(screen, TRIGGER_EDGE, rect, TRIGGER_EDGE_W)
    if self.id:
      try:
        f = pygame.font.SysFont(None, 18, bold=True)
        surf = f.render(str(self.id), True, TRIGGER_LABEL_COLOR)
        screen.blit(surf, (rect.x + 4, rect.y + 2))
      except Exception:
        pass
    if self.locked:
      screen.blit(make_stripe_surface(rect.w, rect.h), rect.topleft)

# =========================================================
# Button - kinematic grab point (id only, no script)
# =========================================================
class EditorButton:
  def __init__(self, x, y):
    self.x, self.y = x, y
    self.r = BUTTON_R
    self.id = ""
    self.locked = False
    self.layer = None

  def hit(self, wx, wy):
    return (wx - self.x) ** 2 + (wy - self.y) ** 2 <= self.r ** 2

  def intersects_rect(self, l, r, b, t):
    nx = max(l, min(self.x, r))
    ny = max(b, min(self.y, t))
    return (self.x - nx) ** 2 + (self.y - ny) ** 2 <= self.r ** 2

  def to_json(self):
    d = {"x": int(self.x), "y": int(self.y)}
    if getattr(self, "id", ""):
      d["id"] = str(self.id)
    if self.layer is not None:
      d["layer"] = int(self.layer)
    if self.locked:
      d["locked"] = True
    return d

  def badge_screen_pos(self, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    r = self.r * ed.zoom
    return sx + r + 2, sy - r - 2

  def draw(self, screen, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    r = max(1, int(self.r * ed.zoom))
    pygame.draw.circle(screen, BUTTON_FILL, (int(sx), int(sy)), r)
    edge_w = max(1, int(2 * ed.zoom))
    pygame.draw.circle(screen, BUTTON_EDGE, (int(sx), int(sy)), r, edge_w)
    if self.locked:
      screen.blit(make_circle_stripe_surface(r),
                  (int(sx) - r, int(sy) - r))

# =========================================================
# Anchor - reactive zone endpoints (A/B) and start point (S)
# =========================================================
class EditorAnchor:
  def __init__(self, x, y, variant=DEFAULT_ANCHOR_VARIANT):
    self.x, self.y = x, y
    self.variant = variant if variant in ANCHOR_VARIANTS else DEFAULT_ANCHOR_VARIANT
    self.binding = ""
    self.name = ""
    self.weight = 1
    self.max_limit = 1
    self.locked = False
    self.layer = None

  @property
  def size(self):
    return ANCHOR_SIZE

  def hit(self, wx, wy):
    h = self.size / 2
    return abs(wx - self.x) <= h and abs(wy - self.y) <= h

  def intersects_rect(self, l, r, b, t):
    h = self.size / 2
    ol, orr = self.x - h, self.x + h
    ob, ot = self.y - h, self.y + h
    return not (orr < l or ol > r or ot < b or ob > t)

  def to_json(self):
    d = {"x": int(self.x), "y": int(self.y), "variant": self.variant}
    if self.binding:
      d["binding"] = str(self.binding)
    if self.name:
      d["name"] = str(self.name)
    if int(self.weight) != 1:
      d["weight"] = int(self.weight)
    if int(self.max_limit) != 1:
      d["max_limit"] = int(self.max_limit)
    if self.locked:
      d["locked"] = True
    if self.layer is not None:
      d["layer"] = int(self.layer)
    return d

  def badge_screen_pos(self, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    h = self.size / 2 * ed.zoom
    return sx + h + 2, sy - h - 2

  def _label_text(self, ed=None):
    # <STRANGE>#1440: letter + binding; truncated to 3 chars if too long
    letter = str(getattr(self, "variant", "A"))
    bnd = str(getattr(self, "binding", ""))
    # <STRANGE>#1461: S binding is automatic - ask editor for the pair map
    if letter == "S" and not bnd and ed is not None:
      try:
        _p, _f, assigned, _zs = ed._anchor_pairs()
        bnd = assigned.get(id(self), "") or ""
      except Exception:
        bnd = ""
    return letter + bnd

  def draw(self, screen, ed):
    fills = {"A": ANCHOR_A_FILL, "B": ANCHOR_B_FILL, "S": ANCHOR_S_FILL}
    edges = {"A": ANCHOR_A_EDGE, "B": ANCHOR_B_EDGE, "S": ANCHOR_S_EDGE}
    fill = fills.get(self.variant, ANCHOR_A_FILL)
    edge = edges.get(self.variant, ANCHOR_A_EDGE)
    sx, sy = ed.to_screen(self.x, self.y)
    h = max(2, int(self.size / 2 * ed.zoom))
    rect = pygame.Rect(int(sx - h), int(sy - h), h * 2, h * 2)
    ov = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    ov.fill((fill[0], fill[1], fill[2], 140))
    screen.blit(ov, rect.topleft)
    pygame.draw.rect(screen, edge, rect, 2)
    label = self._label_text(ed)
    try:
      # <STRANGE>#1441: shrink font until it fits; else truncate to 3 chars
      fs = max(8, int(h * 1.1))
      while fs > 8:
        f = pygame.font.SysFont(None, fs, bold=True)
        ts = f.render(label, True, (255, 255, 255))
        if ts.get_width() <= rect.w - 4 and ts.get_height() <= rect.h - 4:
          break
        fs -= 1
      f = pygame.font.SysFont(None, max(8, fs), bold=True)
      txt = label
      if f.size(txt)[0] > rect.w - 4:
        txt = label[:3]
      ts = f.render(txt, True, (255, 255, 255))
      screen.blit(ts, ts.get_rect(center=rect.center))
    except Exception:
      pass
    if self.locked:
      screen.blit(make_stripe_surface(rect.w, rect.h), rect.topleft)

# =========================================================
# Light - lamp or spot light source (engine renders it in-game)
# =========================================================
class EditorLight:
  def __init__(self, x, y, kind=DEFAULT_LIGHT_TYPE):
    self.x, self.y = x, y
    self.kind = kind if kind in LIGHT_TYPES else DEFAULT_LIGHT_TYPE
    defaults = LIGHT_DEFAULTS.get(self.kind, {})
    self.color = tuple(defaults.get("color", (255, 200, 120)))
    self.intensity = float(defaults.get("intensity", 1.0))
    self.id = ""
    self.layer = None
    self.locked = False
    if self.kind == "lamp":
      self.radius = float(defaults.get("radius", 300.0))
    elif self.kind == "spot":
      self.angle = float(defaults.get("angle", 4.712389))
      self.length = float(defaults.get("length", 600.0))
      self.cone = float(defaults.get("cone", 0.8))
    elif self.kind == "sun":
      d = defaults.get("direction", (0.6, 1.0))
      self.direction = [float(d[0]), float(d[1])]

  def hit(self, wx, wy):
    return (wx - self.x) ** 2 + (wy - self.y) ** 2 <= LIGHT_GIZMO_R ** 2

  def intersects_rect(self, l, r, b, t):
    nx = max(l, min(self.x, r))
    ny = max(b, min(self.y, t))
    return (self.x - nx) ** 2 + (self.y - ny) ** 2 <= LIGHT_GIZMO_R ** 2

  def to_json(self):
    d = {"type": self.kind,
         "x": int(self.x), "y": int(self.y),
         "color": list(self.color),
         "intensity": float(self.intensity)}
    if self.kind == "lamp":
      d["radius"] = float(self.radius)
    elif self.kind == "spot":
      d["angle"] = float(self.angle)
      d["length"] = float(self.length)
      d["cone"] = float(self.cone)
    elif self.kind == "sun":
      d["direction"] = list(getattr(self, "direction", [0.6, 1.0]))
    if self.id:
      d["id"] = str(self.id)
    if self.locked:
      d["locked"] = True
    if self.layer is not None:
      d["layer"] = int(self.layer)
    return d

  def badge_screen_pos(self, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    return sx + LIGHT_GIZMO_R + 2, sy - LIGHT_GIZMO_R - 2

  def draw(self, screen, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    r = max(6, int(LIGHT_GIZMO_R * ed.zoom))
    cx, cy = int(sx), int(sy)
    # gizmo hint of light range/cone
    if self.kind == "sun":
      import math as _m
      pygame.draw.circle(screen, LIGHT_GIZMO_FILL, (cx, cy), r)
      pygame.draw.circle(screen, LIGHT_GIZMO_EDGE, (cx, cy), r, 2)
      for i in range(8):
        a = i * _m.pi / 4
        x1 = int(cx + _m.cos(a) * (r + 3))
        y1 = int(cy + _m.sin(a) * (r + 3))
        x2 = int(cx + _m.cos(a) * (r + 8))
        y2 = int(cy + _m.sin(a) * (r + 8))
        pygame.draw.line(screen, LIGHT_GIZMO_EDGE, (x1, y1), (x2, y2), 2)
      if self.locked:
        screen.blit(make_circle_stripe_surface(r), (cx - r, cy - r))
      return
    if self.kind == "lamp":
      rr = int(self.radius * ed.zoom)
      if rr > r + 2 and rr < 4000:
        ov = pygame.Surface((rr * 2, rr * 2), pygame.SRCALPHA)
        pygame.draw.circle(ov, (*self.color, 30), (rr, rr), rr)
        screen.blit(ov, (cx - rr, cy - rr))
        pygame.draw.circle(screen, LIGHT_GIZMO_EDGE, (cx, cy), rr, 1)
    else:
      L = int(self.length * ed.zoom)
      if 0 < L < 6000:
        import math as _m
        a1 = self.angle - self.cone / 2
        a2 = self.angle + self.cone / 2
        p1 = (cx + _m.cos(a1) * L, cy - _m.sin(a1) * L)
        p2 = (cx + _m.cos(a2) * L, cy - _m.sin(a2) * L)
        pts = [(cx, cy), (int(p1[0]), int(p1[1])),
               (int(p2[0]), int(p2[1]))]
        ov = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(ov, (*self.color, 30), pts)
        screen.blit(ov, (0, 0))
        pygame.draw.polygon(screen, LIGHT_GIZMO_EDGE, pts, 1)
    # center dot
    pygame.draw.circle(screen, LIGHT_GIZMO_FILL, (cx, cy), r)
    pygame.draw.circle(screen, LIGHT_GIZMO_EDGE, (cx, cy), r, 2)
    # label letter (L or S)
    try:
      f = pygame.font.SysFont(None, max(10, int(r * 1.2)), bold=True)
      _letter = "L" if self.kind == "lamp" else ("S" if self.kind == "spot" else "*")
      ts = f.render(_letter, True, (30, 20, 0))
      screen.blit(ts, ts.get_rect(center=(cx, cy)))
    except Exception:
      pass
    if self.locked:
      screen.blit(make_circle_stripe_surface(r), (cx - r, cy - r))

# =========================================================
# Label - text plate that generates a script bound to a trigger
# =========================================================
class EditorLabel:
  def __init__(self, x, y, text=""):
    self.x, self.y = x, y
    self.text = str(text) if text else "label"
    self.target_trigger_id = ""
    self.chips = []
    self.locked = False
    self.layer = None

  def _rect_world(self, zoom=1.0):
    try:
      f = pygame.font.SysFont(None, LABEL_FONT_SIZE, bold=True)
      w = max(40, f.size(self.text)[0] + LABEL_PAD * 2)
      h = max(20, f.get_height() + LABEL_PAD * 2)
    except Exception:
      w, h = 80, 20
    hw = w / 2 / max(0.01, zoom)
    hh = h / 2 / max(0.01, zoom)
    return (self.x - hw, self.x + hw, self.y - hh, self.y + hh)

  def hit(self, wx, wy):
    l, r, b, t = self._rect_world(1.0)
    return l <= wx <= r and b <= wy <= t

  def intersects_rect(self, l, r, b, t):
    ol, orr, ob, ot = self._rect_world(1.0)
    return not (orr < l or ol > r or ot < b or ob > t)

  def to_json(self):
    d = {"x": int(self.x), "y": int(self.y),
         "text": str(self.text),
         "target_trigger_id": str(self.target_trigger_id),
         "chips": [{"kind": c.get("kind", ""),
                     "params": dict(c.get("params", {}))}
                    for c in self.chips]}
    if self.locked:
      d["locked"] = True
    if self.layer is not None:
      d["layer"] = int(self.layer)
    return d

  def badge_screen_pos(self, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    return sx + 4, sy - 14

  def draw(self, screen, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    try:
      f = pygame.font.SysFont(None, max(10, int(LABEL_FONT_SIZE * ed.zoom)),
                              bold=True)
      ts = f.render(str(self.text), True, LABEL_TEXT)
      w = ts.get_width() + LABEL_PAD * 2
      h = ts.get_height() + LABEL_PAD * 2
    except Exception:
      ts = None
      w, h = 80, 20
    rect = pygame.Rect(int(sx - w / 2), int(sy - h / 2), int(w), int(h))
    ov = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    ov.fill(LABEL_BG)
    screen.blit(ov, rect.topleft)
    pygame.draw.rect(screen, LABEL_EDGE, rect, 2)
    if ts is not None:
      screen.blit(ts, ts.get_rect(center=rect.center))
    if self.locked:
      screen.blit(make_stripe_surface(rect.w, rect.h), rect.topleft)
