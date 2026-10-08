def smooth(k, dt):
  # <STRANGE>#339 framerate-independent lerp: same visual speed at 60 and 165 fps; k is the per-60fps-frame coefficient
  if k >= 1.0:
    return 1.0
  return 1.0 - (1.0 - k) ** (dt * 60.0)

def per_sec(v, dt):
  # <STRANGE>#340 converts a "per 60fps frame" value into "per dt"; multiply per-frame constant by dt*60
  return v * dt * 60.0
