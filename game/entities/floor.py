import pygame
from shared.const import LAYER_FLOOR, FLOOR_FILL


class FloorFill:
  # <NOTE>#443 pseudo-entity: draws the dark band below y=0; participates in the layer system like any drawable
  layer = LAYER_FLOOR

  def __init__(self, color=FLOOR_FILL):
    self.color = color

  def draw(self, screen, cam):
    fx0, fy0 = cam.to_screen(cam.x - cam.w, 0)
    fx1, _ = cam.to_screen(cam.x + cam.w, 0)
    pygame.draw.rect(screen, self.color, (fx0, fy0, fx1 - fx0, screen.get_height() - fy0))
