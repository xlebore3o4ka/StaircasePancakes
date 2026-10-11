import pygame
import sys
import math

pygame.init()
W, H = 500, 500
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Сумка — с пуговицей")
clock = pygame.time.Clock()

BG     = (245, 240, 230)
BODY   = (139, 69, 19)
FLAP   = (160, 82, 45)
DARK   = (90, 45, 12)
GOLD   = (218, 165, 32)

while True:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    screen.fill(BG)

    # 1) Ручка — круглая дуга (центр эллипса на y=240 = верх сумки)
    pygame.draw.arc(screen, DARK, (160, 150, 180, 180), 0.0, math.pi, 12)

    # 2) Корпус — прямоугольник со скруглением
    pygame.draw.rect(screen, BODY, (140, 240, 220, 200))

    # 3) Клапан — трапеция поверх корпуса
    pygame.draw.polygon(screen, FLAP,
                        [(140, 240), (360, 240),
                         (340, 330), (160, 330)])

    # 4) Пуговица — круглая застёжка по центру клапана
    pygame.draw.circle(screen, GOLD, (250, 285), 12)

    pygame.display.flip()
    clock.tick(60)