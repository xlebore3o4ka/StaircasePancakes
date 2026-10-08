"""Объекты сцены редактора: пеги, платформы, фоны, предметы.

Предметы делегируют отрисовку и размеры игровым классам — так редактор
автоматически видит новые типы, добавленные в игру. Для инстанцирования
игрового класса используется фиктивный pymunk.Space.
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
)
from .helpers import make_stripe_surface, make_circle_stripe_surface

# игровые классы предметов — редактор тянет из них размеры и отрисовку
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
  """Инстанцирует игровой предмет в фиктивном Space и сразу выдёргивает.

  Сначала пробуем локальный реестр (быстро), потом game_make_item — так
  редактор подхватывает новые типы, даже если они ещё не прописаны в
  GAME_ITEM_CLASSES."""
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


def default_layer_for(obj):
  if isinstance(obj, EditorBackground):
    return LAYER_BG
  if isinstance(obj, EditorPlatform):
    return LAYER_PLATFORM
  if isinstance(obj, EditorPeg):
    return LAYER_PEG
  if isinstance(obj, EditorItem):
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
      "color": list(self.fill),
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
    if self.locked:
      screen.blit(make_stripe_surface(rect.w, rect.h), rect.topleft)


# =========================================================
# Item — delegate to game
# =========================================================
class EditorItem:
  """Превью игрового предмета. Отрисовка и размеры — из игрового класса."""

  def __init__(self, x, y, item_type=DEFAULT_ITEM_TYPE):
    self.x, self.y = x, y
    self.item_type = item_type
    self.locked = False
    self.layer = None
    self._refresh()

  def _refresh(self):
    self._game = make_fake_item(self.item_type)
    if self._game is not None:
      self.w = self._game.w
      self.h = self._game.h
    else:
      self.w, self.h = 30, 30

  def set_type(self, t):
    self.item_type = t
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