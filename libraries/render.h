#ifndef RENDER_H
#define RENDER_H
#include <stdint.h>

typedef struct {
  float *verts;
  int n_verts;
  int cap_verts;
} SolidBatch;

void solid_init(SolidBatch *b, int cap);
void solid_free(SolidBatch *b);
void solid_reset(SolidBatch *b);
int  solid_count(const SolidBatch *b);
const float *solid_data(const SolidBatch *b);

void solid_rect(SolidBatch *b, float x, float y, float w, float h, uint32_t rgba);
void solid_tri(SolidBatch *b, float x0, float y0, float x1, float y1, float x2, float y2, uint32_t rgba);
void solid_circle(SolidBatch *b, float cx, float cy, float r, int segs, uint32_t rgba);
void solid_ring(SolidBatch *b, float cx, float cy, float r_in, float r_out, int segs, uint32_t rgba);
void solid_line(SolidBatch *b, float x0, float y0, float x1, float y1, float thick, uint32_t rgba);
void solid_polygon(SolidBatch *b, const float *xy, int n, uint32_t rgba);
void solid_polygon_outline(SolidBatch *b, const float *xy, int n, float thick, uint32_t rgba);
#endif
