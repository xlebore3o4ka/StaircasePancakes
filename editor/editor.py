import json
import math
import pygame
import tkinter as tk
from tkinter import filedialog
from game.entities.player import BODY_R, ARM_R, ARM_DX, JUMP_V
from game.entities.peg import PEG_R

TOP_H = 40
BOT_H = 70
BG = (50, 55, 65)
UI_BG = (30, 33, 40)
GOLD = (255, 215, 0)
GREY = (110, 110, 110)
GREEN = (60, 220, 100)
PEG_R = 16
PLAT_DEFAULT_W = 180
PLAT_DEFAULT_H = 72
PLAT_FILL = (60, 60, 80)
PLAT_EDGE = (255, 255, 255)
PLAT_EDGE_W = 2
RESIZE_ZONE = 8
MIN_SIZE = 20
PLAYER_R = BODY_R
GHOST_ALPHA = 110
GRAVITY = 900
JUMP_H = JUMP_V * JUMP_V / (2 * GRAVITY)
ARM_ALPHA = 90
JUMP_ALPHA = 70
BG_DEFAULT_COLOR = (70, 75, 82)
GHOST_LERP = 0.15
GHOST_SNAP = 0.5
GHOST_RETURN_DELAY = 2.0


class EditorPeg:
  def __init__(self, x, y):
    self.x, self.y = x, y
    self.r = PEG_R

  def hit(self, wx, wy):
    return (wx - self.x) ** 2 + (wy - self.y) ** 2 <= self.r ** 2

  def to_json(self):
    return [int(self.x), int(self.y)]

  def draw(self, screen, ed):
    sx, sy = ed.to_screen(self.x, self.y)
    pygame.draw.circle(screen, (220, 60, 60), (int(sx), int(sy)), self.r)
    pygame.draw.circle(screen, (255, 255, 255), (int(sx), int(sy)), self.r, 4)


class EditorPlatform:
  def __init__(self, x, y, w=PLAT_DEFAULT_W, h=PLAT_DEFAULT_H):
    self.x, self.y = x, y
    self.w, self.h = w, h
    self.fill = PLAT_FILL
    self.edge = PLAT_EDGE

  def world_rect(self):
    return (self.x - self.w / 2, self.x + self.w / 2,
            self.y - self.h / 2, self.y + self.h / 2)

  def hit(self, wx, wy):
    l, r, b, t = self.world_rect()
    return l <= wx <= r and b <= wy <= t

  def edge_hit(self, wx, wy):
    # <STRANGE>#153 y up in world; top is larger y, bottom is smaller y — kept straight here
    l, r, b, t = self.world_rect()
    in_x = l - RESIZE_ZONE <= wx <= r + RESIZE_ZONE
    in_y = b - RESIZE_ZONE <= wy <= t + RESIZE_ZONE
    if not (in_x and in_y):
      return None
    if abs(wx - l) <= RESIZE_ZONE:
      return "left"
    if abs(wx - r) <= RESIZE_ZONE:
      return "right"
    if abs(wy - t) <= RESIZE_ZONE:
      return "top"
    if abs(wy - b) <= RESIZE_ZONE:
      return "bottom"
    return None

  def to_json(self):
    return {
      "x": int(self.x), "y": int(self.y),
      "w": int(self.w), "h": int(self.h),
      "fill": list(self.fill), "edge": list(self.edge),
    }

  def draw(self, screen, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, y1 = ed.to_screen(r, b)
    rect = pygame.Rect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))
    pygame.draw.rect(screen, self.fill, rect)
    pygame.draw.rect(screen, self.edge, rect, PLAT_EDGE_W)


class EditorBackground:
  def __init__(self, x, y, w=PLAT_DEFAULT_W, h=PLAT_DEFAULT_H):
    self.x, self.y = x, y
    self.w, self.h = w, h
    self.fill = BG_DEFAULT_COLOR

  def world_rect(self):
    return (self.x - self.w / 2, self.x + self.w / 2,
            self.y - self.h / 2, self.y + self.h / 2)

  def hit(self, wx, wy):
    l, r, b, t = self.world_rect()
    return l <= wx <= r and b <= wy <= t

  def edge_hit(self, wx, wy):
    l, r, b, t = self.world_rect()
    in_x = l - RESIZE_ZONE <= wx <= r + RESIZE_ZONE
    in_y = b - RESIZE_ZONE <= wy <= t + RESIZE_ZONE
    if not (in_x and in_y):
      return None
    if abs(wx - l) <= RESIZE_ZONE:
      return "left"
    if abs(wx - r) <= RESIZE_ZONE:
      return "right"
    if abs(wy - t) <= RESIZE_ZONE:
      return "top"
    if abs(wy - b) <= RESIZE_ZONE:
      return "bottom"
    return None

  def to_json(self):
    return {
      "x": int(self.x), "y": int(self.y),
      "w": int(self.w), "h": int(self.h),
      "color": list(self.fill),
    }

  def draw(self, screen, ed):
    l, r, b, t = self.world_rect()
    x0, y0 = ed.to_screen(l, t)
    x1, y1 = ed.to_screen(r, b)
    rect = pygame.Rect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))
    pygame.draw.rect(screen, self.fill, rect)


class Editor:
  def __init__(self):
    pygame.init()
    self.screen = pygame.display.set_mode((1280, 800))
    pygame.display.set_caption("level editor")
    self.clock = pygame.time.Clock()
    self.font = pygame.font.SysFont(None, 22)
    self.running = True
    self.tool = "peg"
    self.objects = []
    self.selected = None
    self.drag = None
    self.cam_x = 0
    self.cam_y = 0
    # <STRANGE>#222 ghost and its walk target; target resets to spawn whenever tool leaves "ghost"
    self.ghost = [0.0, float(BODY_R)]
    self.ghost_target = [0.0, float(BODY_R)]
    self.panning = False
    self.pan_last = (0, 0)
    self.cursor = None
    # <STRANGE>#230 idle timer counts up while ghost not dragged and tool != "ghost"; past delay target snaps back to spawn
    self.ghost_idle = 0.0

  def set_tool(self, name):
    # <STRANGE>#233 reset idle on any tool change so the return timer starts fresh from the switch moment
    self.ghost_idle = 0.0
    self.tool = name

  def to_screen(self, wx, wy):
    sw, sh = self.screen.get_size()
    return wx - self.cam_x + sw / 2, sh / 2 - (wy - self.cam_y)

  def from_screen(self, sx, sy):
    sw, sh = self.screen.get_size()
    return sx - sw / 2 + self.cam_x, sh / 2 - sy + self.cam_y

  def run(self):
    while self.running:
      for e in pygame.event.get():
        self.handle_event(e)
      self.update_cursor()
      self.update_ghost()
      self.draw()
      pygame.display.flip()
      self.clock.tick(60)
    pygame.quit()

  def update_ghost(self):
    # <STRANGE>#231 auto-return only when tool is not ghost; while ghost tool is active, ghost stays where placed
    dragging = self.drag is not None and self.drag[0] == "ghost"
    if dragging:
      self.ghost_idle = 0.0
    elif self.tool == "ghost":
      self.ghost_idle = 0.0
    else:
      self.ghost_idle += 1 / 60
      if self.ghost_idle >= GHOST_RETURN_DELAY:
        self.ghost_target = [0.0, float(BODY_R)]
    # <STRANGE>#226 exponential approach to target; snap when close to avoid infinite tail
    gx, gy = self.ghost
    tx, ty = self.ghost_target
    dx, dy = tx - gx, ty - gy
    if abs(dx) < GHOST_SNAP and abs(dy) < GHOST_SNAP:
      self.ghost[0], self.ghost[1] = tx, ty
    else:
      self.ghost[0] += dx * GHOST_LERP
      self.ghost[1] += dy * GHOST_LERP

  def handle_event(self, e):
    if e.type == pygame.QUIT:
      self.running = False
    elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
      self.running = False
    elif e.type == pygame.KEYDOWN and e.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
      if self.selected is not None:
        self.objects.remove(self.selected)
        self.selected = None
    elif e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
      self.cam_x, self.cam_y = self.ghost[0], self.ghost[1]
    elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 2:
      self.panning = True
      self.pan_last = e.pos
    elif e.type == pygame.MOUSEBUTTONUP and e.button == 2:
      self.panning = False
    elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
      self.on_mouse_down(e.pos)
    elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
      # <STRANGE>#203 clamp to MIN_SIZE on release so a stray click doesn't leave a 1x1 platform
      if self.drag is not None and self.drag[0] == "create" and self.selected is not None:
        if self.selected.w < MIN_SIZE:
          self.selected.w = MIN_SIZE
        if self.selected.h < MIN_SIZE:
          self.selected.h = MIN_SIZE
      self.drag = None
    elif e.type == pygame.MOUSEMOTION:
      if self.panning:
        dx = e.pos[0] - self.pan_last[0]
        dy = e.pos[1] - self.pan_last[1]
        # <STRANGE>#154 camera moves with cursor drag: cursor goes right, world follows, so cam decreases in x; y flips
        self.cam_x -= dx
        self.cam_y += dy
        self.pan_last = e.pos
      elif self.drag is not None:
        self.on_mouse_move(self.from_screen(*e.pos))

  def on_mouse_down(self, pos):
    x, y = pos
    sh = self.screen.get_height()
    if y < TOP_H:
      if self.btn_save_rect().collidepoint(pos):
        self.save()
      elif self.btn_load_rect().collidepoint(pos):
        self.load()
      return
    if y >= sh - BOT_H:
      if self.tab_ghost_rect().collidepoint(pos):
        self.set_tool("ghost")
      elif self.tab_peg_rect().collidepoint(pos):
        self.set_tool("peg")
      elif self.tab_plat_rect().collidepoint(pos):
        self.set_tool("platform")
      elif self.tab_bg_rect().collidepoint(pos):
        self.set_tool("background")
      return

    wx, wy = self.from_screen(x, y)

    if isinstance(self.selected, (EditorPlatform, EditorBackground)):
      edge = self.selected.edge_hit(wx, wy)
      if edge:
        self.drag = ("resize", edge)
        return

    hit = None
    for obj in reversed(self.objects):
      if obj.hit(wx, wy):
        hit = obj
        break
    if hit is not None:
      self.selected = hit
      self.drag = ("move", (wx - hit.x, wy - hit.y))
      return

    # <STRANGE>#227 ghost hit-test after objects so a peg on the ghost still wins; drag locks the ghost
    gx, gy = self.ghost
    if (wx - gx) ** 2 + (wy - gy) ** 2 <= PLAYER_R ** 2:
      self.drag = ("ghost", (wx - gx, wy - gy))
      return
    if self.tool == "ghost":
      self.ghost_target = [wx, wy]
      return

    if self.tool == "peg":
      obj = EditorPeg(wx, wy)
      self.objects.append(obj)
      self.selected = obj
      self.drag = ("move", (0, 0))
    else:
      # <STRANGE>#202 platform/background start 1x1 at click point, grow by drag; released size becomes final
      if self.tool == "background":
        obj = EditorBackground(wx, wy, 1, 1)
      else:
        obj = EditorPlatform(wx, wy, 1, 1)
      self.objects.append(obj)
      self.selected = obj
      self.drag = ("create", (wx, wy))

  def on_mouse_move(self, world):
    wx, wy = world
    if self.drag is None:
      return
    mode, data = self.drag
    if mode == "move":
      dx, dy = data
      self.selected.x = wx - dx
      self.selected.y = wy - dy
    elif mode == "ghost":
      dx, dy = data
      self.ghost[0] = wx - dx
      self.ghost[1] = wy - dy
      self.ghost_target = [self.ghost[0], self.ghost[1]]
    elif mode == "create":
      ox, oy = data
      l = min(ox, wx); r = max(ox, wx)
      b = min(oy, wy); t = max(oy, wy)
      obj = self.selected
      obj.w = max(r - l, 1)
      obj.h = max(t - b, 1)
      obj.x = (l + r) / 2
      obj.y = (b + t) / 2
    elif mode == "resize":
      obj = self.selected
      l, r, b, t = obj.world_rect()
      e = data
      if e == "left":
        nl = min(wx, r - MIN_SIZE)
        obj.w = r - nl
        obj.x = nl + obj.w / 2
      elif e == "right":
        nr = max(wx, l + MIN_SIZE)
        obj.w = nr - l
        obj.x = l + obj.w / 2
      elif e == "top":
        nt = max(wy, b + MIN_SIZE)
        obj.h = nt - b
        obj.y = b + obj.h / 2
      elif e == "bottom":
        nb = min(wy, t - MIN_SIZE)
        obj.h = t - nb
        obj.y = nb + obj.h / 2

  def update_cursor(self):
    want = pygame.SYSTEM_CURSOR_ARROW
    if isinstance(self.selected, (EditorPlatform, EditorBackground)):
      mx, my = pygame.mouse.get_pos()
      wx, wy = self.from_screen(mx, my)
      edge = self.selected.edge_hit(wx, wy)
      if edge in ("left", "right"):
        want = pygame.SYSTEM_CURSOR_SIZEWE
      elif edge in ("top", "bottom"):
        want = pygame.SYSTEM_CURSOR_SIZENS
    if want != self.cursor:
      pygame.mouse.set_cursor(want)
      self.cursor = want

  def draw(self):
    self.screen.fill(BG)
    # <STRANGE>#201 backgrounds first, then floor line, then ghost, then everything else so ghost always reads above bgs
    for obj in self.objects:
      if isinstance(obj, EditorBackground):
        obj.draw(self.screen, self)
    self.draw_floor_line()
    self.draw_ghost()
    for obj in self.objects:
      if not isinstance(obj, EditorBackground):
        obj.draw(self.screen, self)
    if self.selected is not None:
      sx, sy = self.to_screen(self.selected.x, self.selected.y)
      pygame.draw.circle(self.screen, GREEN, (int(sx), int(sy)), 6)
    self.draw_top_bar()
    self.draw_bottom_bar()

  def draw_floor_line(self):
    _, y = self.to_screen(0, 0)
    surf = pygame.Surface((self.screen.get_width(), 2), pygame.SRCALPHA)
    surf.fill((255, 255, 255, 90))
    self.screen.blit(surf, (0, y - 1))

  def draw_ghost(self):
    gx, gy = self.ghost
    sx, sy = self.to_screen(gx, gy)
    self.draw_ghost_line(sx, sy)
    self.draw_ghost_arm(sx, sy, -ARM_DX)
    self.draw_ghost_arm(sx, sy, ARM_DX)
    surf = pygame.Surface((PLAYER_R * 2, PLAYER_R * 2), pygame.SRCALPHA)
    pygame.draw.circle(surf, (255, 255, 255, GHOST_ALPHA), (PLAYER_R, PLAYER_R), PLAYER_R)
    self.screen.blit(surf, (sx - PLAYER_R, sy - PLAYER_R))

  def draw_ghost_line(self, sx, sy):
    ex, ey = self.to_screen(self.ghost[0], self.ghost[1] + JUMP_H)
    surf = pygame.Surface((2, int(sy - ey)), pygame.SRCALPHA)
    surf.fill((255, 255, 255, JUMP_ALPHA))
    self.screen.blit(surf, (int(sx) - 1, int(ey)))
    # <STRANGE>#209 small cap so the line reads as an arc marker, not a wall
    cap = pygame.Surface((10, 2), pygame.SRCALPHA)
    cap.fill((255, 255, 255, JUMP_ALPHA))
    self.screen.blit(cap, (int(sx) - 5, int(ey) - 1))

  def draw_ghost_arm(self, sx, sy, dx):
    ax = sx + dx
    size = ARM_R * 2 + 4
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(surf, (255, 255, 255, ARM_ALPHA), (size // 2, size // 2), ARM_R)
    self.screen.blit(surf, (ax - size // 2, sy - size // 2))

  def draw_top_bar(self):
    pygame.draw.rect(self.screen, UI_BG, (0, 0, self.screen.get_width(), TOP_H))
    self.draw_button(self.btn_save_rect(), "Save")
    self.draw_button(self.btn_load_rect(), "Load")

  def draw_bottom_bar(self):
    h = self.screen.get_height()
    pygame.draw.rect(self.screen, UI_BG, (0, h - BOT_H, self.screen.get_width(), BOT_H))
    self.draw_tab(self.tab_ghost_rect(), "ghost", self.tool == "ghost")
    self.draw_tab(self.tab_peg_rect(), "peg", self.tool == "peg")
    self.draw_tab(self.tab_plat_rect(), "platform", self.tool == "platform")
    self.draw_tab(self.tab_bg_rect(), "background", self.tool == "background")

  def draw_button(self, r, text):
    pygame.draw.rect(self.screen, (70, 75, 85), r)
    pygame.draw.rect(self.screen, GREY, r, 2)
    surf = self.font.render(text, True, (230, 230, 230))
    self.screen.blit(surf, surf.get_rect(center=r.center))

  def draw_tab(self, r, name, active):
    pygame.draw.rect(self.screen, (45, 50, 60), r)
    color = GOLD if active else GREY
    pygame.draw.rect(self.screen, color, r, 3 if active else 2)
    cx, cy = r.center
    if name == "peg":
      pygame.draw.circle(self.screen, (220, 60, 60), (cx, cy), PEG_R)
      pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), PEG_R, 4)
    elif name == "background":
      rr = pygame.Rect(0, 0, 100, 40)
      rr.center = r.center
      pygame.draw.rect(self.screen, BG_DEFAULT_COLOR, rr)
    elif name == "ghost":
      # <STRANGE>#228 mini-ghost: body + two arms, same layout as world ghost so the icon reads as the player
      ar = max(4, ARM_R // 2)
      br = max(6, PLAYER_R // 2)
      pygame.draw.circle(self.screen, (255, 255, 255), (cx - br - ar - 1, cy), ar)
      pygame.draw.circle(self.screen, (255, 255, 255), (cx + br + ar + 1, cy), ar)
      pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), br)
    else:
      rr = pygame.Rect(0, 0, 100, 40)
      rr.center = r.center
      pygame.draw.rect(self.screen, PLAT_FILL, rr)
      pygame.draw.rect(self.screen, PLAT_EDGE, rr, PLAT_EDGE_W)

  def btn_save_rect(self):
    return pygame.Rect(10, 6, 100, TOP_H - 12)

  def btn_load_rect(self):
    return pygame.Rect(120, 6, 100, TOP_H - 12)

  def tab_ghost_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(10, h - BOT_H + 6, 120, BOT_H - 12)

  def tab_peg_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(140, h - BOT_H + 6, 120, BOT_H - 12)

  def tab_plat_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(270, h - BOT_H + 6, 120, BOT_H - 12)

  def tab_bg_rect(self):
    h = self.screen.get_height()
    return pygame.Rect(400, h - BOT_H + 6, 120, BOT_H - 12)

  def save(self):
    root = tk.Tk()
    root.withdraw()
    path = filedialog.asksaveasfilename(
      defaultextension=".json",
      initialdir="levels",
      filetypes=[("JSON", "*.json")],
    )
    root.destroy()
    if not path:
      return
    pegs = [o.to_json() for o in self.objects if isinstance(o, EditorPeg)]
    platforms = [o.to_json() for o in self.objects if isinstance(o, EditorPlatform)]
    backgrounds = [o.to_json() for o in self.objects if isinstance(o, EditorBackground)]
    with open(path, "w") as f:
      json.dump({"pegs": pegs, "platforms": platforms, "backgrounds": backgrounds}, f, indent=2)

  def load(self):
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(
      initialdir="levels",
      filetypes=[("JSON", "*.json")],
    )
    root.destroy()
    if not path:
      return
    data = json.load(open(path))
    self.objects = []
    for p in data.get("pegs", []):
      self.objects.append(EditorPeg(p[0], p[1]))
    for pd in data.get("platforms", []):
      obj = EditorPlatform(pd["x"], pd["y"], pd.get("w", PLAT_DEFAULT_W), pd.get("h", PLAT_DEFAULT_H))
      obj.fill = tuple(pd.get("fill", PLAT_FILL))
      obj.edge = tuple(pd.get("edge", PLAT_EDGE))
      self.objects.append(obj)
    for bd in data.get("backgrounds", []):
      obj = EditorBackground(bd["x"], bd["y"], bd.get("w", PLAT_DEFAULT_W), bd.get("h", PLAT_DEFAULT_H))
      obj.fill = tuple(bd.get("color", BG_DEFAULT_COLOR))
      self.objects.append(obj)
    self.selected = None
