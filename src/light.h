#ifndef LIGHT_H
#define LIGHT_H
#include "camera.h"

typedef struct {
  float min_x, min_y, max_x, max_y;
  int n_edges;
  float *edges;
  int n_points;
  float *points;
  float absorption;
} Occluder;

typedef enum { LK_SUN, LK_LAMP, LK_SPOT } LightKind;

typedef struct {
  LightKind kind;
  float x, y;
  unsigned char color[3];
  float intensity;
  float radius;
  float angle, length, cone;
  unsigned char *scratch;
  int scratch_w, scratch_h;
  unsigned char *grad;
  int grad_w, grad_h;
  float grad_radius, grad_intensity;
  unsigned char grad_color[3];
  int grad_bgr;
} Light;

void light_init_sun (Light *l, float dx, float dy, float shadow_length, float gradient_length, const unsigned char col[3], float intensity);
void light_init_lamp(Light *l, float x, float y, float radius,
                     const unsigned char col[3], float intensity);
void light_init_spot(Light *l, float x, float y, float angle, float length, float cone,
                     const unsigned char col[3], float intensity);
void light_free(Light *l);

void light_contribute(Light *l, unsigned char *buf, int bw, int bh, int bgr,
                      Camera *cam, Occluder *occs, int n_occs);
#endif
