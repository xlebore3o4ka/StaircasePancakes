import random
import pygame
from shared.const import PUFF_COUNT, PUFF_DURATION, PUFF_R_MIN, PUFF_R_MAX, PUFF_SPEED_MIN, PUFF_SPEED_MAX, PUFF_COLOR


class PuffBurst:
  # <STRANGE>#775 one-shot particle burst; player-owned, ticked every frame, removed when lifetime ends
  def __init__(self, pos):
    self.t = 0.0
    self.particles = []
    for _ in range(PUFF_COUNT):
      ang = random.uniform(0, 6.28318)
      spd = random.uniform(PUFF_SPEED_MIN, PUFF_SPEED_MAX)
      self.particles.append({
        "x": pos[0], "y": pos[1],
        "vx": spd * pygame.math.Vector2(1, 0).rotate_rad(ang).x,
        "vy": spd * pygame.math.Vector2(1, 0).rotate_rad(ang).y,
        "r": random.uniform(PUFF_R_MIN, PUFF_R_MAX),
      })

  def update(self, dt):
    self.t += dt
    if self.t >= PUFF_DURATION:
      return False
    for p in self.particles:
      p["x"] += p["vx"] * dt
      p["y"] += p["vy"] * dt
    return True

  def draw(self, screen, cam):
    k = self.t / PUFF_DURATION
    alpha = int(220 * (1.0 - k))
    if alpha <= 0:
      return
    for p in self.particles:
      r = p["r"] * (1.0 - k * 0.7)
      if r < 0.5:
        continue
      sx, sy = cam.to_screen(p["x"], p["y"])
      rr = max(1, int(r * cam.scale))
      surf = pygame.Surface((rr * 2, rr * 2), pygame.SRCALPHA)
      pygame.draw.circle(surf, (*PUFF_COLOR, alpha), (rr, rr), rr)
      screen.blit(surf, (int(sx) - rr, int(sy) - rr))
