"""<STRANGE>#1000: in-editor message store with info/warn/error levels."""
import pygame

INFO = "info"
WARN = "warn"
ERROR = "error"
DEFERRED = "deferred"

_LEVEL_ORDER = {DEFERRED: 0, INFO: 1, WARN: 2, ERROR: 3}

COL_INFO  = (80, 160, 255)
COL_WARN  = (255, 215, 0)
COL_ERROR = (230, 70, 70)
COL_DEFERRED = (160, 160, 160)


def level_color(kind):
  return {INFO: COL_INFO, WARN: COL_WARN, ERROR: COL_ERROR,
          DEFERRED: COL_DEFERRED}.get(kind, COL_WARN)


def draw_icon(screen, cx, cy, kind, r=9):
  col = level_color(kind)
  if kind == ERROR:
    pygame.draw.line(screen, col, (cx - r, cy - r), (cx + r, cy + r), 3)
    pygame.draw.line(screen, col, (cx + r, cy - r), (cx - r, cy + r), 3)
  elif kind == WARN:
    tri = [(cx, cy - r), (cx - r, cy + r), (cx + r, cy + r)]
    pygame.draw.polygon(screen, col, tri)
    pygame.draw.polygon(screen, (20, 20, 20), tri, 1)
    f = pygame.font.SysFont(None, 18, bold=True)
    s = f.render("!", True, (20, 20, 20))
    screen.blit(s, s.get_rect(center=(cx, cy + 2)))
  elif kind == DEFERRED:
    f = pygame.font.SysFont(None, 20, bold=True)
    s = f.render("#", True, col)
    screen.blit(s, s.get_rect(center=(cx, cy + 1)))
  else:
    pygame.draw.circle(screen, col, (cx, cy), r)
    f = pygame.font.SysFont(None, 18, bold=True)
    s = f.render("i", True, (255, 255, 255))
    screen.blit(s, s.get_rect(center=(cx, cy + 1)))


class Message:
  def __init__(self, key, kind, text, targets=None, ttl=None):
    self.key = key
    self.kind = kind
    self.text = text
    self.targets = list(targets) if targets else []
    self.target_idx = 0
    # <STRANGE>#1040: ttl in seconds; None = persists until cleared
    self.ttl = ttl


class MessageStore:
  def __init__(self):
    self.active = {}
    self.toasts = []
    self.blink = 0.0
    self.open = False

  def set(self, key, kind, text, targets=None, duration=4.2, ttl=None):
    prev = self.active.get(key)
    m = Message(key, kind, text, targets, ttl=ttl)
    self.active[key] = m
    if prev is None or prev.kind != kind or prev.text != text:
      self.toasts.append({"kind": kind, "text": text, "t": duration, "max": duration})

  def toast_only(self, kind, text, duration=3.0):
    # <STRANGE>#1030: ephemeral toast, does NOT enter `active` (not shown in center)
    self.toasts.append({"kind": kind, "text": text, "t": duration, "max": duration})

  def clear(self, key):
    if key in self.active:
      del self.active[key]

  def update(self, dt):
    self.blink = (self.blink + dt) % 1.0
    alive = []
    for t in self.toasts:
      t["t"] -= dt
      if t["t"] > 0:
        alive.append(t)
    self.toasts = alive
    # <STRANGE>#1041: expire messages that carry a ttl
    for k in list(self.active.keys()):
      m = self.active[k]
      if m.ttl is not None:
        m.ttl -= dt
        if m.ttl <= 0:
          del self.active[k]

  def top_level(self):
    if not self.active:
      return None
    best = None
    for m in self.active.values():
      if best is None or _LEVEL_ORDER.get(m.kind, 0) > _LEVEL_ORDER.get(best.kind, 0):
        best = m
    return best

  def count(self):
    return len(self.active)
