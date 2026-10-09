"""РЈС‚РёР»РёС‚С‹ СЂРµРЅРґРµСЂР°: С†РІРµС‚Р°, С‚РµРєСЃС‚, РґРµРєРѕСЂР°С‚РёРІРЅС‹Рµ РѕРІРµСЂР»РµРё."""
from raylib import (
  DrawText, MeasureText, DrawCircle, DrawCircleLines,
  DrawRectangle, DrawRectangleLines, DrawLine,
  BeginScissorMode, EndScissorMode,
)
from .const import STRIPE_COLOR, STRIPE_STEP, STRIPE_WIDTH, GOLD


def C(rgb):
  """(r,g,b) РёР»Рё (r,g,b,a) -> РєРѕСЂС‚РµР¶ РёР· 4 int."""
  if len(rgb) == 4:
    return (int(rgb[0]), int(rgb[1]), int(rgb[2]), int(rgb[3]))
  return (int(rgb[0]), int(rgb[1]), int(rgb[2]), 255)


def draw_text(text, x, y, size, color):
  DrawText(str(text).encode('utf-8'), int(x), int(y), int(size), color)


def text_width(text, size):
  return MeasureText(str(text).encode('utf-8'), int(size))


def draw_lock_badge(cx, cy, size=14):
  cx, cy = int(cx), int(cy)
  DrawCircle(cx, cy, size // 2 + 3, (25, 28, 35, 255))
  x = cx - size // 2
  y = cy - size // 2
  body_w = size
  body_h = size - 4
  body_y = y + 4
  DrawCircleLines(cx, body_y - 2, body_w // 3, C(GOLD))
  DrawRectangle(x, body_y, body_w, body_h, C(GOLD))
  DrawRectangleLines(x, body_y, body_w, body_h, (20, 20, 20, 255))
  DrawCircle(cx, body_y + body_h // 2 - 1, 2, (20, 20, 20, 255))


def draw_stripes(x, y, w, h):
  x, y, w, h = int(x), int(y), int(w), int(h)
  if w <= 0 or h <= 0:
    return
  BeginScissorMode(x, y, w, h)
  col = (int(STRIPE_COLOR[0]), int(STRIPE_COLOR[1]),
         int(STRIPE_COLOR[2]), int(STRIPE_COLOR[3]))
  for offset in range(-h, w + 1, STRIPE_STEP):
    for k in range(STRIPE_WIDTH):
      DrawLine(x + offset + k, y + h, x + offset + h + k, y, col)
  EndScissorMode()


def draw_circle_stripes(cx, cy, r):
  cx, cy, r = int(cx), int(cy), int(r)
  if r <= 0:
    return
  d = r * 2
  x, y = cx - r, cy - r
  BeginScissorMode(x, y, d, d)
  col = (int(STRIPE_COLOR[0]), int(STRIPE_COLOR[1]),
         int(STRIPE_COLOR[2]), int(STRIPE_COLOR[3]))
  for offset in range(-d, d + 1, STRIPE_STEP):
    for k in range(STRIPE_WIDTH):
      DrawLine(x + offset + k, cy + r, x + offset + d + k, cy - r, col)
  EndScissorMode()