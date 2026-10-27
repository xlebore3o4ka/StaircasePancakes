#include "render.h"
#include <stdlib.h>
#include <math.h>

#define TAU 6.283185307179586f

static int _ensure(SolidBatch *b, int need) {
  if (b->n_verts + need <= b->cap_verts) return 1;
  int nc = b->cap_verts ? b->cap_verts : 8192;
  while (nc < b->n_verts + need) nc *= 2;
  float *nv = (float *)realloc(b->verts, (size_t)nc * 6 * sizeof(float));
  if (!nv) return 0;
  b->verts = nv;
  b->cap_verts = nc;
  return 1;
}
static void _vtx(SolidBatch *b, float x, float y, uint32_t c) {
  if (b->n_verts >= b->cap_verts) return;
  float *p = b->verts + b->n_verts * 6;
  p[0] = x; p[1] = y;
  p[2] = (float)(c & 0xff) / 255.0f;
  p[3] = (float)((c >> 8) & 0xff) / 255.0f;
  p[4] = (float)((c >> 16) & 0xff) / 255.0f;
  p[5] = (float)((c >> 24) & 0xff) / 255.0f;
  b->n_verts++;
}

void solid_init(SolidBatch *b, int cap) {
  if (cap <= 0) cap = 8192;
  b->verts = (float *)malloc((size_t)cap * 6 * sizeof(float));
  b->n_verts = 0;
  b->cap_verts = b->verts ? cap : 0;
}
void solid_free(SolidBatch *b) { free(b->verts); b->verts = 0; b->n_verts = 0; b->cap_verts = 0; }
void solid_reset(SolidBatch *b) { b->n_verts = 0; }
int solid_count(const SolidBatch *b) { return b->n_verts; }
const float *solid_data(const SolidBatch *b) { return b->verts; }

void solid_tri(SolidBatch *b, float x0, float y0, float x1, float y1, float x2, float y2, uint32_t c) {
  if (!_ensure(b, 3)) return;
  _vtx(b, x0, y0, c); _vtx(b, x1, y1, c); _vtx(b, x2, y2, c);
}
void solid_rect(SolidBatch *b, float x, float y, float w, float h, uint32_t c) {
  if (!_ensure(b, 6)) return;
  float x1 = x + w, y1 = y + h;
  _vtx(b, x, y, c);   _vtx(b, x1, y, c);  _vtx(b, x1, y1, c);
  _vtx(b, x, y, c);   _vtx(b, x1, y1, c); _vtx(b, x, y1, c);
}
void solid_circle(SolidBatch *b, float cx, float cy, float r, int segs, uint32_t c) {
  if (segs < 3) segs = 3;
  if (r <= 0.0f) return;
  if (!_ensure(b, segs * 3)) return;
  for (int i = 0; i < segs; i++) {
    float a0 = (float)i / (float)segs * TAU;
    float a1 = (float)(i + 1) / (float)segs * TAU;
    _vtx(b, cx, cy, c);
    _vtx(b, cx + r * cosf(a0), cy + r * sinf(a0), c);
    _vtx(b, cx + r * cosf(a1), cy + r * sinf(a1), c);
  }
}
void solid_ring(SolidBatch *b, float cx, float cy, float ri, float ro, int segs, uint32_t c) {
  if (segs < 3) segs = 3;
  if (ri < 0.0f) ri = 0.0f;
  if (ro < ri) { float t = ri; ri = ro; ro = t; }
  if (ro <= 0.0f) return;
  if (!_ensure(b, segs * 6)) return;
  for (int i = 0; i < segs; i++) {
    float a0 = (float)i / (float)segs * TAU;
    float a1 = (float)(i + 1) / (float)segs * TAU;
    float c0 = cosf(a0), s0 = sinf(a0), c1 = cosf(a1), s1 = sinf(a1);
    float ox0 = cx + ro * c0, oy0 = cy + ro * s0;
    float ox1 = cx + ro * c1, oy1 = cy + ro * s1;
    float ix0 = cx + ri * c0, iy0 = cy + ri * s0;
    float ix1 = cx + ri * c1, iy1 = cy + ri * s1;
    _vtx(b, ox0, oy0, c); _vtx(b, ox1, oy1, c); _vtx(b, ix1, iy1, c);
    _vtx(b, ox0, oy0, c); _vtx(b, ix1, iy1, c); _vtx(b, ix0, iy0, c);
  }
}
void solid_line(SolidBatch *b, float x0, float y0, float x1, float y1, float th, uint32_t c) {
  float dx = x1 - x0, dy = y1 - y0;
  float len = sqrtf(dx * dx + dy * dy);
  if (len < 1e-6f) return;
  float h = th * 0.5f;
  float nx = -dy / len * h, ny = dx / len * h;
  if (!_ensure(b, 6)) return;
  _vtx(b, x0 + nx, y0 + ny, c); _vtx(b, x1 + nx, y1 + ny, c); _vtx(b, x1 - nx, y1 - ny, c);
  _vtx(b, x0 + nx, y0 + ny, c); _vtx(b, x1 - nx, y1 - ny, c); _vtx(b, x0 - nx, y0 - ny, c);
}

static float _cr(float ax, float ay, float bx, float by, float cx, float cy) {
  return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);
}
void solid_polygon(SolidBatch *b, const float *xy, int n, uint32_t c) {
  if (n < 3) return;
  if (n > 256) n = 256;
  float area = 0.0f;
  for (int i = 0; i < n; i++) {
    int j = (i + 1) % n;
    area += xy[i*2] * xy[j*2+1] - xy[j*2] * xy[i*2+1];
  }
  int ccw = area > 0.0f;
  int idx[256];
  for (int i = 0; i < n; i++) idx[i] = i;
  int count = n, guard = 0;
  while (count > 3 && guard < 512) {
    guard++;
    int clipped = 0;
    for (int i = 0; i < count; i++) {
      int ia = idx[(i + count - 1) % count];
      int ib = idx[i];
      int ic = idx[(i + 1) % count];
      float ax = xy[ia*2], ay = xy[ia*2+1];
      float bx = xy[ib*2], by = xy[ib*2+1];
      float cx = xy[ic*2], cy = xy[ic*2+1];
      float cr = _cr(ax, ay, bx, by, cx, cy);
      if (ccw ? (cr <= 0.0f) : (cr >= 0.0f)) continue;
      int bad = 0;
      for (int j = 0; j < count; j++) {
        int ij = idx[j];
        if (ij == ia || ij == ib || ij == ic) continue;
        float px = xy[ij*2], py = xy[ij*2+1];
        float c1 = _cr(ax, ay, bx, by, px, py);
        float c2 = _cr(bx, by, cx, cy, px, py);
        float c3 = _cr(cx, cy, ax, ay, px, py);
        int has_neg = (c1 < 0.0f) || (c2 < 0.0f) || (c3 < 0.0f);
        int has_pos = (c1 > 0.0f) || (c2 > 0.0f) || (c3 > 0.0f);
        if (!(has_neg && has_pos)) { bad = 1; break; }
      }
      if (bad) continue;
      solid_tri(b, ax, ay, bx, by, cx, cy, c);
      for (int j = i; j < count - 1; j++) idx[j] = idx[j + 1];
      count--;
      clipped = 1;
      break;
    }
    if (!clipped) break;
  }
  if (count == 3) {
    int a = idx[0], bb = idx[1], cc = idx[2];
    solid_tri(b, xy[a*2], xy[a*2+1], xy[bb*2], xy[bb*2+1], xy[cc*2], xy[cc*2+1], c);
  }
}
void solid_polygon_outline(SolidBatch *b, const float *xy, int n, float th, uint32_t c) {
  for (int i = 0; i < n; i++) {
    int j = (i + 1) % n;
    solid_line(b, xy[i*2], xy[i*2+1], xy[j*2], xy[j*2+1], th, c);
  }
  float r = th * 0.5f;
  for (int i = 0; i < n; i++) solid_circle(b, xy[i*2], xy[i*2+1], r, 8, c);
}
