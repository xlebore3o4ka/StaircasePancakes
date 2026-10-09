"""РћР±СЉРµРєС‚С‹ СЃС†РµРЅС‹ СЂРµРґР°РєС‚РѕСЂР°. РђРІС‚РѕРЅРѕРјРЅС‹ РѕС‚ РёРіСЂС‹, СЂРёСЃСѓСЋС‚СЃСЏ С‡РµСЂРµР· raylib."""
import math
from raylib import (
  DrawRectangle, DrawRectangleLines, DrawCircle, DrawCircleLines,
  DrawLine,
)
from .const import (
  PEG_R, PEG_FILL, PEG_EDGE,
  PLAT_FILL, PLAT_EDGE, PLAT_EDGE_W,
  PLAT_DEFAULT_W, PLAT_DEFAULT_H,
  RESIZE_ZONE, BG_DEFAULT_COLOR,
  LAYER_BG, LAYER_PLATFORM, LAYER_PEG, LAYER_ITEM,
  DEFAULT_ITEM_TYPE,
  SPAWNER_R, SPAWNER_FILL, SPAWNER_EDGE,
  SPAWNER_TEXT_COLOR,
  CUBE_FILL, CUBE_EDGE, CUBE_EDGE_W,
  SODA_W, SODA_H, SODA_BLUE, SODA_WHITE,
)
from .helpers import (
  C, draw_stripes, draw_circle_stripes, draw_text, text_width,
)


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


class EditorPeg:
  def __init__(self, x, y):
    self.x, self.y = x, y
    self.r = PEG_R
    self.locked = False
    self.layer = None

  def hit(self, wx, wy):
    return (wx - self.x) ** 2 + (wy - self.y) ** 2 <= self.r ** 2

  def intersects_rect(self, l, r, b, t):
    nx = max(l, min(self.x, r)); ny = max(b, min(self.y, t))
    return (self.x - nx) ** 2 + (self.y - ny) ** 2 <= self.r ** 2

  def to_json(self):
    return [int(self.x), int(self.y)]

  def badge_screen_pos(self, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    r = self.r * ed.zoom
    return sx + r + 2, sy - r - 2

  def draw(self, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    sx, sy = int(sx), int(sy)
    r = max(1, int(self.r * ed.zoom))
    DrawCircle(sx, sy, r, C(PEG_FILL))
    DrawCircleLines(sx, sy, r, C(PEG_EDGE))
    if r >= 3:
      DrawCircleLines(sx, sy, r - 1, C(PEG_EDGE))
    if self.locked:
      draw_circle_stripes(sx, sy, r)


class EditorPlatform:
  def __init__(self, x, y, w=PLAT_DEFAULT_W, h=PLAT_DEFAULT_H):
    self.x, self.y = x, y
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
    if not (l - zone <= wx <= r + zone and b - zone <= wy <= t + zone):
      return None
    if abs(wx - l) <= zone: return "left"
    if abs(wx - r) <= zone: return "right"
    if abs(wy - t) <= zone: return "top"
    if abs(wy - b) <= zone: return "bottom"
    return None

  def to_json(self):
    d = {"x": int(self.x), "y": int(self.y),
         "w": int(self.w), "h": int(self.h),
         "fill": list(self.fill), "edge": list(self.edge),
         "locked": bool(self.locked)}
    if self.layer is not None:
      d["layer"] = int(self.layer)
    return d

  def badge_screen_pos(self, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, _ = ed.to_screen(r, t)
    return x1 - 12, y0 + 12

  def draw(self, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, y1 = ed.to_screen(r, b)
    rx = int(min(x0, x1)); ry = int(min(y0, y1))
    rw = int(abs(x1 - x0)); rh = int(abs(y1 - y0))
    DrawRectangle(rx, ry, rw, rh, C(self.fill))
    # СЂР°РјРєР° РґРІРѕР№РЅРѕР№ С‚РѕР»С‰РёРЅС‹
    for k in range(PLAT_EDGE_W):
      DrawRectangleLines(rx - k, ry - k, rw + k * 2, rh + k * 2, C(self.edge))
    if self.locked:
      draw_stripes(rx, ry, rw, rh)


class EditorBackground:
  def __init__(self, x, y, w=PLAT_DEFAULT_W, h=PLAT_DEFAULT_H):
    self.x, self.y = x, y
    self.w, self.h = w, h
    self.fill = BG_DEFAULT_COLOR
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
    if not (l - zone <= wx <= r + zone and b - zone <= wy <= t + zone):
      return None
    if abs(wx - l) <= zone: return "left"
    if abs(wx - r) <= zone: return "right"
    if abs(wy - t) <= zone: return "top"
    if abs(wy - b) <= zone: return "bottom"
    return None

  def to_json(self):
    d = {"x": int(self.x), "y": int(self.y),
         "w": int(self.w), "h": int(self.h),
         "color": list(self.fill), "locked": bool(self.locked)}
    if self.layer is not None:
      d["layer"] = int(self.layer)
    return d

  def badge_screen_pos(self, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, _ = ed.to_screen(r, t)
    return x1 - 12, y0 + 12

  def draw(self, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, y1 = ed.to_screen(r, b)
    rx = int(min(x0, x1)); ry = int(min(y0, y1))
    rw = int(abs(x1 - x0)); rh = int(abs(y1 - y0))
    DrawRectangle(rx, ry, rw, rh, C(self.fill))
    if self.locked:
      draw_stripes(rx, ry, rw, rh)


class EditorItem:
  SIZE_MAP = {"cube": (30, 30), "soda": (SODA_W, SODA_H)}
  DEFAULT_SIZE = (30, 30)

  def __init__(self, x, y, item_type=DEFAULT_ITEM_TYPE, contents=None):
    self.x, self.y = x, y
    self.item_type = item_type
    self.locked = False
    self.layer = None
    self.contents = []
    if item_type == "cube" and contents:
      self.contents = [self._clean_entry(e) for e in contents]
    self.w, self.h = self.SIZE_MAP.get(item_type, self.DEFAULT_SIZE)

  @staticmethod
  def _clean_entry(e):
    d = {"type": e.get("type", "nothing"),
         "count": int(e.get("count", 1))}
    if d["type"] == "cube" and e.get("contents"):
      d["contents"] = [EditorItem._clean_entry(x) for x in e["contents"]]
    return d

  def set_type(self, t):
    self.item_type = t
    if t != "cube":
      self.contents = []
    self.w, self.h = self.SIZE_MAP.get(t, self.DEFAULT_SIZE)

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
    d = {"x": int(self.x), "y": int(self.y),
         "type": self.item_type,
         "locked": bool(self.locked)}
    if self.layer is not None:
      d["layer"] = int(self.layer)
    if self.item_type == "cube" and self.contents:
      d["contents"] = [dict(e) for e in self.contents]
    return d

  def draw(self, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, y1 = ed.to_screen(r, b)
    rx = int(min(x0, x1)); ry = int(min(y0, y1))
    rw = int(abs(x1 - x0)); rh = int(abs(y1 - y0))

    if self.item_type == "cube":
      DrawRectangle(rx, ry, rw, rh, C(CUBE_FILL))
      DrawRectangleLines(rx, ry, rw, rh, C(CUBE_EDGE))
    elif self.item_type == "soda":
      q = max(1, rh // 4)
      DrawRectangle(rx, ry, rw, q, C(SODA_BLUE))
      DrawRectangle(rx, ry + q, rw, rh - 2 * q, C(SODA_WHITE))
      DrawRectangle(rx, ry + q + (rh - 2 * q), rw, q, C(SODA_BLUE))
      DrawRectangleLines(rx, ry, rw, rh, (20, 20, 20, 255))
    else:
      DrawRectangle(rx, ry, rw, rh, (200, 180, 120, 255))
      DrawRectangleLines(rx, ry, rw, rh, (80, 70, 50, 255))

    if self.locked:
      draw_stripes(rx, ry, rw, rh)


class EditorSpawner:
  def __init__(self, x, y):
    self.x, self.y = x, y
    self.r = SPAWNER_R
    self.locked = False
    self.layer = None
    self.items = []

  def hit(self, wx, wy):
    return (wx - self.x) ** 2 + (wy - self.y) ** 2 <= self.r ** 2

  def intersects_rect(self, l, r, b, t):
    nx = max(l, min(self.x, r)); ny = max(b, min(self.y, t))
    return (self.x - nx) ** 2 + (self.y - ny) ** 2 <= self.r ** 2

  def to_json(self):
    d = {"x": int(self.x), "y": int(self.y),
         "items": [{"type": e.get("type", "nothing"),
                    "count": int(e.get("count", 1))} for e in self.items]}
    if self.locked:
      d["locked"] = True
    if self.layer is not None:
      d["layer"] = int(self.layer)
    return d

  def badge_screen_pos(self, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    r = self.r * ed.zoom
    return sx + r + 2, sy - r - 2

  def draw(self, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    sx, sy = int(sx), int(sy)
    r = max(1, int(self.r * ed.zoom))
    DrawCircle(sx, sy, r, C(SPAWNER_FILL))
    DrawCircleLines(sx, sy, r, C(SPAWNER_EDGE))
    if r >= 2:
      DrawCircleLines(sx, sy, r - 1, C(SPAWNER_EDGE))

    fsize = max(10, int(r * 1.2))
    tw = text_width("S", fsize)
    draw_text("S", sx - tw // 2, sy - fsize // 2 + 1, fsize, C(SPAWNER_TEXT_COLOR))

    if self.locked:
      draw_circle_stripes(sx, sy, r)