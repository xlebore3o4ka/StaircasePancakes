import pygame

_elapsed = 0.0
_next = 0
_active = False


# --- эффекты ---

def _flash_blue(ctx):
    ctx.flash(0.4, color=(80, 160, 255), alpha=140)

def _world_text_main(ctx):
    ctx.text("demo: new API", 0, -40, dur=2.5, size=42, color=(255, 220, 120))

def _world_text_side(ctx):
    ctx.text("world text", 200, -120, dur=2.0, size=28, color=(120, 220, 255))

def _toast_string(ctx):
    ctx.toast("string toast", dur=2.5)

def _toast_shapes(ctx):
    ctx.toast([
        {"kind": "circle", "r": 16, "color": (255, 140, 40), "line": 0},
        {"kind": "circle", "r": 22, "color": (255, 140, 40), "line": 3},
        {"kind": "text", "msg": "SHAPES", "size": 32, "x": 70, "color": (255, 200, 100)},
        {"kind": "rect", "w": 80, "h": 6, "x": -180, "color": (100, 200, 255), "line": 0},
        {"kind": "line", "x": -60, "x1": 60, "y": 0, "y1": 0, "width": 3, "color": (255, 100, 255)},
        {"kind": "polygon", "points": [(-150, 20), (-120, 40), (-180, 40)],
         "color": (120, 255, 120), "line": 0},
    ], dur=3.0, h=90)

def _toast_callback(ctx):
    def draw(surf, cx, cy, t, dur, alpha):
        import math
        pulse = 0.5 + 0.5 * math.sin(t * math.tau * 3)
        r = int(10 + 8 * pulse)
        pygame.draw.circle(surf, (255, 140, 40, alpha), (cx, cy), r, 2)
        if t > dur * 0.5:
            pygame.draw.circle(surf, (255, 60, 60, alpha), (cx, cy), 6)
    ctx.toast(draw, dur=2.5, w=200, h=200)

def _shake_sine(ctx):
    ctx.shake(0.5, 12, freq=8)

def _shake_jitter(ctx):
    ctx.shake(0.3, 20)

def _flash_red(ctx):
    ctx.flash(0.6, color=(200, 0, 0), alpha=180)


# --- таймлайн (время, функция) ---

_EVENTS = [
    (0.0, _flash_blue),        # вспышка в начале
    (0.2, _world_text_main),   # текст по центру
    (0.4, _toast_string),      # простой строковый тост
    (0.8, _world_text_side),   # второй текст сбоку
    (1.2, _toast_shapes),      # примитивы
    (1.8, _toast_callback),    # callback с пульсом
    (2.4, _shake_sine),        # синусоидальная тряска
    (3.2, _shake_jitter),      # случайный джиттер
    (4.0, _flash_red),         # финальная вспышка
]


# --- события триггера ---

def on_load(ctx):
    ctx.log("demo ready — enter the trigger to start")

def on_enter(ctx):
    global _elapsed, _next, _active
    _elapsed = 0.0
    _next = 0
    _active = True
    ctx.log("demo started")

def on_exit(ctx):
    global _active
    _active = False

def on_tick(ctx):
    global _elapsed, _next, _active
    if not _active:
        return
    _elapsed += 0.05  # on_tick = 20 Hz
    while _next < len(_EVENTS) and _elapsed >= _EVENTS[_next][0]:
        _EVENTS[_next][1](ctx)
        _next += 1
    if _next >= len(_EVENTS):
        _active = False