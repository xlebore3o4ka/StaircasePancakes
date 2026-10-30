import pygame
import os

from . import settings


class Button:
    def __init__(self, rect, label, action):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.action = action
        self.hover = False

    def handle(self, e):
        if e.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(e.pos)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos):
            return True
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.hover and self.rect.collidepoint(e.pos):
            if self.action:
                self.action()
            return True
        return False

    def draw(self, screen, font):
        bg = (80, 88, 102) if self.hover else (60, 66, 78)
        border = (200, 180, 80) if self.hover else (105, 112, 126)
        pygame.draw.rect(screen, bg, self.rect, border_radius=6)
        pygame.draw.rect(screen, border, self.rect, 2 if self.hover else 1, border_radius=6)
        surf = font.render(self.label, True, (225, 230, 240))
        screen.blit(surf, surf.get_rect(center=self.rect.center))


class Slider:
    def __init__(self, rect, label, get, setf, minv, maxv, step=1):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.get = get
        self.setf = setf
        self.minv = minv
        self.maxv = maxv
        self.step = step
        self.drag = False

    def value(self):
        return self.get()

    def pos_to_val(self, x):
        t = (x - self.rect.x) / max(1, self.rect.w)
        t = max(0.0, min(1.0, t))
        v = self.minv + t * (self.maxv - self.minv)
        if self.step >= 1:
            v = round(v / self.step) * self.step
        return int(v) if self.step == int(self.step) else v

    def val_to_pos(self, v):
        t = (v - self.minv) / max(1e-6, self.maxv - self.minv)
        t = max(0.0, min(1.0, t))
        return self.rect.x + int(t * self.rect.w)

    def handle(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.rect.collidepoint(e.pos):
                self.drag = True
                self.setf(self.pos_to_val(e.pos[0]))
                return True
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if self.drag:
                self.drag = False
                return True
        elif e.type == pygame.MOUSEMOTION and self.drag:
            self.setf(self.pos_to_val(e.pos[0]))
            return True
        return False

    def draw(self, screen, font):
        pygame.draw.rect(screen, (40, 44, 54), self.rect, border_radius=4)
        pygame.draw.rect(screen, (90, 96, 112), self.rect, 1, border_radius=4)
        v = self.value()
        cx = self.val_to_pos(v)
        pygame.draw.circle(screen, (255, 215, 0), (cx, self.rect.centery), 8)
        lbl = font.render(f"{self.label}: {v}", True, (200, 206, 218))
        screen.blit(lbl, (self.rect.x, self.rect.y - 22))


class Toggle:
    def __init__(self, rect, label, get, setf):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.get = get
        self.setf = setf

    def handle(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos):
            return True
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.rect.collidepoint(e.pos):
            self.setf(not self.get())
            return True
        return False

    def draw(self, screen, font):
        on = self.get()
        bg = (58, 128, 92) if on else (60, 66, 78)
        pygame.draw.rect(screen, bg, self.rect, border_radius=4)
        pygame.draw.rect(screen, (255, 215, 0) if on else (105, 112, 126), self.rect, 2 if on else 1, border_radius=4)
        lbl = font.render(f"{self.label}: {'ВКЛ' if on else 'ВЫКЛ'}", True, (225, 230, 240))
        screen.blit(lbl, (self.rect.x + 10, self.rect.centery - lbl.get_height() // 2))


class PauseMenu:
    def __init__(self, screen_size, on_resume, on_quit):
        self.w, self.h = screen_size
        self.on_resume = on_resume
        self.on_quit = on_quit
        self.cfg = settings.load()
        self.tab = "main"
        self.font = pygame.font.SysFont(None, 28)
        self.font_title = pygame.font.SysFont(None, 48, bold=True)
        self.font_small = pygame.font.SysFont(None, 22)
        cx = self.w // 2
        cy = self.h // 2
        self.btn_resume = Button((cx - 150, cy - 40, 300, 44), "Продолжить", self._resume)
        self.btn_graph = Button((cx - 150, cy + 14, 300, 44), "Графика", self._graph)
        self.btn_quit = Button((cx - 150, cy + 68, 300, 44), "Выйти в меню", self._quit)
        self.back = Button((cx - 150, self.h - 110, 300, 44), "Назад", self._back)
        self.slider_cull = Slider((cx - 200, cy - 80, 400, 6), "Радиус отсечения света", 
                                   lambda: self.cfg.get("light_cull_margin", 32),
                                   lambda v: self._set("light_cull_margin", int(v)),
                                   0, 256, 8)
        self.toggle_blur = Toggle((cx - 200, cy - 10, 400, 36), "Блюр света",
                                   lambda: self.cfg.get("light_blur", True),
                                   lambda v: self._set("light_blur", bool(v)))
        self.toggle_fps = Toggle((cx - 200, cy + 40, 400, 36), "Показывать FPS",
                                   lambda: self.cfg.get("show_fps", True),
                                   lambda v: self._set("show_fps", bool(v)))
        self._last = None

    def _set(self, k, v):
        self.cfg[k] = v
        settings.save(self.cfg)

    def _resume(self):
        if self.on_resume:
            self.on_resume()

    def _graph(self):
        self.tab = "graphics"

    def _back(self):
        self.tab = "main"

    def _quit(self):
        if self.on_quit:
            self.on_quit()

    def handle(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            if self.tab == "graphics":
                self.tab = "main"
            else:
                self._resume()
            return True
        if self.tab == "main":
            self.btn_resume.handle(e)
            self.btn_graph.handle(e)
            self.btn_quit.handle(e)
        else:
            self.slider_cull.handle(e)
            self.toggle_blur.handle(e)
            self.toggle_fps.handle(e)
            self.back.handle(e)
        return True

    def draw(self, screen):
        size = screen.get_size()
        if self._last != size:
            self.w, self.h = size
            cx = self.w // 2
            cy = self.h // 2
            self.btn_resume.rect = pygame.Rect(cx - 150, cy - 40, 300, 44)
            self.btn_graph.rect = pygame.Rect(cx - 150, cy + 14, 300, 44)
            self.btn_quit.rect = pygame.Rect(cx - 150, cy + 68, 300, 44)
            self.back.rect = pygame.Rect(cx - 150, self.h - 110, 300, 44)
            self.slider_cull.rect = pygame.Rect(cx - 200, cy - 80, 400, 6)
            self.toggle_blur.rect = pygame.Rect(cx - 200, cy - 10, 400, 36)
            self.toggle_fps.rect = pygame.Rect(cx - 200, cy + 40, 400, 36)
            self._last = size
        overlay = pygame.Surface(size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        screen.blit(overlay, (0, 0))
        cx = self.w // 2
        if self.tab == "main":
            title = self.font_title.render("ПАУЗА", True, (235, 238, 245))
            screen.blit(title, title.get_rect(center=(cx, self.h // 2 - 120)))
            self.btn_resume.draw(screen, self.font)
            self.btn_graph.draw(screen, self.font)
            self.btn_quit.draw(screen, self.font)
        else:
            title = self.font_title.render("НАСТРОЙКИ ГРАФИКИ", True, (235, 238, 245))
            screen.blit(title, title.get_rect(center=(cx, self.h // 2 - 150)))
            self.slider_cull.draw(screen, self.font_small)
            self.toggle_blur.draw(screen, self.font)
            self.toggle_fps.draw(screen, self.font)
            self.back.draw(screen, self.font)
