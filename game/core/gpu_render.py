import ctypes
import math
import os
import sys

import moderngl
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LIB_EXT = ".dll" if os.name == "nt" else (".dylib" if sys.platform == "darwin" else ".so")
_DLL_PATH = os.path.join(_ROOT, "libraries", "render" + _LIB_EXT)

_SOLID_VERT = """
#version 330
in vec2 in_pos;
in vec4 in_color;
uniform vec2 screen_size;
out vec4 v_color;
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
void main() { f_color = v_color; }
"""

_SPRITE_VERT = """
#version 330
in vec2 in_pos;
in vec2 in_uv;
uniform vec2 screen_size;
out vec2 v_uv;
void main() {
  vec2 ndc = (in_pos / screen_size) * 2.0 - 1.0;
  ndc.y = -ndc.y;
  gl_Position = vec4(ndc, 0.0, 1.0);
  v_uv = in_uv;
}
"""

_SPRITE_FRAG = """
#version 330
uniform sampler2D tex;
in vec2 v_uv;
out vec4 f_color;
void main() { f_color = texture(tex, v_uv); }
"""

class _CBatch(ctypes.Structure):
  _fields_ = [
    ("verts", ctypes.POINTER(ctypes.c_float)),
    ("n_verts", ctypes.c_int),
    ("cap_verts", ctypes.c_int),
  ]

_lib_cache = None

def _lib():
  global _lib_cache
  if _lib_cache is not None:
    return _lib_cache
  if not os.path.exists(_DLL_PATH):
    raise RuntimeError("render.dll missing at " + _DLL_PATH)
  lib = ctypes.CDLL(_DLL_PATH)
  lib.solid_init.argtypes = [ctypes.POINTER(_CBatch), ctypes.c_int]
  lib.solid_init.restype = None
  lib.solid_free.argtypes = [ctypes.POINTER(_CBatch)]
  lib.solid_free.restype = None
  lib.solid_reset.argtypes = [ctypes.POINTER(_CBatch)]
  lib.solid_reset.restype = None
  lib.solid_count.argtypes = [ctypes.POINTER(_CBatch)]
  lib.solid_count.restype = ctypes.c_int
  lib.solid_data.argtypes = [ctypes.POINTER(_CBatch)]
  lib.solid_data.restype = ctypes.POINTER(ctypes.c_float)
  lib.solid_rect.argtypes = [ctypes.POINTER(_CBatch), ctypes.c_float, ctypes.c_float,
                             ctypes.c_float, ctypes.c_float, ctypes.c_uint32]
  lib.solid_rect.restype = None
  lib.solid_tri.argtypes = [ctypes.POINTER(_CBatch), ctypes.c_float, ctypes.c_float,
                            ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float,
                            ctypes.c_uint32]
  lib.solid_tri.restype = None
  lib.solid_circle.argtypes = [ctypes.POINTER(_CBatch), ctypes.c_float, ctypes.c_float,
                               ctypes.c_float, ctypes.c_int, ctypes.c_uint32]
  lib.solid_circle.restype = None
  lib.solid_ring.argtypes = [ctypes.POINTER(_CBatch), ctypes.c_float, ctypes.c_float,
                             ctypes.c_float, ctypes.c_float, ctypes.c_int, ctypes.c_uint32]
  lib.solid_ring.restype = None
  lib.solid_line.argtypes = [ctypes.POINTER(_CBatch), ctypes.c_float, ctypes.c_float,
                             ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_uint32]
  lib.solid_line.restype = None
  lib.solid_polygon.argtypes = [ctypes.POINTER(_CBatch), ctypes.POINTER(ctypes.c_float),
                                ctypes.c_int, ctypes.c_uint32]
  lib.solid_polygon.restype = None
  lib.solid_polygon_outline.argtypes = [ctypes.POINTER(_CBatch), ctypes.POINTER(ctypes.c_float),
                                        ctypes.c_int, ctypes.c_float, ctypes.c_uint32]
  lib.solid_polygon_outline.restype = None
  _lib_cache = lib
  return lib

def _rgba(color, alpha=255):
  r = max(0, min(255, int(color[0])))
  g = max(0, min(255, int(color[1])))
  b = max(0, min(255, int(color[2])))
  a = max(0, min(255, int(alpha)))
  return r | (g << 8) | (b << 16) | (a << 24)

class _AlphaScope:
  def __init__(self, ctx, mul):
    self.ctx = ctx
    self.mul = mul
    self.prev = 1.0
  def __enter__(self):
    self.prev = self.ctx._alpha
    self.ctx._alpha = self.prev * self.mul
    return self.ctx
  def __exit__(self, *a):
    self.ctx._alpha = self.prev
    return False

class WorldCtx:
  # pygame.draw-compatible surface for entities; coordinates are SCREEN pixels
  def __init__(self, renderer, cam):
    self._r = renderer
    self.cam = cam
    self.scale = cam.scale
    self.width, self.height = renderer.size
    self._alpha = 1.0

  def to_screen(self, wx, wy):
    return self.cam.to_screen(wx, wy)
  def from_screen(self, sx, sy):
    return self.cam.from_screen(sx, sy)
  def get_size(self):
    return (self.width, self.height)
  def get_width(self):
    return self.width
  def get_height(self):
    return self.height
  def fill(self, color, rect=None):
    self._r.bg = tuple(color[:3])
  def alpha_scope(self, mul):
    return _AlphaScope(self, mul)

  def rect(self, x, y, w, h, color, alpha=255):
    self._r.solid_rect(x, y, w, h, _rgba(color, alpha * self._alpha))

  def circle(self, cx, cy, r, color, alpha=255, segments=24):
    self._r.solid_circle(cx, cy, r, segments, _rgba(color, alpha * self._alpha))

  def ring(self, cx, cy, r, width, color, alpha=255, segments=32):
    self._r.solid_ring(cx, cy, r - width, r, segments, _rgba(color, alpha * self._alpha))

  def line(self, x0, y0, x1, y1, width, color, alpha=255):
    self._r.solid_line(x0, y0, x1, y1, width, _rgba(color, alpha * self._alpha))

  def polygon(self, pts, color, alpha=255, width=0):
    a = alpha * self._alpha
    if width and width > 0:
      self._r.solid_polygon_outline(pts, width, _rgba(color, a))
    else:
      self._r.solid_polygon(pts, _rgba(color, a))

  def blit(self, surf, pos):
    try:
      import pygame as _pg
      w, h = surf.get_size()
      if w <= 0 or h <= 0:
        return
      data = _pg.image.tobytes(surf, "RGBA", False)
      self._r._sprites.append((data, w, h, float(pos[0]), float(pos[1])))
    except Exception as e:
      print("WorldCtx.blit failed:", e)

class WorldRenderer:
  MAX_VERTS = 512 * 1024

  def __init__(self, gl_ctx, size, bg=(89, 95, 102)):
    self.gl_ctx = gl_ctx
    self.size = size
    self.bg = bg
    self._lib = _lib()
    self._batch = _CBatch()
    self._byref = ctypes.byref(self._batch)
    self._lib.solid_init(self._byref, self.MAX_VERTS)
    if self._batch.cap_verts <= 0:
      raise RuntimeError("solid_init failed")

    self.solid_prog = gl_ctx.program(vertex_shader=_SOLID_VERT, fragment_shader=_SOLID_FRAG)
    self.solid_vbo = gl_ctx.buffer(reserve=self.MAX_VERTS * 6 * 4, dynamic=True)
    self.solid_vao = gl_ctx.vertex_array(
      self.solid_prog, [(self.solid_vbo, "2f 4f", "in_pos", "in_color")])

    self.scene_tex = gl_ctx.texture(size, 4)
    self.scene_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
    self.scene_fbo = gl_ctx.framebuffer(color_attachments=[self.scene_tex])

    self.sprites_prog = gl_ctx.program(vertex_shader=_SPRITE_VERT, fragment_shader=_SPRITE_FRAG)
    self.sprites_vbo = gl_ctx.buffer(reserve=6 * 4 * 4, dynamic=True)
    self.sprites_vao = gl_ctx.vertex_array(
      self.sprites_prog, [(self.sprites_vbo, "2f 2f", "in_pos", "in_uv")])
    self._sprites = []

  def _flat(self, pts):
    n = len(pts)
    arr = (ctypes.c_float * (n * 2))()
    for i, (x, y) in enumerate(pts):
      arr[i * 2] = float(x)
      arr[i * 2 + 1] = float(y)
    return arr, n

  def solid_rect(self, x, y, w, h, rgba):
    self._lib.solid_rect(self._byref, x, y, w, h, rgba)
  def solid_circle(self, cx, cy, r, segs, rgba):
    self._lib.solid_circle(self._byref, cx, cy, r, segs, rgba)
  def solid_ring(self, cx, cy, r_in, r_out, segs, rgba):
    self._lib.solid_ring(self._byref, cx, cy, r_in, r_out, segs, rgba)
  def solid_line(self, x0, y0, x1, y1, thick, rgba):
    self._lib.solid_line(self._byref, x0, y0, x1, y1, thick, rgba)
  def solid_polygon(self, pts, rgba):
    arr, n = self._flat(pts)
    self._lib.solid_polygon(self._byref, arr, n, rgba)
  def solid_polygon_outline(self, pts, thick, rgba):
    arr, n = self._flat(pts)
    self._lib.solid_polygon_outline(self._byref, arr, n, thick, rgba)

  def begin(self):
    self._lib.solid_reset(self._byref)
    self._sprites.clear()
    self.scene_fbo.use()
    self.gl_ctx.viewport = (0, 0, *self.size)
    r, g, b = self.bg
    self.gl_ctx.clear(r / 255.0, g / 255.0, b / 255.0, 1.0)

  def flush(self):
    n = self._lib.solid_count(self._byref)
    if n > 0:
      ptr = self._lib.solid_data(self._byref)
      addr = ctypes.cast(ptr, ctypes.c_void_p).value
      data = ctypes.string_at(addr, n * 6 * 4)
      self.solid_vbo.write(data)
      self.gl_ctx.enable(moderngl.BLEND)
      self.gl_ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
      self.solid_prog["screen_size"] = self.size
      self.solid_vao.render(moderngl.TRIANGLES, vertices=n)
    # sprites after solids, still on scene_fbo
    if self._sprites:
      self.gl_ctx.enable(moderngl.BLEND)
      self.gl_ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
      self.sprites_prog["screen_size"] = self.size
      for data, w, h, x, y in self._sprites:
        tex = self.gl_ctx.texture((w, h), 4, data)
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        verts = np.array([
          x,     y,     0.0, 0.0,
          x + w, y,     1.0, 0.0,
          x + w, y + h, 1.0, 1.0,
          x,     y,     0.0, 0.0,
          x + w, y + h, 1.0, 1.0,
          x,     y + h, 0.0, 1.0,
        ], dtype="f4")
        self.sprites_vbo.write(verts.tobytes())
        tex.use(0)
        self.sprites_prog["tex"] = 0
        self.sprites_vao.render(moderngl.TRIANGLES, vertices=6)
        tex.release()
      self._sprites.clear()
    self.gl_ctx.screen.use()

  def release(self):
    self._lib.solid_free(self._byref)
    self.scene_fbo.release()
    self.scene_tex.release()
    self.solid_vbo.release()
    self.solid_vao.release()
