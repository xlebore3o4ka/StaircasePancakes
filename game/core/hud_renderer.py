import math
import pygame

try:
    import moderngl
    import numpy as np
    _GL_OK = True
except Exception:
    _GL_OK = False


_SOLID_VERT = """
#version 330
in vec2 in_pos;
in vec4 in_color;
out vec4 v_color;
uniform vec2 screen_size;
void main() {
    vec2 ndc = (in_pos / screen_size) * 2.0 - 1.0;
    ndc.y = -ndc.y;
    gl_Position = vec4(ndc, 0.0, 1.0);
    v_color = in_color;
}
"""

_SOLID_FRAG = """
#version 330
in vec4 v_color;
out vec4 f_color;
void main() {
    f_color = v_color;
}
"""

_SPRITE_VERT = """
#version 330
in vec2 in_pos;
in vec2 in_uv;
in vec4 in_color;
out vec2 v_uv;
out vec4 v_color;
uniform vec2 screen_size;
void main() {
    vec2 ndc = (in_pos / screen_size) * 2.0 - 1.0;
    ndc.y = -ndc.y;
    gl_Position = vec4(ndc, 0.0, 1.0);
    v_uv = in_uv;
    v_color = in_color;
}
"""

_SPRITE_FRAG = """
#version 330
uniform sampler2D tex;
in vec2 v_uv;
in vec4 v_color;
out vec4 f_color;
void main() {
    f_color = texture(tex, v_uv) * v_color;
}
"""


class _InnerCam:
  def __init__(self, scale):
    self.scale = scale
  def to_screen(self, x, y):
    return (x, y)


class HudRenderer:
  # <STRANGE>#1500 batched GL HUD; no full-screen texture upload per frame
  MAX_SOLID_FLOATS = 1024 * 1024
  MAX_SPRITE_FLOATS = 1024 * 1024
  MAX_TEXT_CACHE = 512

  def __init__(self, gl_ctx, size):
    self.gl_ctx = gl_ctx
    self.size = size
    self.solid_prog = gl_ctx.program(vertex_shader=_SOLID_VERT, fragment_shader=_SOLID_FRAG)
    self.sprite_prog = gl_ctx.program(vertex_shader=_SPRITE_VERT, fragment_shader=_SPRITE_FRAG)
    self.solid_vbo = gl_ctx.buffer(reserve=self.MAX_SOLID_FLOATS * 4, dynamic=True)
    self.sprite_vbo = gl_ctx.buffer(reserve=self.MAX_SPRITE_FLOATS * 4, dynamic=True)
    self.solid_vao = gl_ctx.vertex_array(
      self.solid_prog, [(self.solid_vbo, "2f 4f", "in_pos", "in_color")])
    self.sprite_vao = gl_ctx.vertex_array(
      self.sprite_prog, [(self.sprite_vbo, "2f 2f 4f", "in_pos", "in_uv", "in_color")])
    self.text_cache = {}
    self._solid_np = np.zeros((self.MAX_SOLID_FLOATS,), dtype="f4")
    self._solid_count = 0
    self._sprites = []
    self._temp_tex = []

  def get_size(self):
    return self.size

  def begin(self):
    # <STRANGE>#1510 release previous frame's temp textures here, safer than in flush
    for tex in self._temp_tex:
      try:
        tex.release()
      except Exception:
        pass
    self._temp_tex = []
    self._solid_count = 0
    self._sprites = []

  def _tri(self, p0, p1, p2, col):
    b = self._solid_count
    a = self._solid_np
    a[b] = p0[0]; a[b+1] = p0[1]; a[b+2] = col[0]; a[b+3] = col[1]; a[b+4] = col[2]; a[b+5] = col[3]
    a[b+6] = p1[0]; a[b+7] = p1[1]; a[b+8] = col[0]; a[b+9] = col[1]; a[b+10] = col[2]; a[b+11] = col[3]
    a[b+12] = p2[0]; a[b+13] = p2[1]; a[b+14] = col[0]; a[b+15] = col[1]; a[b+16] = col[2]; a[b+17] = col[3]
    self._solid_count += 18

  def circle(self, cx, cy, r, color, alpha=255, segments=24):
    cx, cy, r = float(cx), float(cy), float(r)
    col = (color[0] / 255.0, color[1] / 255.0, color[2] / 255.0, alpha / 255.0)
    for i in range(segments):
      a0 = i / segments * math.tau
      a1 = (i + 1) / segments * math.tau
      p0 = (cx + r * math.cos(a0), cy + r * math.sin(a0))
      p1 = (cx + r * math.cos(a1), cy + r * math.sin(a1))
      self._tri((cx, cy), p0, p1, col)

  def ring(self, cx, cy, r, width, color, alpha=255, segments=32):
    cx, cy, r, width = float(cx), float(cy), float(r), float(width)
    r_in = max(0.0, r - width)
    col = (color[0] / 255.0, color[1] / 255.0, color[2] / 255.0, alpha / 255.0)
    for i in range(segments):
      a0 = i / segments * math.tau
      a1 = (i + 1) / segments * math.tau
      o0 = (cx + r * math.cos(a0), cy + r * math.sin(a0))
      o1 = (cx + r * math.cos(a1), cy + r * math.sin(a1))
      i0 = (cx + r_in * math.cos(a0), cy + r_in * math.sin(a0))
      i1 = (cx + r_in * math.cos(a1), cy + r_in * math.sin(a1))
      self._tri(o0, o1, i1, col)
      self._tri(o0, i1, i0, col)

  def rect(self, x, y, w, h, color, alpha=255):
    col = (color[0] / 255.0, color[1] / 255.0, color[2] / 255.0, alpha / 255.0)
    p0 = (float(x), float(y))
    p1 = (float(x + w), float(y))
    p2 = (float(x + w), float(y + h))
    p3 = (float(x), float(y + h))
    self._tri(p0, p1, p2, col)
    self._tri(p0, p2, p3, col)

  def text(self, text, x, y, size, color, alpha=255, anchor="center"):
    key = (str(text), int(size), tuple(color[:3]))
    if key not in self.text_cache:
      try:
        font = pygame.font.SysFont("consolas", int(size))
        src = font.render(str(text), True, color[:3])
        w, h = src.get_size()
        if w <= 0 or h <= 0:
          return
        # <STRANGE>#1511 force RGBA by blitting into fresh SRCALPHA surface
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.blit(src, (0, 0))
        data = pygame.image.tobytes(surf, "RGBA", False)
        if len(data) != w * h * 4:
          print(f"hud.text: data size mismatch {len(data)} vs {w*h*4} for {text!r}")
          return
        tex = self.gl_ctx.texture((w, h), 4)
        if tex is None:
          return
        tex.write(data)
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.text_cache[key] = (tex, w, h)
        if len(self.text_cache) > self.MAX_TEXT_CACHE:
          old_key = next(iter(self.text_cache))
          if old_key != key:
            old_tex, _, _ = self.text_cache.pop(old_key)
            try:
              old_tex.release()
            except Exception:
              pass
      except Exception as e:
        print(f"hud.text failed for {text!r}: {e}")
        return
    tex, w, h = self.text_cache[key]
    self._blit_tex(tex, w, h, x, y, alpha, anchor)

  def surface(self, surf, x, y, alpha=255, anchor="topleft"):
    try:
      w, h = surf.get_size()
      if w <= 0 or h <= 0:
        return
      data = pygame.image.tobytes(surf, "RGBA", False)
      if len(data) != w * h * 4:
        return
      tex = self.gl_ctx.texture((w, h), 4)
      if tex is None:
        return
      tex.write(data)
      tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
      self._blit_tex(tex, w, h, x, y, alpha, anchor)
      self._temp_tex.append(tex)
    except Exception as e:
      print(f"hud.surface failed: {e}")

  def item_at(self, item, x, y, alpha=255, scale=1.0, whiten=0.0, y_up=True, cam_scale=1.0):
    extent = max(item.w, item.h) * cam_scale * scale
    surf_size = int(extent * 2) + 20
    if surf_size < 8:
      surf_size = 8
    surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
    inner = _InnerCam(cam_scale * scale)
    item.draw_at(surf, inner, (surf_size // 2, surf_size // 2),
                 0.0, alpha, 1.0, whiten=whiten, y_up=y_up)
    self.surface(surf, x - surf_size // 2, y - surf_size // 2, anchor="topleft")

  def _blit_tex(self, tex, w, h, x, y, alpha, anchor):
    x, y = float(x), float(y)
    if anchor == "center":
      x0, y0 = x - w / 2, y - h / 2
    elif anchor == "topright":
      x0, y0 = x - w, y
    else:
      x0, y0 = x, y
    x1, y1 = x0 + w, y0 + h
    a = alpha / 255.0
    data = np.array([
      x0, y0, 0, 0, 1, 1, 1, a,
      x1, y0, 1, 0, 1, 1, 1, a,
      x1, y1, 1, 1, 1, 1, 1, a,
      x0, y0, 0, 0, 1, 1, 1, a,
      x1, y1, 1, 1, 1, 1, 1, a,
      x0, y1, 0, 1, 1, 1, 1, a,
    ], dtype="f4")
    self._sprites.append((tex, data))

  def flush(self):
    self.gl_ctx.enable(moderngl.BLEND)
    self.gl_ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
    self.solid_prog["screen_size"] = self.size
    if self._solid_count > 0:
      try:
        self.solid_vbo.write(self._solid_np[:self._solid_count].tobytes())
        self.solid_vao.render(moderngl.TRIANGLES, vertices=self._solid_count // 6)
      except Exception as e:
        print(f"hud.flush solid failed: {e}")
    self.sprite_prog["screen_size"] = self.size
    for tex, data in self._sprites:
      try:
        self.sprite_vbo.write(data.tobytes())
        tex.use(0)
        self.sprite_prog["tex"] = 0
        self.sprite_vao.render(moderngl.TRIANGLES, vertices=6)
      except Exception as e:
        print(f"hud.flush sprite failed: {e}")
        continue


class HudFallback:
  # <STRANGE>#1501 API-compatible pygame fallback; same draw calls, pygame surface internally
  def __init__(self, size):
    self.size = size
    self.surf = pygame.Surface(size, pygame.SRCALPHA)
    self._text_cache = {}

  def get_size(self):
    return self.size

  def begin(self):
    self.surf.fill((0, 0, 0, 0))

  def circle(self, cx, cy, r, color, alpha=255, segments=24):
    if r <= 0:
      return
    pygame.draw.circle(self.surf, (*color[:3], alpha), (int(cx), int(cy)), int(r))

  def ring(self, cx, cy, r, width, color, alpha=255, segments=32):
    if r <= 0 or width <= 0:
      return
    pygame.draw.circle(self.surf, (*color[:3], alpha), (int(cx), int(cy)), int(r), int(width))

  def rect(self, x, y, w, h, color, alpha=255):
    if w <= 0 or h <= 0:
      return
    s = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
    s.fill((*color[:3], alpha))
    self.surf.blit(s, (int(x), int(y)))

  def text(self, text, x, y, size, color, alpha=255, anchor="center"):
    key = (str(text), int(size), tuple(color[:3]))
    if key not in self._text_cache:
      font = pygame.font.SysFont("consolas", int(size))
      self._text_cache[key] = font.render(str(text), True, color[:3])
    s = self._text_cache[key]
    s.set_alpha(alpha)
    rect = s.get_rect()
    if anchor == "center":
      rect.center = (int(x), int(y))
    elif anchor == "topright":
      rect.topright = (int(x), int(y))
    else:
      rect.topleft = (int(x), int(y))
    self.surf.blit(s, rect)

  def surface(self, surf, x, y, alpha=255, anchor="topleft"):
    s = surf
    if alpha < 255:
      s = surf.copy()
      s.set_alpha(alpha)
    rect = s.get_rect()
    if anchor == "center":
      rect.center = (int(x), int(y))
    elif anchor == "topright":
      rect.topright = (int(x), int(y))
    else:
      rect.topleft = (int(x), int(y))
    self.surf.blit(s, rect)

  def item_at(self, item, x, y, alpha=255, scale=1.0, whiten=0.0, y_up=True, cam_scale=1.0):
    extent = max(item.w, item.h) * cam_scale * scale
    surf_size = int(extent * 2) + 20
    if surf_size < 8:
      surf_size = 8
    surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
    inner = _InnerCam(cam_scale * scale)
    item.draw_at(surf, inner, (surf_size // 2, surf_size // 2),
                 0.0, alpha, 1.0, whiten=whiten, y_up=y_up)
    self.surf.blit(surf, (int(x - surf_size // 2), int(y - surf_size // 2)))

  def flush(self):
    pass
