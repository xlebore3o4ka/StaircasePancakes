import pygame
import math

try:
    import moderngl
    import numpy as np
    _GL_OK = True
except Exception as _e:
    print(f"lighting: moderngl/numpy unavailable ({_e}); software fallback")
    _GL_OK = False


LIGHT_SCALE = 2


_VERT = """
#version 330
in vec2 in_vert;
in vec2 in_uv;
out vec2 v_uv;
void main() {
    v_uv = in_uv;
    gl_Position = vec4(in_vert, 0.0, 1.0);
}
"""

_FRAG_BLUR = """
#version 330
uniform sampler2D tex;
uniform vec2 texel;
uniform vec2 dir;
in vec2 v_uv;
out vec4 f_color;
void main() {
    vec4 c = texture(tex, v_uv).rgba * 0.2270270270;
    c += texture(tex, v_uv + dir * texel * 1.3846153846).rgba * 0.3162162162;
    c += texture(tex, v_uv - dir * texel * 1.3846153846).rgba * 0.3162162162;
    c += texture(tex, v_uv + dir * texel * 3.2307692308).rgba * 0.0702702703;
    c += texture(tex, v_uv - dir * texel * 3.2307692308).rgba * 0.0702702703;
    f_color = c;
}
"""

_FRAG_LIGHT = """
#version 330
uniform sampler2D scene_tex;
uniform sampler2D light_tex;
uniform vec2 uv_offset;
uniform float gain;
in vec2 v_uv;
out vec4 f_color;
void main() {
    vec3 scene = texture(scene_tex, v_uv).rgb;
    vec3 light = texture(light_tex, v_uv + uv_offset).rgb;
    vec3 lit = scene * light * gain;
    f_color = vec4(clamp(lit, 0.0, 1.0), 1.0);
}
"""

_FRAG_HUD = """
#version 330
uniform sampler2D hud_tex;
in vec2 v_uv;
out vec4 f_color;
void main() {
    f_color = texture(hud_tex, v_uv);
}
"""


class LightingPipeline:
  def __init__(self, size):
    self.size = size
    self.light_size = (max(1, size[0] // LIGHT_SCALE), max(1, size[1] // LIGHT_SCALE))
    self.light = pygame.Surface(self.light_size)
    self.light.fill((255, 255, 255))
    self.gain = 1.0
    self._light_key = None
    self._light_dirty = True
    self._uv_offset = (0.0, 0.0)
    self.gl_ctx = None
    self._blur_fbo = None
    self._blur_tex = None
    if not _GL_OK:
      return
    try:
      self.gl_ctx = moderngl.create_context()
    except Exception as e:
      print(f"lighting: create_context failed ({e}); software fallback")
      self.gl_ctx = None
      return
    try:
      self.prog_blur = self.gl_ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG_BLUR)
      self.prog_light = self.gl_ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG_LIGHT)
      self.prog_hud = self.gl_ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG_HUD)
    except Exception as e:
      print(f"lighting: shader compile failed ({e}); software fallback")
      self.gl_ctx = None
      return
    verts = np.array([
      -1.0, -1.0, 0.0, 1.0,
       1.0, -1.0, 1.0, 1.0,
      -1.0,  1.0, 0.0, 0.0,
       1.0,  1.0, 1.0, 0.0,
    ], dtype="f4")
    vbo = self.gl_ctx.buffer(verts.tobytes())
    self.vao_blur = self.gl_ctx.vertex_array(self.prog_blur, [(vbo, "2f 2f", "in_vert", "in_uv")])
    self.vao_light = self.gl_ctx.vertex_array(self.prog_light, [(vbo, "2f 2f", "in_vert", "in_uv")])
    self.vao_hud = self.gl_ctx.vertex_array(self.prog_hud, [(vbo, "2f 2f", "in_vert", "in_uv")])
    self.scene_tex = self.gl_ctx.texture(size, 3)
    self.light_tex_raw = self.gl_ctx.texture(self.light_size, 3)
    self.light_tex_raw.filter = (moderngl.LINEAR, moderngl.LINEAR)
    self.light_tex_raw.repeat_x = False
    self.light_tex_raw.repeat_y = False
    # <STRANGE>#1430 ping-pong blur: two textures + two FBOs, no read-write feedback
    self.blur_tex_A = self.gl_ctx.texture(self.light_size, 3)
    self.blur_tex_A.filter = (moderngl.LINEAR, moderngl.LINEAR)
    self.blur_tex_A.repeat_x = False
    self.blur_tex_A.repeat_y = False
    self.blur_tex_B = self.gl_ctx.texture(self.light_size, 3)
    self.blur_tex_B.filter = (moderngl.LINEAR, moderngl.LINEAR)
    self.blur_tex_B.repeat_x = False
    self.blur_tex_B.repeat_y = False
    self.fbo_blur_A = self.gl_ctx.framebuffer(color_attachments=[self.blur_tex_A])
    self.fbo_blur_B = self.gl_ctx.framebuffer(color_attachments=[self.blur_tex_B])

  @property
  def has_gl(self):
    return self.gl_ctx is not None

  def _compute_key(self, config, lights, cam_scale, sx, sy, sox, soy, occluders):
    parts = [tuple(config.get("ambient", (60, 60, 70))),
             float(config.get("gain", 1.0)),
             sx, sy, cam_scale, sox, soy,
             tuple((plat["bbox"], tuple(plat["edges"])) for plat in occluders)]
    for l in lights:
      parts.append((
        type(l).__name__,
        l.pos, tuple(l.color), l.intensity,
        getattr(l, "radius", 0.0),
        getattr(l, "angle", 0.0),
        getattr(l, "length", 0.0),
        getattr(l, "cone", 0.0),
        getattr(l, "direction", (0.0, 0.0)),
      ))
    return hash(tuple(parts))

  def setup(self, config, lights, cam, occluders):
    step = LIGHT_SCALE / max(1e-6, cam.scale)
    sx = round(cam.x / step) * step
    sy = round(cam.y / step) * step
    sox = round(cam._ox / LIGHT_SCALE) * LIGHT_SCALE
    soy = round(cam._oy / LIGHT_SCALE) * LIGHT_SCALE
    w, h = self.size
    self._uv_offset = (
      ((cam.x - sx) * cam.scale + (sox - cam._ox)) / w,
      ((sy - cam.y) * cam.scale + (soy - cam._oy)) / h,
    )
    key = self._compute_key(config, lights, cam.scale, sx, sy, sox, soy, occluders)
    if key == self._light_key:
      return
    self._light_key = key
    self._light_dirty = True
    self.gain = float(config.get("gain", 1.6))
    self.light.fill(config.get("ambient", (60, 60, 70)))
    light_cam = type(cam)(sx, sy, cam.w, cam.h, cam.scale / LIGHT_SCALE)
    light_cam._ox = sox / LIGHT_SCALE
    light_cam._oy = soy / LIGHT_SCALE
    for lt in lights:
      lt.contribute(self.light, light_cam, occluders)

  def begin(self, ambient=(255, 255, 255)):
    self._light_key = None
    self.light.fill(ambient)

  def present(self, scene_surf):
    if self.gl_ctx is None:
      return
    w, h = self.size
    try:
      scene_data = pygame.image.tobytes(scene_surf, "RGB", False)
    except Exception as e:
      print(f"lighting: tobytes failed ({e})")
      return
    self.scene_tex.write(scene_data)

    if self._light_dirty:
      light_data = pygame.image.tobytes(self.light, "RGB", False)
      self.light_tex_raw.write(light_data)
      texel = (1.0 / self.light_size[0], 1.0 / self.light_size[1])
      # <STRANGE>#1431 horizontal pass: raw -> tex_A
      self.gl_ctx.screen.use()
      self.fbo_blur_A.use()
      self.gl_ctx.clear(0.0, 0.0, 0.0, 1.0)
      self.light_tex_raw.use(0)
      self.prog_blur["tex"] = 0
      self.prog_blur["texel"] = texel
      self.prog_blur["dir"] = (1.0, 0.0)
      self.vao_blur.render(moderngl.TRIANGLE_STRIP)
      # <STRANGE>#1432 vertical pass: tex_A -> tex_B
      self.gl_ctx.screen.use()
      self.fbo_blur_B.use()
      self.gl_ctx.clear(0.0, 0.0, 0.0, 1.0)
      self.blur_tex_A.use(0)
      self.prog_blur["tex"] = 0
      self.prog_blur["dir"] = (0.0, 1.0)
      self.vao_blur.render(moderngl.TRIANGLE_STRIP)
      self.gl_ctx.screen.use()
      self._light_dirty = False

    self.gl_ctx.viewport = (0, 0, w, h)
    self.gl_ctx.clear(0.0, 0.0, 0.0, 1.0)
    self.gl_ctx.disable(moderngl.BLEND)
    self.scene_tex.use(0)
    self.blur_tex_B.use(1)
    self.prog_light["scene_tex"] = 0
    self.prog_light["light_tex"] = 1
    self.prog_light["gain"] = float(self.gain)
    self.prog_light["uv_offset"] = self._uv_offset
    self.vao_light.render(moderngl.TRIANGLE_STRIP)

  def present_software(self, scene_surf, hud_surf):
    disp = pygame.display.get_surface()
    if disp is None:
      return
    disp.blit(scene_surf, (0, 0))
    big_light = pygame.transform.smoothscale(self.light, scene_surf.get_size())
    disp.blit(big_light, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    if hud_surf is not None:
      disp.blit(hud_surf, (0, 0))
