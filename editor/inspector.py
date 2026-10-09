"""Инспектор-панель. Поддерживает стек вложенных панелей."""
import math
import pygame

from .const import (
  INSPECTOR_W, INSPECTOR_HEADER_H, INSPECTOR_PAD, INSPECTOR_ROW_H,
  INSPECTOR_ENTRY_ROW_H, INSPECTOR_ANIM_SPEED, INSPECTOR_STACK_STEP,
  INSPECTOR_GEAR_W,
  INSPECTOR_BG, INSPECTOR_HEADER_BG, INSPECTOR_BORDER,
  INSPECTOR_TITLE, INSPECTOR_LABEL, INSPECTOR_SECTION, INSPECTOR_HINT,
  INSPECTOR_ROW_BG, INSPECTOR_ROW_HOVER, INSPECTOR_ROW_EDGE,
  INSPECTOR_BTN_BG, INSPECTOR_BTN_HOVER, INSPECTOR_BTN_TEXT,
  INSPECTOR_BTN_BORDER, INSPECTOR_DANGER, INSPECTOR_DANGER_HOVER,
  INSPECTOR_GEAR_BG, INSPECTOR_GEAR_HOVER, INSPECTOR_GEAR_TEXT,
  INSPECTOR_INPUT_BG, INSPECTOR_INPUT_EDGE, INSPECTOR_INPUT_EDGE_FOCUS,
  INSPECTOR_INPUT_TEXT,
  SPAWNER_ENTRY_TYPES, BOT_H,
)


def _find_entry_list(owner):
  """owner: EditorSpawner | dict-запись с 'contents' | EditorItem(cube)."""
  if owner is None:
    return None
  if isinstance(owner, dict):
    if owner.get("type") == "cube":
      if "contents" not in owner:
        owner["contents"] = []
      return owner["contents"]
    return None
  if hasattr(owner, "items"):
    return owner.items
  if getattr(owner, "item_type", None) == "cube":
    return owner.contents
  return None


def _is_world_obj(owner):
  return owner is not None and not isinstance(owner, dict)


class InspectorPanel:
  def __init__(self, editor, owner, depth=0):
    self.editor = editor
    self.owner = owner
    self.depth = depth

    self.font = pygame.font.SysFont(None, 20)
    self.font_small = pygame.font.SysFont(None, 18)
    self.font_title = pygame.font.SysFont(None, 22, bold=True)

    self._last = owner
    self.t = 0.0

    self.count_text = {}
    self.focused_entry = None
    self.cursor_blink = 0.0

    self.hover_key = None
    self.hover_entry = None

  # ---------- lifecycle ----------
  def set_owner(self, owner):
    if owner is self.owner:
      return
    if owner is not None:
      self._last = owner
    self.owner = owner
    self.count_text.clear()
    self.focused_entry = None

  def _view(self):
    return self.owner if self.owner is not None else self._last

  def is_visible(self):
    return self.t > 0.001

  def wants_keyboard(self):
    return self.owner is not None and self.focused_entry is not None

  def update(self, dt):
    self.cursor_blink = (self.cursor_blink + dt) % 1.0
    goal = 1.0 if self.owner is not None else 0.0
    step = INSPECTOR_ANIM_SPEED * dt
    if self.t < goal:
      self.t = min(goal, self.t + step)
    elif self.t > goal:
      self.t = max(goal, self.t - step)

  # ---------- geometry ----------
  def _full_rect(self):
    sw, sh = self.editor.screen.get_size()
    top = self.editor.panel.height()
    x = sw - INSPECTOR_W - self.depth * INSPECTOR_STACK_STEP
    return pygame.Rect(x, top, INSPECTOR_W, sh - top - BOT_H)

  def _visible_rect(self):
    fr = self._full_rect()
    offset = int(INSPECTOR_W * (1.0 - self.t))
    return pygame.Rect(fr.x + offset, fr.y,
                       INSPECTOR_W - offset, fr.h)

  # ---------- positions (единый источник истины) ----------
  def _row_positions(self, fr):
    """Возвращает dict с y координатами строк. Работает одинаково для
    layout и draw, поэтому клики совпадают с картинкой."""
    view = self._view()
    if view is None:
      return None

    positions = {}
    pad = INSPECTOR_PAD
    y = fr.y + 8
    positions["close_y"] = y

    y += INSPECTOR_HEADER_H
    y += 18
    positions["basic_label_y"] = y
    y += 18

    if _is_world_obj(view):
      positions["lock_y"] = y
      y += INSPECTOR_ROW_H + 6
      positions["layer_y"] = y
      y += INSPECTOR_ROW_H + 14
    else:
      positions["type_line_y"] = y
      y += 26 + 14

    entries = _find_entry_list(view)
    if entries is not None:
      positions["entries_label_y"] = y
      y += 18
      positions["entries_start_y"] = y
      n = len(entries)
      y += n * (INSPECTOR_ENTRY_ROW_H + 4)
      positions["add_y"] = y
      y += INSPECTOR_ROW_H + 8
      positions["total_y"] = y

    return positions

  def _layout(self):
    view = self._view()
    if view is None:
      return []
    fr = self._full_rect()
    pos = self._row_positions(fr)
    pad = INSPECTOR_PAD
    items = []

    close = pygame.Rect(fr.right - 34, pos["close_y"], 26, 26)
    items.append((close, "close", None))

    if _is_world_obj(view):
      row = pygame.Rect(fr.x + pad, pos["lock_y"],
                        fr.w - pad * 2, INSPECTOR_ROW_H)
      items.append((row, "lock", None))

      row = pygame.Rect(fr.x + pad, pos["layer_y"],
                        fr.w - pad * 2, INSPECTOR_ROW_H)
      dec = pygame.Rect(row.x + 120, row.y + 2, 24, row.h - 4)
      inc = pygame.Rect(row.right - 26, row.y + 2, 24, row.h - 4)
      items.append((dec, "layer_dec", None))
      items.append((inc, "layer_inc", None))

    entries = _find_entry_list(view)
    if entries is not None:
      y = pos["entries_start_y"]
      for entry in entries:
        row = pygame.Rect(fr.x + pad, y, fr.w - pad * 2, INSPECTOR_ENTRY_ROW_H)
        type_w = 80
        count_w = 60
        gear_w = INSPECTOR_GEAR_W if entry.get("type") == "cube" else 0
        del_w = 26
        gap = 4

        type_r = pygame.Rect(row.x, row.y, type_w, row.h)
        count_r = pygame.Rect(row.x + type_w + gap, row.y, count_w, row.h)
        gear_r = None
        x_after = count_r.right + gap
        if gear_w:
          gear_r = pygame.Rect(x_after, row.y, gear_w, row.h)
        del_r = pygame.Rect(row.right - del_w, row.y, del_w, row.h)

        items.append((type_r, "entry_type", entry))
        items.append((count_r, "entry_count", entry))
        if gear_r is not None:
          items.append((gear_r, "entry_gear", entry))
        items.append((del_r, "entry_del", entry))
        y += INSPECTOR_ENTRY_ROW_H + 4

      add = pygame.Rect(fr.x + pad, pos["add_y"],
                        fr.w - pad * 2, INSPECTOR_ROW_H)
      items.append((add, "add_entry", None))

    return items

  def _hit(self, pos):
    vr = self._visible_rect()
    if not vr.collidepoint(pos):
      return None
    for rect, kind, entry in self._layout():
      if rect.collidepoint(pos):
        return (kind, entry, rect)
    return None

  # ---------- events ----------
  def on_event(self, e):
    if not self.is_visible() or self.owner is None:
      return False

    fr = self._full_rect()

    if e.type == pygame.MOUSEMOTION:
      if fr.collidepoint(e.pos):
        h = self._hit(e.pos)
        if h is None:
          self.hover_key = None
          self.hover_entry = None
        else:
          self.hover_key = h[0]
          self.hover_entry = h[1]
        return True
      self.hover_key = None
      self.hover_entry = None
      return False

    if e.type == pygame.MOUSEBUTTONDOWN:
      if not fr.collidepoint(e.pos):
        if self.focused_entry is not None:
          self._commit_count()
        return False
      if e.button != 1:
        return True
      if self.focused_entry is not None:
        self._commit_count()
      h = self._hit(e.pos)
      if h is None:
        return True
      self._dispatch(h[0], h[1])
      return True

    if e.type == pygame.MOUSEWHEEL:
      return fr.collidepoint(pygame.mouse.get_pos())

    if e.type == pygame.KEYDOWN:
      if self.focused_entry is not None:
        self._on_count_key(e)
        return True
      return False

    return False

  def _dispatch(self, kind, entry):
    if self.owner is None:
      return

    if kind == "close":
      self.editor.pop_inspector()
      return

    # lock/layer — только для объектов мира
    if kind == "lock":
      if _is_world_obj(self.owner):
        self.owner.locked = not self.owner.locked
        self.editor._mark_scene_dirty()
      return
    if kind == "layer_dec":
      self._bump_layer(-1)
      return
    if kind == "layer_inc":
      self._bump_layer(+1)
      return

    # записи — работают и в объектах, и в dict
    if kind == "entry_type":
      self._open_type_menu(entry)
    elif kind == "entry_count":
      self.focused_entry = entry
      self.count_text[id(entry)] = str(entry.get("count", 1))
      self.cursor_blink = 0.0
    elif kind == "entry_gear":
      self.editor.push_inspector_entry(entry)
    elif kind == "entry_del":
      entries = _find_entry_list(self.owner)
      if entries is not None:
        for i, e in enumerate(entries):
          if e is entry:
            del entries[i]
            break
    elif kind == "add_entry":
      entries = _find_entry_list(self.owner)
      if entries is not None:
        entries.append({"type": SPAWNER_ENTRY_TYPES[0], "count": 1})

  def _bump_layer(self, delta):
    if not _is_world_obj(self.owner):
      return
    from .objects import default_layer_for
    cur = self.owner.layer if getattr(self.owner, "layer", None) is not None \
      else default_layer_for(self.owner)
    self.owner.layer = cur + delta
    self.editor._mark_scene_dirty()

  def _open_type_menu(self, entry):
    if self.owner is None:
      return
    from .widgets import ContextMenu
    pos = pygame.mouse.get_pos()
    def on_select(t):
      entry["type"] = t
      if t == "cube":
        entry.setdefault("contents", [])
      else:
        entry.pop("contents", None)
    options = [(t, t) for t in SPAWNER_ENTRY_TYPES]
    title = f"Type  ·  {entry.get('type', '?')}"
    self.editor.context_menu = ContextMenu(
      self.editor.screen.get_size(), options, pos, on_select, title=title)

  def _on_count_key(self, e):
    if e.key == pygame.K_ESCAPE:
      self.focused_entry = None
      return
    if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
      self._commit_count()
      return
    if e.key == pygame.K_BACKSPACE:
      buf = self.count_text.get(id(self.focused_entry), "")
      self.count_text[id(self.focused_entry)] = buf[:-1]
      return
    if e.unicode and e.unicode.isdigit():
      buf = self.count_text.get(id(self.focused_entry), "")
      if len(buf) < 7:
        self.count_text[id(self.focused_entry)] = buf + e.unicode

  def _commit_count(self):
    if self.focused_entry is None:
      return
    buf = self.count_text.get(id(self.focused_entry), "")
    try:
      v = int(buf)
      if v < 1:
        v = 1
    except ValueError:
      v = self.focused_entry.get("count", 1)
    self.focused_entry["count"] = v
    self.focused_entry = None

  # ---------- draw ----------
  def draw(self, screen):
    if not self.is_visible() or self._view() is None:
      return
    fr = self._full_rect()
    vr = self._visible_rect()
    if vr.w <= 0:
      return
    surf = pygame.Surface((INSPECTOR_W, fr.h), pygame.SRCALPHA)
    local = pygame.Rect(0, 0, INSPECTOR_W, fr.h)
    self._draw_panel(surf, local)
    src_x = INSPECTOR_W - vr.w
    screen.blit(surf, (vr.x, fr.y),
                area=pygame.Rect(src_x, 0, vr.w, fr.h))

  def _draw_panel(self, s, r):
    view = self._view()
    if view is None:
      return
    fr = self._full_rect()
    pos = self._row_positions(fr)
    # локальные координаты: сдвигаем pos на -fr.topleft
    ox, oy = fr.topleft

    pygame.draw.rect(s, INSPECTOR_BG, r)
    pygame.draw.line(s, INSPECTOR_BORDER,
                     (r.right - 1, r.y), (r.right - 1, r.bottom), 1)

    hdr = pygame.Rect(r.x, r.y, r.w, INSPECTOR_HEADER_H)
    pygame.draw.rect(s, INSPECTOR_HEADER_BG, hdr)
    pygame.draw.line(s, INSPECTOR_BORDER,
                     (r.x, hdr.bottom - 1), (r.right, hdr.bottom - 1), 1)

    kind = self._title_for(view)
    title = self.font_title.render(kind, True, INSPECTOR_TITLE)
    s.blit(title, (hdr.x + INSPECTOR_PAD,
                   hdr.y + (hdr.h - title.get_height()) // 2))

    close_r = pygame.Rect(r.right - 34, pos["close_y"] - oy, 26, 26)
    bg = INSPECTOR_BTN_HOVER if self._is_hover("close", None) else INSPECTOR_BTN_BG
    pygame.draw.rect(s, bg, close_r, border_radius=4)
    pygame.draw.rect(s, INSPECTOR_BTN_BORDER, close_r, 1, border_radius=4)
    xs = self.font.render("x", True, INSPECTOR_BTN_TEXT)
    s.blit(xs, xs.get_rect(center=close_r.center))

    self._draw_basic(s, r, pos, ox, oy)
    entries = _find_entry_list(view)
    if entries is not None:
      self._draw_entries_section(s, r, entries, pos, ox, oy)

  @staticmethod
  def _title_for(view):
    if isinstance(view, dict):
      t = view.get("type", "?")
      return "cube  ·  contents" if t == "cube" else f"entry  ·  {t}"
    return type(view).__name__.replace("Editor", "")

  def _draw_basic(self, s, r, pos, ox, oy):
    view = self._view()
    if view is None:
      return
    pad = INSPECTOR_PAD

    y_lbl = pos["basic_label_y"] - oy
    lbl = self.font_small.render("BASIC", True, INSPECTOR_SECTION)
    s.blit(lbl, (pad, y_lbl))

    if _is_world_obj(view):
      y_lock = pos["lock_y"] - oy
      row = pygame.Rect(pad, y_lock, INSPECTOR_W - pad * 2, INSPECTOR_ROW_H)
      self._row_bg(s, row, self._is_hover("lock", None))
      s.blit(self.font.render("Locked", True, INSPECTOR_LABEL),
             (row.x + 10, row.y + (row.h - self.font.get_height()) // 2))
      val = "yes" if view.locked else "no"
      fg = INSPECTOR_DANGER if view.locked else INSPECTOR_LABEL
      vs = self.font.render(val, True, fg)
      s.blit(vs, (row.right - vs.get_width() - 10,
                  row.y + (row.h - vs.get_height()) // 2))

      from .objects import default_layer_for
      y_lr = pos["layer_y"] - oy
      lr = pygame.Rect(pad, y_lr, INSPECTOR_W - pad * 2, INSPECTOR_ROW_H)
      self._row_bg(s, lr, False)
      s.blit(self.font.render("Layer", True, INSPECTOR_LABEL),
             (lr.x + 10, lr.y + (lr.h - self.font.get_height()) // 2))
      cur = view.layer if view.layer is not None else default_layer_for(view)
      is_def = view.layer is None
      lv = self.font.render(str(cur), True,
                            INSPECTOR_HINT if is_def else INSPECTOR_TITLE)
      s.blit(lv, (lr.x + 80, lr.y + (lr.h - lv.get_height()) // 2))

      for key, xr in (("layer_dec", lr.x + 120), ("layer_inc", lr.right - 26)):
        rr = pygame.Rect(xr, lr.y + 2, 24, lr.h - 4)
        hov = self._is_hover(key, None)
        bg = INSPECTOR_BTN_HOVER if hov else INSPECTOR_BTN_BG
        pygame.draw.rect(s, bg, rr, border_radius=3)
        pygame.draw.rect(s, INSPECTOR_BTN_BORDER, rr, 1, border_radius=3)
        t = "-" if key == "layer_dec" else "+"
        ts = self.font.render(t, True, INSPECTOR_BTN_TEXT)
        s.blit(ts, ts.get_rect(center=rr.center))
    else:
      y_type = pos["type_line_y"] - oy
      tn = view.get("type", "?")
      ts = self.font.render(f"type: {tn}", True, INSPECTOR_LABEL)
      s.blit(ts, (pad, y_type))

  def _draw_entries_section(self, s, r, entries, pos, ox, oy):
    pad = INSPECTOR_PAD
    y_lbl = pos["entries_label_y"] - oy
    lbl = self.font_small.render("ITEMS (WEIGHTED)", True, INSPECTOR_SECTION)
    s.blit(lbl, (pad, y_lbl))

    total = sum(e.get("count", 1) for e in entries)
    y = pos["entries_start_y"] - oy

    for entry in entries:
      row = pygame.Rect(pad, y, INSPECTOR_W - pad * 2, INSPECTOR_ENTRY_ROW_H)
      type_w = 80
      count_w = 60
      gear_w = INSPECTOR_GEAR_W if entry.get("type") == "cube" else 0
      del_w = 26
      gap = 4

      type_r = pygame.Rect(row.x, row.y, type_w, row.h)
      count_r = pygame.Rect(row.x + type_w + gap, row.y, count_w, row.h)
      gear_r = None
      x_after = count_r.right + gap
      if gear_w:
        gear_r = pygame.Rect(x_after, row.y, gear_w, row.h)
      del_r = pygame.Rect(row.right - del_w, row.y, del_w, row.h)

      hov = self._is_hover("entry_type", entry)
      bg = INSPECTOR_BTN_HOVER if hov else INSPECTOR_BTN_BG
      pygame.draw.rect(s, bg, type_r, border_radius=3)
      pygame.draw.rect(s, INSPECTOR_BTN_BORDER, type_r, 1, border_radius=3)
      tn = entry.get("type", "?")
      tcol = INSPECTOR_HINT if tn == "nothing" else INSPECTOR_BTN_TEXT
      ts = self.font.render(tn, True, tcol)
      s.blit(ts, ts.get_rect(center=type_r.center))

      focused = self.focused_entry is entry
      edge = INSPECTOR_INPUT_EDGE_FOCUS if focused else INSPECTOR_INPUT_EDGE
      pygame.draw.rect(s, INSPECTOR_INPUT_BG, count_r, border_radius=3)
      pygame.draw.rect(s, edge, count_r, 1, border_radius=3)
      txt = self.count_text.get(id(entry), "") if focused else str(entry.get("count", 1))
      cs = self.font.render(txt, True, INSPECTOR_INPUT_TEXT)
      s.blit(cs, cs.get_rect(center=count_r.center))
      if focused and self.cursor_blink < 0.5:
        cx = count_r.centerx + cs.get_width() // 2 + 2
        pygame.draw.line(s, INSPECTOR_INPUT_TEXT,
                         (cx, count_r.y + 5), (cx, count_r.bottom - 5))

      if gear_r is not None:
        hov = self._is_hover("entry_gear", entry)
        bg = INSPECTOR_GEAR_HOVER if hov else INSPECTOR_GEAR_BG
        pygame.draw.rect(s, bg, gear_r, border_radius=3)
        pygame.draw.rect(s, INSPECTOR_BTN_BORDER, gear_r, 1, border_radius=3)
        self._draw_gear(s, gear_r.center)

      hov = self._is_hover("entry_del", entry)
      bg = INSPECTOR_DANGER_HOVER if hov else INSPECTOR_DANGER
      pygame.draw.rect(s, bg, del_r, border_radius=3)
      xs = self.font.render("x", True, (255, 255, 255))
      s.blit(xs, xs.get_rect(center=del_r.center))

      y += INSPECTOR_ENTRY_ROW_H + 4

    add_r = pygame.Rect(pad, pos["add_y"] - oy, INSPECTOR_W - pad * 2,
                        INSPECTOR_ROW_H)
    hov = self._is_hover("add_entry", None)
    bg = INSPECTOR_BTN_HOVER if hov else INSPECTOR_BTN_BG
    pygame.draw.rect(s, bg, add_r, border_radius=3)
    pygame.draw.rect(s, INSPECTOR_BTN_BORDER, add_r, 1, border_radius=3)
    ts = self.font.render("+ Add item", True, INSPECTOR_BTN_TEXT)
    s.blit(ts, ts.get_rect(center=add_r.center))

    if total > 0:
      total_str = f"total weight: {total}"
    else:
      total_str = "total weight: 0  (nothing will spawn)"
    col = INSPECTOR_DANGER if total == 0 else INSPECTOR_SECTION
    ts = self.font_small.render(total_str, True, col)
    s.blit(ts, (pad, pos["total_y"] - oy))

  def _draw_gear(self, s, center):
    cx, cy = center
    r_out = 8
    r_in = 5
    teeth = 6
    pts = []
    for i in range(teeth * 2):
      ang = (i / (teeth * 2)) * math.tau - math.pi / 2
      r = r_out if i % 2 == 0 else r_in
      pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
    pygame.draw.polygon(s, INSPECTOR_GEAR_TEXT, pts)
    pygame.draw.circle(s, INSPECTOR_GEAR_BG, (int(cx), int(cy)), 3)
    pygame.draw.circle(s, INSPECTOR_GEAR_TEXT, (int(cx), int(cy)), 3, 1)

  def _row_bg(self, s, r, hover):
    bg = INSPECTOR_ROW_HOVER if hover else INSPECTOR_ROW_BG
    pygame.draw.rect(s, bg, r, border_radius=3)
    pygame.draw.rect(s, INSPECTOR_ROW_EDGE, r, 1, border_radius=3)

  def _is_hover(self, kind, entry):
    if self.hover_key != kind:
      return False
    if entry is None:
      return self.hover_entry is None
    return self.hover_entry is entry