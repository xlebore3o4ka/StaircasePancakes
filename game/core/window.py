import pygame

DESIGN_H = 1080


class Window:
  def __enter__(self):
    pygame.init()
    # <STRANGE>#1406 try ModernGL via OPENGL display mode; fall back to plain software display
    self.gl_mode = False
    try:
      _ = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.OPENGL | pygame.DOUBLEBUF, vsync=1)
      info = pygame.display.Info()
      size = (info.current_w, info.current_h)
      self.gl_mode = True
    except Exception as e:
      print(f"window: OPENGL mode failed ({e}); software fallback")
      _ = pygame.display.set_mode((0, 0), pygame.FULLSCREEN, vsync=1)
      size = pygame.display.get_surface().get_size()
    self.screen = pygame.Surface(size).convert()
    self.scale = size[1] / DESIGN_H
    from .lighting import LightingPipeline
    self.lighting = LightingPipeline(size)
    if self.lighting.has_gl:
      from .hud_renderer import HudRenderer
      try:
        self.hud = HudRenderer(self.lighting.gl_ctx, size)
      except Exception as e:
        print(f"window: HudRenderer init failed ({e}); pygame HUD fallback")
        from .hud_renderer import HudFallback
        self.hud = HudFallback(size)
    else:
      print("window: ModernGL unavailable, software lighting fallback active")
      from .hud_renderer import HudFallback
      self.hud = HudFallback(size)
    return self

  def __exit__(self, *exc):
    pygame.quit()

  def flip(self):
    if self.lighting.has_gl:
      self.lighting.present(self.screen)
      self.hud.flush()
    else:
      self.lighting.present_software(self.screen, getattr(self.hud, "surf", None))
    pygame.display.flip()
