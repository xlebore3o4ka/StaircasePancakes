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
)
from .helpers import make_stripe_surface, make_circle_stripe_surface
from . import settings

try:
  from game.entities.item import (
    CubeItem as GameCubeItem,
    SodaItem as GameSodaItem,
    make_item as game_make_item,
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
  if isinstance(obj, EditorPeg):
    return LAYER_PEG
  if isinstance(obj, (EditorItem, EditorSpawner)):
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
    self.layer = None

  def hit(self, wx, wy):
    return (wx - self.x) ** 2 + (wy - self.y) ** 2 <= self.r ** 2

  def intersects_rect(self, l, r, b, t):
    nx = max(l, min(self.x, r))
    ny = max(b, min(self.y, t))
    return (self.x - nx) ** 2 + (self.y - ny) ** 2 <= self.r ** 2

  def to_json(self):
    return [int(self.x), int(self.y)]

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
      "w": int(self.w), "h": int(self.h),
      "fill": list(self.fill), "edge": list(self.edge),
      "locked": bool(self.locked),
    }
    if self.layer is not None:
      d["layer"] = int(self.layer)
    return d

  def badge_screen_pos(self, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, _ = ed.to_screen(r, t)
    return x1 - 12, y0 + 12

  def draw(self, screen, ed):
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
    # <STRANGE>#506: ?? JSON ?????????? ?????????????? ???????????? ???????? ?????????? >= 3
    if self.polygon and len(self.points) >= 3:
      d["polygon"] = True
      d["points"] = [[int(p[0]), int(p[1])] for p in self.points]
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

    self._game.draw_at(screen, ed, (self.x, self.y), 0.0, 255, 1.0)

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