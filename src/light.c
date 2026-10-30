#include "light.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

void light_init_sun(Light *l, float dx, float dy, float shadow_length, float gradient_length, const unsigned char col[3], float intensity) {
  memset(l, 0, sizeof(*l));
  l->kind = LK_SUN;
  memcpy(l->color, col, 3);
  l->intensity = intensity;
  l->angle = dx;
  l->length = dy;
  l->radius = shadow_length;
  l->cone = gradient_length;
}

void light_init_lamp(Light *l, float x, float y, float radius, const unsigned char col[3], float intensity) {
  memset(l, 0, sizeof(*l));
  l->kind = LK_LAMP;
  l->x = x; l->y = y; l->radius = radius;
  memcpy(l->color, col, 3);
  l->intensity = intensity;
}

void light_init_spot(Light *l, float x, float y, float angle, float length, float cone, const unsigned char col[3], float intensity) {
  memset(l, 0, sizeof(*l));
  l->kind = LK_SPOT;
  l->x = x; l->y = y; l->angle = angle; l->length = length; l->cone = cone;
  memcpy(l->color, col, 3);
  l->intensity = intensity;
}

void light_free(Light *l) {
  free(l->scratch); l->scratch = NULL; l->scratch_w = l->scratch_h = 0;
  free(l->grad); l->grad = NULL; l->grad_w = l->grad_h = 0;
}

static void fill_polygon(unsigned char *buf, int bw, int bh, float darkness, float *px, float *py, int n) {
  if (n < 3) return;
  float ymin = py[0], ymax = py[0];
  for (int i = 1; i < n; i++) {
    if (py[i] < ymin) ymin = py[i];
    if (py[i] > ymax) ymax = py[i];
  }
  int sy = (int)floorf(ymin), ey = (int)ceilf(ymax);
  if (sy < 0) sy = 0;
  if (ey >= bh) ey = bh - 1;
  if (sy > ey) return;
  int keep = (int)((1.0f - darkness) * 256.0f);
  if (keep < 0) keep = 0;
  if (keep > 256) keep = 256;

  for (int y = sy; y <= ey; y++) {
    float yc = y + 0.5f;
    float xs[32];
    int nx = 0;
    for (int i = 0; i < n && nx < 30; i++) {
      int j = (i + 1) % n;
      float ya = py[i], yb = py[j];
      if ((yc >= ya && yc < yb) || (yc >= yb && yc < ya)) {
        float t = (yc - ya) / (yb - ya);
        xs[nx++] = px[i] + t * (px[j] - px[i]);
      }
    }
    for (int i = 1; i < nx; i++) {
      for (int j = i; j > 0 && xs[j] < xs[j-1]; j--) {
        float t = xs[j]; xs[j] = xs[j-1]; xs[j-1] = t;
      }
    }
    for (int i = 0; i + 1 < nx; i += 2) {
      int xa = (int)ceilf(xs[i]);
      int xb = (int)floorf(xs[i+1]);
      if (xa < 0) xa = 0;
      if (xb >= bw) xb = bw - 1;
      int k = (y * bw + xa) * 3;
      for (int x = xa; x <= xb; x++) {
        buf[k+0] = (unsigned char)((buf[k+0] * keep) >> 8);
        buf[k+1] = (unsigned char)((buf[k+1] * keep) >> 8);
        buf[k+2] = (unsigned char)((buf[k+2] * keep) >> 8);
        k += 3;
      }
    }
  }
}

void light_contribute(Light *l, unsigned char *buf, int bw, int bh, int bgr, Camera *cam, Occluder *occs, int n_occs) {
  float floor_sy_light = (cam->h * 0.5f - (0.0f - cam->y)) * cam->scale + cam->oy;
  int floor_y = (int)ceilf(floor_sy_light);
  if (floor_y < 0) floor_y = 0;
  if (floor_y > bh) floor_y = bh;

  if (l->kind == LK_SUN) {
    if (l->scratch_w < bw || l->scratch_h < bh) {
      free(l->scratch);
      l->scratch = (unsigned char *)malloc((size_t)bw * bh * 3);
      l->scratch_w = bw; l->scratch_h = bh;
    }
    int ir = (int)(l->color[0] * l->intensity); if (ir > 255) ir = 255;
    int ig = (int)(l->color[1] * l->intensity); if (ig > 255) ig = 255;
    int ib = (int)(l->color[2] * l->intensity); if (ib > 255) ib = 255;
    for (int i = 0, n = bw * bh; i < n; i++) {
      int k = i * 3;
      if (bgr) { l->scratch[k+0] = ib; l->scratch[k+1] = ig; l->scratch[k+2] = ir; }
      else     { l->scratch[k+0] = ir; l->scratch[k+1] = ig; l->scratch[k+2] = ib; }
    }

    float wx_dir = -l->angle;
    float wy_dir = -l->length;
    float sx_dir = wx_dir;
    float sy_dir = -wy_dir;
    float sh_len = l->radius * cam->scale;
    float sh_dx = sx_dir * sh_len;
    float sh_dy = sy_dir * sh_len;

    if (occs && n_occs > 0) {
      for (int pi = 0; pi < n_occs; pi++) {
        Occluder *p = &occs[pi];
        /* <STRANGE>#5012 cull occluders whose (screen bbox + shadow) misses the canvas */
        {
          float _sax, _say, _sbx, _sby;
          camera_to_screen(cam, p->min_x, p->min_y, &_sax, &_say);
          camera_to_screen(cam, p->max_x, p->max_y, &_sbx, &_sby);
          float _sminx = fminf(_sax, _sbx) + fminf(0.0f, sh_dx);
          float _smaxx = fmaxf(_sax, _sbx) + fmaxf(0.0f, sh_dx);
          float _sminy = fminf(_say, _sby) + fminf(0.0f, sh_dy);
          float _smaxy = fmaxf(_say, _sby) + fmaxf(0.0f, sh_dy);
          if (_smaxx < 0.0f || _sminx > (float)bw || _smaxy < 0.0f || _sminy > (float)bh) continue;
        }
        for (int ei = 0; ei < p->n_edges; ei++) {
          float *e = p->edges + ei * 7;
          float ax = e[0], ay = e[1], bx = e[2], by = e[3];
          float nx = e[4], ny = e[5];
          if (nx * wx_dir + ny * wy_dir >= 0.0f) continue;

          float sax, say, sbx, sby;
          camera_to_screen(cam, ax, ay, &sax, &say);
          camera_to_screen(cam, bx, by, &sbx, &sby);
          
          float tpx[4] = {sax, sbx, sbx + sh_dx, sax + sh_dx};
          float tpy[4] = {say, sby, sby + sh_dy, say + sh_dy};
          
          fill_polygon(l->scratch, bw, bh, p->absorption, tpx, tpy, 4);
        }
      }
    }

    for (int i = 0, n = bw * bh; i < n; i++) {
      int y = i / bw;
      if (y > floor_y) break;
      int k = i * 3;
      if (buf[k+0] < l->scratch[k+0]) buf[k+0] = l->scratch[k+0];
      if (buf[k+1] < l->scratch[k+1]) buf[k+1] = l->scratch[k+1];
      if (buf[k+2] < l->scratch[k+2]) buf[k+2] = l->scratch[k+2];
    }
    return;
  }

  static int _lut_ready = 0;
  static float _lut[256];
  if (!_lut_ready) {
    for (int i = 0; i < 256; i++) _lut[i] = 1.0f - (float)i / 255.0f;
    _lut_ready = 1;
  }

  float r_world = (l->kind == LK_LAMP) ? l->radius : l->length;
  int r = (int)(r_world * cam->scale);
  if (r < 1) r = 1;
  float cx, cy;
  camera_to_screen(cam, l->x, l->y, &cx, &cy);
  if (cx + r < 0 || cx - r > bw || cy + r < 0 || cy - r > bh) return;

  int sw = r * 2, sh = r * 2;
  if (l->scratch_w < sw || l->scratch_h < sh) {
    free(l->scratch);
    l->scratch = (unsigned char *)malloc((size_t)sw * sh * 3);
    l->scratch_w = sw; l->scratch_h = sh;
  }

  int need_rebuild = (l->grad_w != sw || l->grad_h != sh ||
                      l->grad_intensity != l->intensity ||
                      l->grad_radius != r_world || l->grad_bgr != bgr ||
                      l->grad_angle != l->angle || l->grad_cone != l->cone ||
                      memcmp(l->grad_color, l->color, 3) != 0);

  if (need_rebuild) {
    if (l->grad_w < sw || l->grad_h < sh) {
      free(l->grad);
      l->grad = (unsigned char *)malloc((size_t)sw * sh * 3);
    }
    l->grad_w = sw; l->grad_h = sh;
    int is_spot = (l->kind == LK_SPOT);
    float ux = 0, uy = 0, cos_half = 0;
    if (is_spot) {
      ux = cosf(l->angle); uy = sinf(l->angle); cos_half = cosf(l->cone * 0.5f);
    }
    float r2 = (float)(r * r);
    float inv_r2 = 1.0f / r2;
    for (int y = 0; y < sh; y++) {
      float dy = (float)(y - r);
      for (int x = 0; x < sw; x++) {
        float dx = (float)(x - r);
        float d2 = dx*dx + dy*dy;
        int idx = (y * sw + x) * 3;
        if (d2 > r2) { l->grad[idx] = l->grad[idx+1] = l->grad[idx+2] = 0; continue; }
        if (is_spot) {
          float dl = sqrtf(d2);
          if (dl > 0.0001f) {
            float ca = (dx * ux - dy * uy) / dl;
            if (ca < cos_half) { l->grad[idx] = l->grad[idx+1] = l->grad[idx+2] = 0; continue; }
          }
        }
        int li = (int)((d2 * inv_r2) * 255.0f);
        if (li < 0) li = 0;
        if (li > 255) li = 255;
        float a = _lut[li] * l->intensity;
        float cr = l->color[0] * a;
        float cg = l->color[1] * a;
        float cb = l->color[2] * a;
        if (bgr) {
          l->grad[idx+0] = (unsigned char)(cb > 255.0f ? 255 : cb);
          l->grad[idx+1] = (unsigned char)(cg > 255.0f ? 255 : cg);
          l->grad[idx+2] = (unsigned char)(cr > 255.0f ? 255 : cr);
        } else {
          l->grad[idx+0] = (unsigned char)(cr > 255.0f ? 255 : cr);
          l->grad[idx+1] = (unsigned char)(cg > 255.0f ? 255 : cg);
          l->grad[idx+2] = (unsigned char)(cb > 255.0f ? 255 : cb);
        }
      }
    }
    l->grad_intensity = l->intensity;
    l->grad_radius = r_world;
    l->grad_bgr = bgr;
    l->grad_angle = l->angle;
    l->grad_cone = l->cone;
    memcpy(l->grad_color, l->color, 3);
  }

  memcpy(l->scratch, l->grad, (size_t)sw * sh * 3);

  if (occs && n_occs > 0) {
    float ox = cx - r, oy = cy - r;
    float max_r = r * 3.0f;
    float lwx = l->x, lwy = l->y;
    float reach_world = max_r / cam->scale;
    for (int pi = 0; pi < n_occs; pi++) {
      Occluder *p = &occs[pi];
      if (p->max_x < lwx - reach_world || p->min_x > lwx + reach_world ||
          p->max_y < lwy - reach_world || p->min_y > lwy + reach_world) {
        continue;
      }
      int inside = (lwx >= p->min_x && lwx <= p->max_x &&
                    lwy >= p->min_y && lwy <= p->max_y);
      for (int ei = 0; ei < p->n_edges; ei++) {
        float *e = p->edges + ei * 7;
        float ax = e[0], ay = e[1], bx = e[2], by = e[3];
        float nx = e[4], ny = e[5], nc_dot = e[6];
        if (!inside) {
          float tlx = lwx - ax, tly = lwy - ay;
          if ((nx * tlx + ny * tly) * nc_dot >= 0.0f) continue;
        }
        float ex = bx - ax, ey = by - ay;
        float e2 = ex*ex + ey*ey;
        if (e2 < 1e-6f) continue;
        float tp = ((lwx - ax) * ex + (lwy - ay) * ey) / e2;
        float nn = sqrtf(nx*nx + ny*ny);
        float snx = nn > 1e-6f ? nx / nn : 0.0f;
        float sny = nn > 1e-6f ? -ny / nn : -1.0f;
        float eax[2], eay[2], ebx[2], eby[2];
        int nsub = 1;
        if (tp > 0.0f && tp < 1.0f) {
          float cxe = ax + tp*ex, cye = ay + tp*ey;
          eax[0]=ax; eay[0]=ay; ebx[0]=cxe; eby[0]=cye;
          eax[1]=cxe; eay[1]=cye; ebx[1]=bx; eby[1]=by;
          nsub = 2;
        } else {
          eax[0]=ax; eay[0]=ay; ebx[0]=bx; eby[0]=by;
        }
        for (int s = 0; s < nsub; s++) {
          float sax, say, sbx, sby;
          camera_to_screen(cam, eax[s], eay[s], &sax, &say);
          camera_to_screen(cam, ebx[s], eby[s], &sbx, &sby);
          float dax = sax - cx, day = say - cy;
          float dbx = sbx - cx, dby = sby - cy;
          float la = sqrtf(dax*dax + day*day);
          float lb = sqrtf(dbx*dbx + dby*dby);
          float fax, fay, fbx, fby;
          if (la < 5.0f) { fax = cx + snx*max_r; fay = cy + sny*max_r; }
          else          { fax = cx + dax/la*max_r; fay = cy + day/la*max_r; }
          if (lb < 5.0f) { fbx = cx + snx*max_r; fby = cy + sny*max_r; }
          else          { fbx = cx + dbx/lb*max_r; fby = cy + dby/lb*max_r; }

          float tpx[4] = {sax - ox, sbx - ox, fbx - ox, fax - ox};
          float tpy[4] = {say - oy, sby - oy, fby - oy, fay - oy};
          fill_polygon(l->scratch, sw, sh, p->absorption, tpx, tpy, 4);
        }
      }
    }
  }

  int oxi = (int)(cx - r), oyi = (int)(cy - r);
  for (int y = 0; y < sh; y++) {
    int by = oyi + y;
    if (by < 0 || by >= bh) continue;
    if (by > floor_y) break;
    for (int x = 0; x < sw; x++) {
      int bx = oxi + x;
      if (bx < 0 || bx >= bw) continue;
      int si = (y * sw + x) * 3;
      int di = (by * bw + bx) * 3;
      int rr = buf[di+0] + l->scratch[si+0];
      int gg = buf[di+1] + l->scratch[si+1];
      int bb = buf[di+2] + l->scratch[si+2];
      buf[di+0] = rr > 255 ? 255 : (unsigned char)rr;
      buf[di+1] = gg > 255 ? 255 : (unsigned char)gg;
      buf[di+2] = bb > 255 ? 255 : (unsigned char)bb;
    }
  }
}
