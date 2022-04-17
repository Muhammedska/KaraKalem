import time
import pygame


def main():
    try:
        screen = pygame.display.set_mode((1024, 768), pygame.FULLSCREEN)
        screen.fill((255,255,255,5))
        pygame.draw.rect(screen, (255,0,0), (50,50,300,200))
        pygame.display.flip()
        time.sleep(5)
    finally:
        pygame.quit()


main()