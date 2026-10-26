import math
import pygame
try:
  import pygame.gfxdraw
  _HAS_GFX = True
except Exception:
  _HAS_GFX = False


def _fill_shadow(surf, pts, color):
  # <STRANGE>#1420 AA shadow fill; falls back to aliased draw.polygon if gfxdraw missing
  if _HAS_GFX:
    pygame.gfxdraw.filled_polygon(surf, pts, color)
    pygame.gfxdraw.aapolygon(surf, pts, color)
  else:
    pygame.draw.polygon(surf, color, pts)


class LightBase:
  # <STRANGE>#1402 base for light sources; contribute() paints additive light into light_surf
  def __init__(self, pos, color=(255, 240, 200), intensity=1.0):
    self.pos = pos
    self.color = color
    self.intensity = intensity
    self.id = None

  # <STRANGE>#1530 x/y accessors so Level.move_to and _snap work on lights (no .body needed)
  @property
  def x(self):
    return self.pos[0]

  @x.setter
  def x(self, v):
    self.pos = (v, self.pos[1])

  @property
  def y(self):
    return self.pos[1]

  @y.setter
  def y(self, v):
    self.pos = (self.pos[0], v)

  def contribute(self, light_surf, cam, occluders):
    pass


class SunLight(LightBase):
  # <STRANGE>#1403 uniform sky light; casts parallel shadows from each occluder segment
  def __init__(self, color=(200, 210, 240), intensity=0.5, direction=(0.5, 1.0), shadow_length=1000.0, gradient_length=100.0):
    super().__init__((0, 0), color, intensity)
    nx, ny = float(direction[0]), float(direction[1])
    mag = math.hypot(nx, ny)
    if mag > 0:
      self.direction = (nx / mag, ny / mag)
    else:
      self.direction = (0.0, 1.0)
    self.shadow_length = shadow_length
    self.gradient_length = gradient_length
    self._tint = None
    self._tint_key = None
    self._tmp = None

  def contribute(self, light_surf, cam, occluders):
    key = (tuple(self.color), float(self.intensity))
    sw, sh = light_surf.get_size()
    if self._tint is None or self._tint.get_size() != (sw, sh):
      self._tint = pygame.Surface((sw, sh))
      self._tint_key = None
    if self._tint_key != key:
      c = tuple(min(255, int(ch * self.intensity)) for ch in self.color)
      self._tint.fill(c)
      self._tint_key = key
    # <STRANGE>#1570 SunLight is uniform fill (no shadows), acts as soft ambient
    light_surf.blit(self._tint, (0, 0), special_flags=pygame.BLEND_RGB_MAX)


class LampLight(LightBase):
  # <STRANGE>#1404 radial light; caches a gradient surface, draws shadow quads to cut light behind platforms
  def __init__(self, pos, radius=300, color=(255, 200, 120), intensity=1.0):
    super().__init__(pos, color, intensity)
    self.radius = radius
    self._grad = None
    self._grad_r = 0
    self._tmp = None

  def _gradient(self, r):
    # <STRANGE>#1560 intensity/color in cache key so dynamic changes rebuild the gradient
    key = (r, round(self.intensity, 3), tuple(self.color))
    if self._grad is not None and self._grad_r == key:
      return self._grad
    # <STRANGE>#1421 tiny source, smoothscale up: no visible ring banding at any radius
    SMALL = 128
    tiny = pygame.Surface((SMALL, SMALL))
    tiny.fill((0, 0, 0))
    cr, cg, cb = self.color
    inten = self.intensity
    for i in range(SMALL, 0, -1):
      k = i / SMALL
      rad = max(1, int(SMALL / 2 * k))
      fall = 1.0 - k * k
      a = fall * inten
      # <STRANGE>#1740 clamp to [0, 255]; intensity > 1 would overflow pygame color range
      col = (min(255, int(cr * a)), min(255, int(cg * a)), min(255, int(cb * a)))
      if col == (0, 0, 0):
        continue
      pygame.draw.circle(tiny, col, (SMALL // 2, SMALL // 2), rad)
    target = max(1, r * 2)
    if target == SMALL:
      big = tiny
    else:
      big = pygame.transform.smoothscale(tiny, (target, target))
    self._grad = big
    self._grad_r = key
    return big

  def contribute(self, light_surf, cam, occluders):
    r = max(1, int(self.radius * cam.scale))
    cx, cy = cam.to_screen(self.pos[0], self.pos[1])
    sw, sh = light_surf.get_size()
    if cx + r < 0 or cx - r > sw or cy + r < 0 or cy - r > sh:
      return
    grad = self._gradient(r)
    rs = r * 2
    if self._tmp is None or self._tmp.get_size() != (rs, rs):
      self._tmp = pygame.Surface((rs, rs))
    tmp = self._tmp
    tmp.fill((0, 0, 0))
    tmp.blit(grad, (0, 0))
    if occluders:
      self._cut_shadows(tmp, cx, cy, r, occluders, cam)
    light_surf.blit(tmp, (int(cx - r), int(cy - r)), special_flags=pygame.BLEND_RGB_ADD)

  def _cut_shadows(self, tmp, cx, cy, r, occluders, cam):
    max_r = r * 3
    ox, oy = cx - r, cy - r
    # <STRANGE>#1671 world-space light pos for backface check; screen coords for drawing
    lwx, lwy = self.pos[0], self.pos[1]
    for plat in occluders:
      bb = plat["bbox"]
      inside = bb[0] <= lwx <= bb[2] and bb[1] <= lwy <= bb[3]
      for ax, ay, bx, by, nx, ny, nc_dot in plat["edges"]:
        if not inside:
          tlx, tly = lwx - ax, lwy - ay
          if (nx * tlx + ny * tly) * nc_dot >= 0:
            continue
        # <STRANGE>#1710 split edge at light projection: prevents bowtie when light
        # is near or inside the platform. Each half casts a proper shadow.
        ex = bx - ax
        ey = by - ay
        e2 = ex * ex + ey * ey
        if e2 < 1e-6:
          continue
        t_proj = ((lwx - ax) * ex + (lwy - ay) * ey) / e2
        n_norm = math.hypot(nx, ny)
        if n_norm > 1e-6:
          snx, sny = nx / n_norm, -ny / n_norm
        else:
          snx, sny = 0.0, -1.0
        if 0.0 < t_proj < 1.0:
          cxe = ax + t_proj * ex
          cye = ay + t_proj * ey
          sub_edges = ((ax, ay, cxe, cye), (cxe, cye, bx, by))
        else:
          sub_edges = ((ax, ay, bx, by),)
        for (s_ax, s_ay, s_bx, s_by) in sub_edges:
          sax, say = cam.to_screen(s_ax, s_ay)
          sbx, sby = cam.to_screen(s_bx, s_by)
          dx = sbx - sax
          dy = sby - say
          l2 = dx*dx + dy*dy
          if l2 > 1e-6:
            t = ((cx - sax) * dx + (cy - say) * dy) / l2
            t = 0.0 if t < 0 else (1.0 if t > 1 else t)
            px = sax + t * dx
            py = say + t * dy
            if (cx - px)**2 + (cy - py)**2 > (r * 2)**2:
              continue
          else:
            if (cx - sax)**2 + (cy - say)**2 > (r * 2)**2:
              continue
          dax, day = sax - cx, say - cy
          dbx, dby = sbx - cx, sby - cy
          la = math.hypot(dax, day)
          lb = math.hypot(dbx, dby)
          # <STRANGE>#1711 fallback to outward normal when an endpoint is on/very close to the light
          if la < 5.0:
            fax = cx + snx * max_r
            fay = cy + sny * max_r
          else:
            fax = cx + dax / la * max_r
            fay = cy + day / la * max_r
          if lb < 5.0:
            fbx = cx + snx * max_r
            fby = cy + sny * max_r
          else:
            fbx = cx + dbx / lb * max_r
            fby = cy + dby / lb * max_r
          pts = [
            (sax - ox, say - oy),
            (sbx - ox, sby - oy),
            (fbx - ox, fby - oy),
            (fax - ox, fay - oy)
          ]
          _fill_shadow(tmp, pts, (0, 0, 0))


class SpotLight(LightBase):
  # <STRANGE>#1405 cone light; angle rotates, length and cone define reach
  def __init__(self, pos, angle=0.0, length=500, cone=math.radians(60),
               color=(255, 240, 200), intensity=1.0):
    super().__init__(pos, color, intensity)
    self.angle = angle
    self.length = length
    self.cone = cone
    self._radial = None
    self._radial_key = None
    self._grad_rgba = None
    self._tmp = None

  def _radial_gradient(self, r):
    # <STRANGE>#1561 intensity/color in cache key so dynamic changes rebuild the gradient
    key = (r, round(self.intensity, 3), tuple(self.color))
    if self._radial is not None and self._radial_key == key:
      return self._radial
    # <STRANGE>#1421 tiny source, smoothscale up: no visible ring banding at any radius
    SMALL = 128
    tiny = pygame.Surface((SMALL, SMALL))
    tiny.fill((0, 0, 0))
    cr, cg, cb = self.color
    inten = self.intensity
    for i in range(SMALL, 0, -1):
      k = i / SMALL
      rad = max(1, int(SMALL / 2 * k))
      fall = 1.0 - k * k
      a = fall * inten
      # <STRANGE>#1741 clamp to [0, 255]; flash_intensity=4 would overflow pygame color range
      col = (min(255, int(cr * a)), min(255, int(cg * a)), min(255, int(cb * a)))
      if col == (0, 0, 0):
        continue
      pygame.draw.circle(tiny, col, (SMALL // 2, SMALL // 2), rad)
    target = max(1, r * 2)
    if target == SMALL:
      big = tiny
    else:
      big = pygame.transform.smoothscale(tiny, (target, target))
    self._radial = big
    self._radial_key = key
    return big

  def contribute(self, light_surf, cam, occluders):
    r = max(1, int(self.length * cam.scale))
    cx, cy = cam.to_screen(self.pos[0], self.pos[1])
    sw, sh = light_surf.get_size()
    if cx + r < 0 or cx - r > sw or cy + r < 0 or cy - r > sh:
      return
    radial = self._radial_gradient(r)
    rs = r * 2
    if self._tmp is None or self._tmp.get_size() != (rs, rs):
      self._tmp = pygame.Surface((rs, rs), pygame.SRCALPHA)
    tmp = self._tmp
    tmp.fill((0, 0, 0, 0))
    half = self.cone / 2
    a0 = self.angle - half
    a1 = self.angle + half
    R = r * 2
    p0 = (r + math.cos(a0) * R, r - math.sin(a0) * R)
    p1 = (r + math.cos(a1) * R, r - math.sin(a1) * R)
    pygame.draw.polygon(tmp, (255, 255, 255, 255), [(r, r), p0, p1])
    
    if self._grad_rgba is None or self._grad_rgba.get_size() != (rs, rs):
      self._grad_rgba = pygame.Surface((rs, rs), pygame.SRCALPHA)
    grad_rgba = self._grad_rgba
    grad_rgba.fill((0, 0, 0, 0))
    grad_rgba.blit(radial, (0, 0))
    tmp.blit(grad_rgba, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    
    if occluders:
      max_r = r * 2
      ox, oy = cx - r, cy - r
      # <STRANGE>#1672 world-space light pos for backface check; screen coords for drawing
      lwx, lwy = self.pos[0], self.pos[1]
      for plat in occluders:
        bb = plat["bbox"]
        inside = bb[0] <= lwx <= bb[2] and bb[1] <= lwy <= bb[3]
        for ax, ay, bx, by, nx, ny, nc_dot in plat["edges"]:
          if not inside:
            tlx, tly = lwx - ax, lwy - ay
            if (nx * tlx + ny * tly) * nc_dot >= 0:
              continue
          # <STRANGE>#1712 split edge at light projection: prevents bowtie
          ex = bx - ax
          ey = by - ay
          e2 = ex * ex + ey * ey
          if e2 < 1e-6:
            continue
          t_proj = ((lwx - ax) * ex + (lwy - ay) * ey) / e2
          n_norm = math.hypot(nx, ny)
          if n_norm > 1e-6:
            snx, sny = nx / n_norm, -ny / n_norm
          else:
            snx, sny = 0.0, -1.0
          if 0.0 < t_proj < 1.0:
            cxe = ax + t_proj * ex
            cye = ay + t_proj * ey
            sub_edges = ((ax, ay, cxe, cye), (cxe, cye, bx, by))
          else:
            sub_edges = ((ax, ay, bx, by),)
          for (s_ax, s_ay, s_bx, s_by) in sub_edges:
            sax, say = cam.to_screen(s_ax, s_ay)
            sbx, sby = cam.to_screen(s_bx, s_by)
            dx = sbx - sax
            dy = sby - say
            l2 = dx*dx + dy*dy
            if l2 > 1e-6:
              t = ((cx - sax) * dx + (cy - say) * dy) / l2
              t = 0.0 if t < 0 else (1.0 if t > 1 else t)
              px = sax + t * dx
              py = say + t * dy
              if (cx - px)**2 + (cy - py)**2 > (r * 2)**2:
                continue
            else:
              if (cx - sax)**2 + (cy - say)**2 > (r * 2)**2:
                continue
            dax, day = sax - cx, say - cy
            dbx, dby = sbx - cx, sby - cy
            la = math.hypot(dax, day)
            lb = math.hypot(dbx, dby)
            # <STRANGE>#1713 fallback to outward normal when endpoint on/near light
            if la < 5.0:
              fax = cx + snx * max_r
              fay = cy + sny * max_r
            else:
              fax = cx + dax / la * max_r
              fay = cy + day / la * max_r
            if lb < 5.0:
              fbx = cx + snx * max_r
              fby = cy + sny * max_r
            else:
              fbx = cx + dbx / lb * max_r
              fby = cy + dby / lb * max_r
            pts = [
              (sax - ox, say - oy),
              (sbx - ox, sby - oy),
              (fbx - ox, fby - oy),
              (fax - ox, fay - oy)
            ]
            pygame.draw.polygon(tmp, (0, 0, 0, 0), pts)
        
    light_surf.blit(tmp, (int(cx - r), int(cy - r)), special_flags=pygame.BLEND_RGB_ADD)
