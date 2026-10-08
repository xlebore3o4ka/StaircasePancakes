"""Кэши и утилиты рендера: текст, полосы блокировки, замочек."""
import pygame
from .const import STRIPE_COLOR, STRIPE_STEP, STRIPE_WIDTH, GOLD

_CACHE_LIMIT = 64

_TEXT_CACHE = {}
_STRIPE_RECT_CACHE = {}
_STRIPE_CIRCLE_CACHE = {}


def render_text(font, text, color):
  """Кэшированный font.render — ключ (id(font), text, color)."""
  key = (id(font), text, color)
  surf = _TEXT_CACHE.get(key)
  if surf is None:
    surf = font.render(text, True, color)
    _TEXT_CACHE[key] = surf
  return surf


def draw_lock_badge(screen, cx, cy, size=14):
  """Значок замочка для блокированных объектов."""
  cx, cy = int(cx), int(cy)
  pygame.draw.circle(screen, (25, 28, 35), (cx, cy), size // 2 + 3)
  x = cx - size // 2
  y = cy - size // 2
  body = pygame.Rect(x, y + 4, size, size - 4)
  pygame.draw.arc(screen, GOLD, (x + 2, y - 1, size - 4, size - 1), 0, 3.14159, 2)
  pygame.draw.rect(screen, GOLD, body, border_radius=2)
  pygame.draw.rect(screen, (20, 20, 20), body, 1, border_radius=2)
  pygame.draw.circle(screen, (20, 20, 20), (cx, body.y + body.h // 2 - 1), 2)


def make_stripe_surface(w, h):
  w = max(1, int(w))
  h = max(1, int(h))
  key = (w, h)
  surf = _STRIPE_RECT_CACHE.get(key)
  if surf is not None:
    return surf
  surf = pygame.Surface((w, h), pygame.SRCALPHA)
  for offset in range(-h, w + 1, STRIPE_STEP):
    pygame.draw.line(surf, STRIPE_COLOR,
                     (offset, h), (offset + h, 0), STRIPE_WIDTH)
  if len(_STRIPE_RECT_CACHE) > _CACHE_LIMIT:
    _STRIPE_RECT_CACHE.clear()
  _STRIPE_RECT_CACHE[key] = surf
  return surf


def make_circle_stripe_surface(r):
  r = max(1, int(r))
  key = r
  surf = _STRIPE_CIRCLE_CACHE.get(key)
  if surf is not None:
    return surf
  d = r * 2
  surf = pygame.Surface((d, d), pygame.SRCALPHA)
  for offset in range(-d, d + 1, STRIPE_STEP):
    pygame.draw.line(surf, STRIPE_COLOR,
                     (offset, d), (offset + d, 0), STRIPE_WIDTH)
  mask = pygame.Surface((d, d), pygame.SRCALPHA)
  pygame.draw.circle(mask, (255, 255, 255, 255), (r, r), r)
  surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
  if len(_STRIPE_CIRCLE_CACHE) > _CACHE_LIMIT:
    _STRIPE_CIRCLE_CACHE.clear()
  _STRIPE_CIRCLE_CACHE[key] = surf
  return surf