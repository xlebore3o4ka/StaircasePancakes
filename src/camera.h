#ifndef CAMERA_H
#define CAMERA_H
typedef struct {
  float x, y, w, h, scale, lerp_t;
  float shake_t, shake_dur, shake_amp, shake_freq;
  float ox, oy;
} Camera;

void camera_init(Camera *c, float x, float y, float w, float h, float scale);
void camera_follow(Camera *c, float tx, float ty, float dt);
void camera_shake(Camera *c, float dur, float amp, float freq);
void camera_update(Camera *c, float dt);
void camera_to_screen(const Camera *c, float wx, float wy, float *sx, float *sy);
void camera_from_screen(const Camera *c, float sx, float sy, float *wx, float *wy);
#endif
