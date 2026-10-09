"""РЎС‚РµРє РёРЅСЃРїРµРєС‚РѕСЂРѕРІ. Р РµРєСѓСЂСЃРёРІРЅС‹Рµ contents РїРѕРґРґРµСЂР¶РёРІР°СЋС‚СЃСЏ."""
import math
from raylib import (
  DrawRectangle, DrawRectangleLines, DrawCircle, DrawCircleLines,
  DrawLine,
  BeginScissorMode, EndScissorMode,
)

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
from .helpers import C, draw_text, text_width


def _find_entry_list(owner):
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


def _hit(r, pos):
  return r[0] <= pos[0] < r[0] + r[2] and r[1] <= pos[1] < r[1] + r[3]


class InspectorPanel:
  def __init__(self, editor, owner, depth=0):
    self.editor = editor
    self.owner = owner
    self.depth = depth

    self._last = owner
    self.t = 0.0

    self.count_text = {}
    self.focused_entry = None
    self.cursor_blink = 0.0

    self.hover_key = None
    self.hover_entry = None

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

  def _full_rect(self):
    sw, sh = self.editor.screen_size
    top = self.editor.panel.height()
    x = sw - INSPECTOR_W - self.depth * INSPECTOR_STACK_STEP
    return (x, top, INSPECTOR_W, sh - top - BOT_H)

  def _visible_rect(self):
    fr = self._full_rect()
    offset = int(INSPECTOR_W * (1.0 - self.t))
    return (fr[0] + offset, fr[1], INSPECTOR_W - offset, fr[3])

  def _row_positions(self):
    view = self._view()
    if view is None:
      return None
    fr = self._full_rect()
    positions = {}
    y = fr[1] + 8
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
      y += len(entries) * (INSPECTOR_ENTRY_ROW_H + 4)
      positions["add_y"] = y
      y += INSPECTOR_ROW_H + 8
      positions["total_y"] = y
    return positions

  def _layout(self):
    view = self._view()
    if view is None:
      return []
    fr = self._full_rect()
    pos = self._row_positions()
    pad = INSPECTOR_PAD
    items = []

    close = (fr[0] + fr[2] - 34, pos["close_y"], 26, 26)
    items.append((close, "close", None))

    if _is_world_obj(view):
      row = (fr[0] + pad, pos["lock_y"], fr[2] - pad * 2, INSPECTOR_ROW_H)
      items.append((row, "lock", None))
      row = (fr[0] + pad, pos["layer_y"], fr[2] - pad * 2, INSPECTOR_ROW_H)
      dec = (row[0] + 120, row[1] + 2, 24, row[3] - 4)
      inc = (row[0] + row[2] - 26, row[1] + 2, 24, row[3] - 4)
      items.append((dec, "layer_dec", None))
      items.append((inc, "layer_inc", None))

    entries = _find_entry_list(view)
    if entries is not None:
      y = pos["entries_start_y"]
      for entry in entries:
        row = (fr[0] + pad, y, fr[2] - pad * 2, INSPECTOR_ENTRY_ROW_H)
        type_w = 80
        count_w = 60
        gear_w = INSPECTOR_GEAR_W if entry.get("type") == "cube" else 0
        del_w = 26
        gap = 4
        type_r = (row[0], row[1], type_w, row[3])
        count_r = (row[0] + type_w + gap, row[1], count_w, row[3])
        gear_r = None
        x_after = count_r[0] + count_r[2] + gap
        if gear_w:
          gear_r = (x_after, row[1], gear_w, row[3])
        del_r = (row[0] + row[2] - del_w, row[1], del_w, row[3])
        items.append((type_r, "entry_type", entry))
        items.append((count_r, "entry_count", entry))
        if gear_r is not None:
          items.append((gear_r, "entry_gear", entry))
        items.append((del_r, "entry_del", entry))
        y += INSPECTOR_ENTRY_ROW_H + 4
      add = (fr[0] + pad, pos["add_y"], fr[2] - pad * 2, INSPECTOR_ROW_H)
      items.append((add, "add_entry", None))
    return items

  def _hit_at(self, pos):
    vr = self._visible_rect()
    if not _hit(vr, pos):
      return None
    for rect, kind, entry in self._layout():
      if _hit(rect, pos):
        return (kind, entry, rect)
    return None

  def on_event(self, e_type, pos, button):
    if not self.is_visible() or self.owner is None:
      return False

    fr = self._full_rect()

    if e_type == "move":
      if _hit(fr, pos):
        h = self._hit_at(pos)
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

    if e_type == "down":
      if not _hit(fr, pos):
        if self.focused_entry is not None:
          self._commit_count()
        return False
      if button != 0:
        return True
      if self.focused_entry is not None:
        self._commit_count()
      h = self._hit_at(pos)
      if h is None:
        return True
      self._dispatch(h[0], h[1])
      return True

    if e_type == "scroll":
      return _hit(fr, pos)

    return False

  def _dispatch(self, kind, entry):
    if self.owner is None:
      return
    if kind == "close":
      self.editor.close_inspector(self)
      return
    if kind == "lock":
      if _is_world_obj(self.owner):
        self.owner.locked = not self.owner.locked
        self.editor._mark_scene_dirty()
      return
    if kind == "layer_dec":
      self._bump_layer(-1); return
    if kind == "layer_inc":
      self._bump_layer(+1); return

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
    pos = self.editor.get_mouse_pos()
    def on_select(t):
      entry["type"] = t
      if t == "cube":
        entry.setdefault("contents", [])
      else:
        entry.pop("contents", None)
    options = [(t, t) for t in SPAWNER_ENTRY_TYPES]
    title = "Type  -  " + str(entry.get("type", "?"))
    self.editor.context_menu = ContextMenu(
      self.editor.screen_size, options, pos, on_select, title=title)

  def handle_text(self, ch):
    if self.focused_entry is None:
      return False
    if ch.isdigit():
      buf = self.count_text.get(id(self.focused_entry), "")
      if len(buf) < 7:
        self.count_text[id(self.focused_entry)] = buf + ch
    return True

  def handle_key(self, key):
    if self.focused_entry is None:
      return False
    from raylib import KeyboardKey
    if key == KeyboardKey.KEY_ESCAPE:
      self.focused_entry = None
      return True
    if key in (KeyboardKey.KEY_ENTER, KeyboardKey.KEY_KP_ENTER,
               KeyboardKey.KEY_TAB):
      self._commit_count()
      return True
    if key == KeyboardKey.KEY_BACKSPACE:
      buf = self.count_text.get(id(self.focused_entry), "")
      self.count_text[id(self.focused_entry)] = buf[:-1]
      return True
    return True

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

  def draw(self):
    if not self.is_visible() or self._view() is None:
      return
    fr = self._full_rect()
    vr = self._visible_rect()
    if vr[2] <= 0:
      return
    BeginScissorMode(vr[0], vr[1], vr[2], vr[3])
    self._draw_panel(fr)
    EndScissorMode()

  def _draw_panel(self, fr):
    view = self._view()
    if view is None:
      return
    pos = self._row_positions()
    if pos is None:
      return

    DrawRectangle(fr[0], fr[1], fr[2], fr[3], C(INSPECTOR_BG))
    DrawLine(fr[0] + fr[2] - 1, fr[1],
             fr[0] + fr[2] - 1, fr[1] + fr[3], C(INSPECTOR_BORDER))

    hdr = (fr[0], fr[1], fr[2], INSPECTOR_HEADER_H)
    DrawRectangle(hdr[0], hdr[1], hdr[2], hdr[3], C(INSPECTOR_HEADER_BG))
    DrawLine(hdr[0], hdr[1] + hdr[3] - 1,
             hdr[0] + hdr[2], hdr[1] + hdr[3] - 1, C(INSPECTOR_BORDER))

    kind = self._title_for(view)
    draw_text(kind, hdr[0] + INSPECTOR_PAD,
              hdr[1] + (hdr[3] - 22) // 2, 22, C(INSPECTOR_TITLE))

    cx, cy = fr[0] + fr[2] - 34, pos["close_y"]
    bg = INSPECTOR_BTN_HOVER if self._is_hover("close", None) else INSPECTOR_BTN_BG
    DrawRectangle(cx, cy, 26, 26, C(bg))
    DrawRectangleLines(cx, cy, 26, 26, C(INSPECTOR_BTN_BORDER))
    tw = text_width("x", 20)
    draw_text("x", cx + (26 - tw) // 2, cy + 3, 20, C(INSPECTOR_BTN_TEXT))

    self._draw_basic(fr, pos)
    entries = _find_entry_list(view)
    if entries is not None:
      self._draw_entries_section(fr, entries, pos)

  @staticmethod
  def _title_for(view):
    if isinstance(view, dict):
      t = view.get("type", "?")
      return "cube  -  contents" if t == "cube" else "entry  -  " + str(t)
    return type(view).__name__.replace("Editor", "")

  def _draw_basic(self, fr, pos):
    view = self._view()
    if view is None:
      return
    pad = INSPECTOR_PAD

    draw_text("BASIC", fr[0] + pad, pos["basic_label_y"], 18, C(INSPECTOR_SECTION))

    if _is_world_obj(view):
      y_lock = pos["lock_y"]
      row = (fr[0] + pad, y_lock, fr[2] - pad * 2, INSPECTOR_ROW_H)
      self._row_bg(row, self._is_hover("lock", None))
      draw_text("Locked", row[0] + 10, row[1] + (row[3] - 20) // 2, 20, C(INSPECTOR_LABEL))
      val = "yes" if view.locked else "no"
      fg = INSPECTOR_DANGER if view.locked else INSPECTOR_LABEL
      vw = text_width(val, 20)
      draw_text(val, row[0] + row[2] - vw - 10, row[1] + (row[3] - 20) // 2,
                20, C(fg))

      from .objects import default_layer_for
      y_lr = pos["layer_y"]
      lr = (fr[0] + pad, y_lr, fr[2] - pad * 2, INSPECTOR_ROW_H)
      self._row_bg(lr, False)
      draw_text("Layer", lr[0] + 10, lr[1] + (lr[3] - 20) // 2, 20, C(INSPECTOR_LABEL))
      cur = view.layer if view.layer is not None else default_layer_for(view)
      is_def = view.layer is None
      lcol = INSPECTOR_HINT if is_def else INSPECTOR_TITLE
      draw_text(str(cur), lr[0] + 80, lr[1] + (lr[3] - 20) // 2, 20, C(lcol))

      for key, xr in (("layer_dec", lr[0] + 120),
                      ("layer_inc", lr[0] + lr[2] - 26)):
        rr = (xr, lr[1] + 2, 24, lr[3] - 4)
        hov = self._is_hover(key, None)
        bg = INSPECTOR_BTN_HOVER if hov else INSPECTOR_BTN_BG
        DrawRectangle(rr[0], rr[1], rr[2], rr[3], C(bg))
        DrawRectangleLines(rr[0], rr[1], rr[2], rr[3],
                           C(INSPECTOR_BTN_BORDER))
        t = "-" if key == "layer_dec" else "+"
        tw = text_width(t, 20)
        draw_text(t, rr[0] + (rr[2] - tw) // 2, rr[1] + (rr[3] - 20) // 2,
                  20, C(INSPECTOR_BTN_TEXT))
    else:
      tn = view.get("type", "?")
      draw_text("type: " + str(tn), fr[0] + pad, pos["type_line_y"], 20,
                C(INSPECTOR_LABEL))

  def _draw_entries_section(self, fr, entries, pos):
    pad = INSPECTOR_PAD
    draw_text("ITEMS (WEIGHTED)", fr[0] + pad, pos["entries_label_y"],
              18, C(INSPECTOR_SECTION))

    total = sum(e.get("count", 1) for e in entries)
    y = pos["entries_start_y"]

    for entry in entries:
      row = (fr[0] + pad, y, fr[2] - pad * 2, INSPECTOR_ENTRY_ROW_H)
      type_w = 80
      count_w = 60
      gear_w = INSPECTOR_GEAR_W if entry.get("type") == "cube" else 0
      del_w = 26
      gap = 4

      type_r = (row[0], row[1], type_w, row[3])
      count_r = (row[0] + type_w + gap, row[1], count_w, row[3])
      gear_r = None
      x_after = count_r[0] + count_r[2] + gap
      if gear_w:
        gear_r = (x_after, row[1], gear_w, row[3])
      del_r = (row[0] + row[2] - del_w, row[1], del_w, row[3])

      hov = self._is_hover("entry_type", entry)
      bg = INSPECTOR_BTN_HOVER if hov else INSPECTOR_BTN_BG
      DrawRectangle(type_r[0], type_r[1], type_r[2], type_r[3], C(bg))
      DrawRectangleLines(type_r[0], type_r[1], type_r[2], type_r[3],
                         C(INSPECTOR_BTN_BORDER))
      tn = entry.get("type", "?")
      tcol = INSPECTOR_HINT if tn == "nothing" else INSPECTOR_BTN_TEXT
      tw = text_width(tn, 20)
      draw_text(tn, type_r[0] + (type_r[2] - tw) // 2,
                type_r[1] + (type_r[3] - 20) // 2, 20, C(tcol))

      focused = self.focused_entry is entry
      edge = INSPECTOR_INPUT_EDGE_FOCUS if focused else INSPECTOR_INPUT_EDGE
      DrawRectangle(count_r[0], count_r[1], count_r[2], count_r[3],
                    C(INSPECTOR_INPUT_BG))
      DrawRectangleLines(count_r[0], count_r[1], count_r[2], count_r[3],
                         C(edge))
      txt = self.count_text.get(id(entry), "") if focused else str(entry.get("count", 1))
      tw = text_width(txt, 20)
      tx = count_r[0] + (count_r[2] - tw) // 2
      ty = count_r[1] + (count_r[3] - 20) // 2
      draw_text(txt, tx, ty, 20, C(INSPECTOR_INPUT_TEXT))
      if focused and self.cursor_blink < 0.5:
        cx = tx + tw + 2
        DrawLine(cx, count_r[1] + 5,
                 cx, count_r[1] + count_r[3] - 5, C(INSPECTOR_INPUT_TEXT))

      if gear_r is not None:
        hov = self._is_hover("entry_gear", entry)
        bg = INSPECTOR_GEAR_HOVER if hov else INSPECTOR_GEAR_BG
        DrawRectangle(gear_r[0], gear_r[1], gear_r[2], gear_r[3], C(bg))
        DrawRectangleLines(gear_r[0], gear_r[1], gear_r[2], gear_r[3],
                           C(INSPECTOR_BTN_BORDER))
        self._draw_gear(gear_r[0] + gear_r[2] // 2, gear_r[1] + gear_r[3] // 2)

      hov = self._is_hover("entry_del", entry)
      bg = INSPECTOR_DANGER_HOVER if hov else INSPECTOR_DANGER
      DrawRectangle(del_r[0], del_r[1], del_r[2], del_r[3], C(bg))
      xw = text_width("x", 20)
      draw_text("x", del_r[0] + (del_r[2] - xw) // 2,
                del_r[1] + (del_r[3] - 20) // 2, 20, (255, 255, 255, 255))

      y += INSPECTOR_ENTRY_ROW_H + 4

    add_r = (fr[0] + pad, pos["add_y"], fr[2] - pad * 2, INSPECTOR_ROW_H)
    hov = self._is_hover("add_entry", None)
    bg = INSPECTOR_BTN_HOVER if hov else INSPECTOR_BTN_BG
    DrawRectangle(add_r[0], add_r[1], add_r[2], add_r[3], C(bg))
    DrawRectangleLines(add_r[0], add_r[1], add_r[2], add_r[3],
                       C(INSPECTOR_BTN_BORDER))
    label = "+ Add item"
    tw = text_width(label, 20)
    draw_text(label, add_r[0] + (add_r[2] - tw) // 2,
              add_r[1] + (add_r[3] - 20) // 2, 20, C(INSPECTOR_BTN_TEXT))

    if total > 0:
      total_str = "total weight: " + str(total)
    else:
      total_str = "total weight: 0  (nothing will spawn)"
    col = INSPECTOR_DANGER if total == 0 else INSPECTOR_SECTION
    draw_text(total_str, fr[0] + pad, pos["total_y"], 18, C(col))

  def _draw_gear(self, cx, cy):
    r_out = 8
    r_in = 5
    teeth = 6
    pts = []
    for i in range(teeth * 2):
      ang = (i / (teeth * 2)) * math.tau - math.pi / 2
      r = r_out if i % 2 == 0 else r_in
      pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
    col = C(INSPECTOR_GEAR_TEXT)
    for i in range(0, teeth * 2, 2):
      p0 = pts[i]
      p1 = pts[(i + 1) % (teeth * 2)]
      p2 = pts[(i + 2) % (teeth * 2)]
      DrawLine(int(p0[0]), int(p0[1]), int(p1[0]), int(p1[1]), col)
      DrawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]), col)
    DrawCircle(int(cx), int(cy), 4, C(INSPECTOR_GEAR_BG))
    DrawCircleLines(int(cx), int(cy), 4, C(INSPECTOR_GEAR_TEXT))

  def _row_bg(self, r, hover):
    bg = INSPECTOR_ROW_HOVER if hover else INSPECTOR_ROW_BG
    DrawRectangle(r[0], r[1], r[2], r[3], C(bg))
    DrawRectangleLines(r[0], r[1], r[2], r[3], C(INSPECTOR_ROW_EDGE))

  def _is_hover(self, kind, entry):
    if self.hover_key != kind:
      return False
    if entry is None:
      return self.hover_entry is None
    return self.hover_entry is entry