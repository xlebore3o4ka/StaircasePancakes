"""Graphical launcher for Lestnichnie Blini (singleplayer / multiplayer).

Standalone: only imports game.Game. Does not touch game/ or shared/.
Run: python launcher.py
"""
import glob
import os
import sys

import pygame

from game import Game


# <STRANGE>#772: crash logger so silent exits leave a trace
import traceback as _tb

def _log_crash(tag, exc):
    try:
        with open("launcher_crash.log", "a", encoding="utf-8") as f:
            f.write("==== %s ====\n" % tag)
            _tb.print_exception(type(exc), exc, exc.__traceback__, file=f)
            f.write("\n")
    except Exception:
        pass
    _tb.print_exc()

# <STRANGE>#780: remember last used nickname and server url
SETTINGS_PATH = "launcher_settings.json"

def _load_launcher_settings():
    try:
        import json
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}

def _save_launcher_settings(name, server):
    try:
        import json
        data = _load_launcher_settings()
        data["name"] = name or ""
        data["server"] = server or ""
        with open(SETTINGS_PATH, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass




# ---------------------------------------------------------------
# style (kept local so launcher does not depend on editor/)
# ---------------------------------------------------------------
WIN_W, WIN_H = 900, 600
FPS = 60

BG          = (28, 31, 38)
PANEL_BG    = (24, 27, 33)
PANEL_EDGE  = (60, 66, 78)
TITLE_FG    = (225, 230, 240)
LABEL_FG    = (170, 176, 188)
HINT_FG     = (110, 116, 128)
GOLD        = (255, 215, 0)

BTN_BG      = (60, 66, 78)
BTN_BG_HOV  = (80, 88, 102)
BTN_BG_PRS  = (46, 52, 62)
BTN_BG_ACT  = (58, 128, 92)
BTN_BORDER  = (105, 112, 126)
BTN_TEXT    = (225, 230, 240)
BTN_TEXT_D  = (130, 135, 145)

INPUT_BG    = (16, 18, 22)
INPUT_EDGE  = (85, 92, 106)
INPUT_FOCUS = GOLD
INPUT_TEXT  = (235, 238, 245)
INPUT_PH    = (110, 116, 128)

ROW_BG      = (42, 46, 56)
ROW_HOV     = (56, 62, 74)
ROW_SEL     = (58, 128, 92)
ROW_EDGE    = (70, 76, 88)
ROW_TEXT    = (225, 230, 240)


LEVELS_DIR = "levels"


# ---------------------------------------------------------------
# widgets
# ---------------------------------------------------------------
class Button:
    def __init__(self, rect, label, on_click, toggle=False):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.on_click = on_click
        self.toggle = toggle
        self.active = False
        self.hover = False
        self.pressed = False

    def handle(self, e):
        if e.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(e.pos)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.rect.collidepoint(e.pos):
                self.pressed = True
                return True
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            was = self.pressed
            self.pressed = False
            if was and self.rect.collidepoint(e.pos):
                if self.toggle:
                    self.active = not self.active
                if self.on_click:
                    self.on_click(self)
                return True
        return False

    def draw(self, screen, font):
        if self.toggle and self.active:
            bg, fg, border = BTN_BG_ACT, BTN_TEXT, GOLD
            bw = 2
        elif self.pressed:
            bg, fg, border = BTN_BG_PRS, BTN_TEXT, BTN_BORDER
            bw = 1
        elif self.hover:
            bg, fg, border = BTN_BG_HOV, BTN_TEXT, BTN_BORDER
            bw = 1
        else:
            bg, fg, border = BTN_BG, BTN_TEXT, BTN_BORDER
            bw = 1
        pygame.draw.rect(screen, bg, self.rect, border_radius=5)
        pygame.draw.rect(screen, border, self.rect, bw, border_radius=5)
        surf = font.render(self.label, True, fg)
        screen.blit(surf, surf.get_rect(center=self.rect.center))


class TextField:
    def __init__(self, rect, placeholder="", text=""):
        self.rect = pygame.Rect(rect)
        self.placeholder = placeholder
        self.text = text
        self.focused = False
        self.blink = 0.0

    @staticmethod
    def _clip_get():
        # <STRANGE>#764: tkinter is std-lib and already used by editor/.
        try:
            import tkinter as tk
            r = tk.Tk()
            r.withdraw()
            try:
                txt = r.clipboard_get()
            except Exception:
                txt = ""
            r.destroy()
            return txt or ""
        except Exception:
            pass
        # fallback: pygame 2.2+ text API
        try:
            return pygame.scrap.get_text() or ""
        except Exception:
            return ""

    @staticmethod
    def _clip_put(txt):
        try:
            import tkinter as tk
            r = tk.Tk()
            r.withdraw()
            r.clipboard_clear()
            r.clipboard_append(txt)
            r.update()
            r.destroy()
            return True
        except Exception:
            pass
        try:
            pygame.scrap.put_text(txt)
            return True
        except Exception:
            return False

    def _paste_from_clipboard(self):
        txt = self._clip_get()
        txt = txt.replace("\x00", "").replace("\r", "").replace("\n", "")
        txt = "".join(ch for ch in txt if ch.isprintable())
        if txt:
            self.text += txt

    def _copy_to_clipboard(self, cut=False):
        # <STRANGE>#765: no selection model yet - copy/paste whole field
        self._clip_put(self.text)
        if cut:
            self.text = ""

    def handle(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.rect.collidepoint(e.pos):
                self.focused = True
                self.blink = 0.0
                return True
            if self.focused:
                self.focused = False
        if e.type == pygame.KEYDOWN and self.focused:
            mods = pygame.key.get_mods()
            ctrl = bool(mods & pygame.KMOD_CTRL)
            if ctrl:
                if e.key == pygame.K_v:
                    self._paste_from_clipboard()
                    return True
                if e.key == pygame.K_c:
                    self._copy_to_clipboard(cut=False)
                    return True
                if e.key == pygame.K_x:
                    self._copy_to_clipboard(cut=True)
                    return True
                if e.key == pygame.K_a:
                    # no selection model yet: swallow to avoid inserting "a"
                    return True
                # ignore other ctrl chords in the field
                return True
            if e.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                return True
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
                self.focused = False
                return True
            if e.key in (pygame.K_HOME, pygame.K_END,
                         pygame.K_LEFT, pygame.K_RIGHT,
                         pygame.K_UP, pygame.K_DOWN):
                # no caret movement yet - swallow so they do not type
                return True
            if e.unicode and e.unicode.isprintable():
                self.text += e.unicode
                return True
            return True
        return False

    def update(self, dt):
        self.blink = (self.blink + dt) % 1.0

    def draw(self, screen, font):
        pygame.draw.rect(screen, INPUT_BG, self.rect, border_radius=5)
        edge = INPUT_FOCUS if self.focused else INPUT_EDGE
        pygame.draw.rect(screen, edge, self.rect, 1, border_radius=5)
        pad = 10
        if self.text:
            surf = font.render(self.text, True, INPUT_TEXT)
        else:
            surf = font.render(self.placeholder, True, INPUT_PH)
        screen.blit(surf, (self.rect.x + pad,
                           self.rect.centery - surf.get_height() // 2))
        if self.focused and self.blink < 0.5:
            cx = self.rect.x + pad + font.size(self.text)[0] + 1
            pygame.draw.line(screen, INPUT_TEXT,
                             (cx, self.rect.y + 8),
                             (cx, self.rect.bottom - 8))


class MapList:
    """Scrollable list of level files. Click selects, double-click plays."""

    def __init__(self, rect, on_pick, on_double=None):
        self.rect = pygame.Rect(rect)
        self.on_pick = on_pick
        self.on_double = on_double
        self.items = []       # list of paths
        self.selected = -1
        self.hover = -1
        self.scroll = 0
        self.row_h = 30
        self.last_click_t = 0.0
        self.last_click_idx = -1

    def set_items(self, paths):
        self.items = list(paths)
        self.selected = 0 if self.items else -1
        self.scroll = 0
        if self.selected >= 0:
            self.on_pick(self.items[self.selected])

    def _row_at(self, pos):
        if not self.rect.collidepoint(pos):
            return -1
        y = pos[1] - self.rect.y + self.scroll
        idx = int(y // self.row_h)
        if 0 <= idx < len(self.items):
            return idx
        return -1

    def handle(self, e, now):
        if e.type == pygame.MOUSEMOTION:
            self.hover = self._row_at(e.pos)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            idx = self._row_at(e.pos)
            if idx >= 0:
                self.selected = idx
                self.on_pick(self.items[idx])
                # double-click detection
                if (idx == self.last_click_idx) and (now - self.last_click_t < 0.4):
                    if self.on_double:
                        self.on_double(self.items[idx])
                    self.last_click_idx = -1
                    self.last_click_t = 0.0
                else:
                    self.last_click_idx = idx
                    self.last_click_t = now
                return True
        elif e.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                self.scroll -= e.y * self.row_h
                max_scroll = max(0, len(self.items) * self.row_h - self.rect.h)
                self.scroll = max(0, min(self.scroll, max_scroll))
                return True
        return False

    def draw(self, screen, font, font_small):
        pygame.draw.rect(screen, PANEL_BG, self.rect, border_radius=6)
        pygame.draw.rect(screen, PANEL_EDGE, self.rect, 1, border_radius=6)

        clip = screen.get_clip()
        screen.set_clip(self.rect.inflate(-2, -2))
        y = self.rect.y - self.scroll
        for i, path in enumerate(self.items):
            row = pygame.Rect(self.rect.x + 2, y, self.rect.w - 4, self.row_h)
            if i == self.selected:
                pygame.draw.rect(screen, ROW_SEL, row, border_radius=4)
                fg = (245, 248, 255)
            elif i == self.hover:
                pygame.draw.rect(screen, ROW_HOV, row, border_radius=4)
                fg = ROW_TEXT
            else:
                pygame.draw.rect(screen, ROW_BG, row, border_radius=4)
                fg = ROW_TEXT
            pygame.draw.rect(screen, ROW_EDGE, row, 1, border_radius=4)
            name = os.path.splitext(os.path.basename(path))[0]
            surf = font.render(name, True, fg)
            screen.blit(surf, (row.x + 12,
                               row.centery - surf.get_height() // 2))
            y += self.row_h
        screen.set_clip(clip)

        if not self.items:
            msg = font_small.render("no levels in levels/", True, HINT_FG)
            screen.blit(msg, msg.get_rect(center=self.rect.center))


# ---------------------------------------------------------------
# app
# ---------------------------------------------------------------
class Launcher:
    SINGLE = 0
    MULTI  = 1

    def __init__(self):
        pygame.init()
        # <STRANGE>#763: clipboard goes through tkinter (std-lib).
        # pygame.scrap is deprecated since 2.2 and does not work.
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("Lestnichnie Blini")
        self.clock = pygame.time.Clock()
        self.font       = pygame.font.SysFont(None, 24)
        self.font_small = pygame.font.SysFont(None, 20)
        self.font_title = pygame.font.SysFont(None, 40, bold=True)
        self.font_tab   = pygame.font.SysFont(None, 26, bold=True)

        self.running = True
        self.mode = self.SINGLE
        self.launch_cfg = None  # set when user presses Play/Connect

        self.cheats = False
        self.spawninfo = False

        # widgets ---------------------------------------------------
        self.tab_sp_rect = pygame.Rect(20, 80, 200, 44)
        self.tab_mp_rect = pygame.Rect(230, 80, 200, 44)

        self.list_rect = pygame.Rect(20, 140, 540, 380)
        self.map_list = MapList(
            self.list_rect,
            on_pick=self._on_pick,
            on_double=lambda p: self._play(),
        )

        # right side panel (mode specific) --------------------------
        px = 580
        pw = WIN_W - px - 20

        self.cheats_btn   = Button((px, 140, pw, 36), "Cheats", self._toggle_cheats, toggle=True)
        self.spawn_btn    = Button((px, 184, pw, 36), "Spawn info", self._toggle_spawn, toggle=True)

        self.name_field   = TextField((px, 140, pw, 36), "nickname")
        self.server_field = TextField((px, 184, pw, 36), "ws://host:port")
        # <STRANGE>#781: prefill from launcher_settings.json
        _cfg = _load_launcher_settings()
        self.name_field.text = str(_cfg.get("name", "") or "")
        self.server_field.text = str(_cfg.get("server", "") or "")
        self.name_lbl_pos   = (px, 116)
        self.server_lbl_pos = (px, 160)

        self.play_btn  = Button((px, WIN_H - 80, pw, 48), "Play", self._play)
        self.quit_btn  = Button((WIN_W - 120, 20, 100, 36), "Quit", self._quit)

        self.error = ""
        self.error_t = 0.0

    # ---------------- events ----------------
    def handle(self, e, now):
        if e.type == pygame.QUIT:
            self.running = False
            return

        # tabs
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.tab_sp_rect.collidepoint(e.pos):
                self.mode = self.SINGLE
                return
            if self.tab_mp_rect.collidepoint(e.pos):
                self.mode = self.MULTI
                return

        # global widgets
        if self.quit_btn.handle(e):
            return
        if self.play_btn.handle(e):
            return

        # list (works for both modes)
        if self.map_list.handle(e, now):
            return

        # right panel
        if self.mode == self.SINGLE:
            self.cheats_btn.handle(e)
            self.spawn_btn.handle(e)
        else:
            self.name_field.handle(e)
            self.server_field.handle(e)

        # Enter anywhere -> play
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._play()

        # Esc -> quit
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.running = False

    # ---------------- actions ----------------
    def _toggle_cheats(self, btn):
        self.cheats = btn.active

    def _toggle_spawn(self, btn):
        self.spawninfo = btn.active

    def _on_pick(self, path):
        # clear error when the map changes
        self.error = ""

    def _play(self, _btn=None):
        if self.map_list.selected < 0:
            self._set_error("Pick a level first.")
            return
        path = self.map_list.items[self.map_list.selected]
        if self.mode == self.SINGLE:
            self.launch_cfg = dict(
                cheats=self.cheats,
                map_path=path,
                spawninfo=self.spawninfo,
                name=None,
                server=None,
            )
            self.running = False
        else:
            name = self.name_field.text.strip()
            server = self.server_field.text.strip()
            if not name:
                self._set_error("Enter a nickname.")
                return
            if not server:
                self._set_error("Enter a server url.")
                return
            self.launch_cfg = dict(
                cheats=self.cheats,
                map_path=path,
                spawninfo=self.spawninfo,
                name=name,
                server=server,
            )
            self.running = False

    def _quit(self, btn):
        # <STRANGE>#783: persist last typed values even without Connect
        try:
            _save_launcher_settings(
                self.name_field.text.strip(),
                self.server_field.text.strip())
        except Exception:
            pass
        self.launch_cfg = None
        self.running = False

    def _set_error(self, msg):
        self.error = msg
        self.error_t = 2.5

    # ---------------- draw ----------------
    def draw(self):
        self.screen.fill(BG)

        # title
        title = self.font_title.render("Lestnichnie Blini", True, TITLE_FG)
        self.screen.blit(title, (20, 20))

        # tabs
        self._draw_tab(self.tab_sp_rect, "Singleplayer", self.mode == self.SINGLE)
        self._draw_tab(self.tab_mp_rect, "Multiplayer",  self.mode == self.MULTI)

        # map list
        self.map_list.draw(self.screen, self.font, self.font_small)

        # right panel
        if self.mode == self.SINGLE:
            self._draw_label("Options", (580, 116))
            self.cheats_btn.draw(self.screen, self.font)
            self.spawn_btn.draw(self.screen, self.font)
        else:
            self._draw_label("Nickname", self.name_lbl_pos)
            self.name_field.draw(self.screen, self.font)
            self._draw_label("Server", self.server_lbl_pos)
            self.server_field.draw(self.screen, self.font)

        # play + quit
        self.play_btn.label = "Play" if self.mode == self.SINGLE else "Connect"
        self.play_btn.draw(self.screen, self.font)
        self.quit_btn.draw(self.screen, self.font)

        # error
        if self.error and self.error_t > 0:
            es = self.font.render(self.error, True, (230, 90, 90))
            self.screen.blit(es, (580, WIN_H - 110))

        # footer hint
        hint = self.font_small.render(
            "double-click a level to play  ??  Esc to quit", True, HINT_FG)
        self.screen.blit(hint, (20, WIN_H - 30))

    def _draw_tab(self, rect, label, active):
        bg = BTN_BG_ACT if active else BTN_BG
        edge = GOLD if active else BTN_BORDER
        pygame.draw.rect(self.screen, bg, rect, border_radius=6)
        pygame.draw.rect(self.screen, edge, rect, 2 if active else 1, border_radius=6)
        fg = (245, 248, 255) if active else BTN_TEXT
        surf = self.font_tab.render(label, True, fg)
        self.screen.blit(surf, surf.get_rect(center=rect.center))

    def _draw_label(self, text, pos):
        surf = self.font_small.render(text, True, LABEL_FG)
        self.screen.blit(surf, pos)

    # ---------------- loop ----------------
    def run(self):
        # populate list
        maps = []
        if os.path.isdir(LEVELS_DIR):
            maps = sorted(glob.glob(os.path.join(LEVELS_DIR, "*.json")))
        self.map_list.set_items(maps)

        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            now = pygame.time.get_ticks() / 1000.0
            for e in pygame.event.get():
                try:
                    self.handle(e, now)
                except SystemExit:
                    raise
                except Exception as _ex:
                    _log_crash("handle_event", _ex)
                    self.running = False
            self.name_field.update(dt)
            self.server_field.update(dt)
            if self.error_t > 0:
                self.error_t -= dt
            self.draw()
            pygame.display.flip()

        # <STRANGE>#770: do NOT call pygame.quit() here. It tears
        # down the display and breaks the next set_mode() inside Game.
        # Let Game manage its own pygame lifecycle.

        if self.launch_cfg is not None:
            try:
                Game(**self.launch_cfg).run()
            except Exception as _ex:
                _log_crash("game_launch", _ex)
                try:
                    input("Game crashed. See launcher_crash.log. Press Enter...")
                except Exception:
                    pass
            finally:
                try:
                    pygame.quit()
                except Exception:
                    pass
        else:
            try:
                pygame.quit()
            except Exception:
                pass


def main():
    Launcher().run()


if __name__ == "__main__":
    main()
