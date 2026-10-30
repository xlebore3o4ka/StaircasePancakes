#include "camera.h"
#include <math.h>
#include <stdlib.h>
#define TAU 6.283185307179586f

static inline float smooth_step(float k, float dt) {
  if (k >= 1.0f) return 1.0f;
  return 1.0f - powf(1.0f - k, dt * 60.0f);
}

void camera_init(Camera *c, float x, float y, float w, float h, float scale) {
  c->x=x; c->y=y; c->w=w; c->h=h; c->scale=scale; c->lerp_t=0.1f;
  c->shake_t=c->shake_dur=c->shake_amp=c->shake_freq=0.0f;
  c->ox=c->oy=0.0f;
}
void camera_follow(Camera *c, float tx, float ty, float dt) {
  float k = smooth_step(c->lerp_t, dt);
  c->x += (tx-c->x)*k; c->y += (ty-c->y)*k;
}
void camera_shake(Camera *c, float dur, float amp, float freq) {
  c->shake_t=dur;
  c->shake_dur = dur > 0.001f ? dur : 0.001f;
  c->shake_amp=amp; c->shake_freq=freq;
}
void camera_update(Camera *c, float dt) {
  if (c->shake_t <= 0.0f) { c->ox=c->oy=0.0f; return; }
  c->shake_t = fmaxf(0.0f, c->shake_t - dt);
  float k = c->shake_t / c->shake_dur;
  if (c->shake_freq > 0.0f) {
    float ph = (c->shake_dur - c->shake_t) * c->shake_freq * TAU;
    c->ox = sinf(ph)         * c->shake_amp * k;
    c->oy = sinf(ph + 1.3f)  * c->shake_amp * k;
  } else {
    float rx = (float)rand()/(float)RAND_MAX;
    float ry = (float)rand()/(float)RAND_MAX;
    c->ox = (rx*2.0f-1.0f)*c->shake_amp*k;
    c->oy = (ry*2.0f-1.0f)*c->shake_amp*k;
  }
}
void camera_to_screen(const Camera *c, float wx, float wy, float *sx, float *sy) {
  *sx = (wx - c->x + c->w*0.5f)  * c->scale + c->ox;
  *sy = (c->h*0.5f - (wy - c->y)) * c->scale + c->oy;
}
void camera_from_screen(const Camera *c, float sx, float sy, float *wx, float *wy) {
  *wx = sx / c->scale - c->w*0.5f + c->x;
  *wy = c->h*0.5f - sy / c->scale + c->y;
}
