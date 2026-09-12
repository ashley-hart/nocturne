import pygame 
import sys
from scripts.entities import Player
from scripts.tilemap import Tilemap
from scripts.utils import load_image, load_images, Animation


class Game:

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((1280, 960))
        self.display = pygame.Surface((320, 240))
        pygame.display.set_caption("Mini Jam - Nocturne")
        self.clock = pygame.time.Clock()

        self.movement = [False, False, False, False]
        self.assets = {
            'decor': load_images('tiles/decor'),
            'grass': load_images('tiles/grass'),
            'large_decor': load_images('tiles/large_decor'),
            'spawners': load_images('tiles/spawners'),
            'stone': load_images('tiles/stone'),
            'player': load_image('entities/player.png'),
            'background': load_image('background.png'),
            'clouds': load_images('clouds'),
            'player/idle': Animation(load_images('entities/player/idle'), img_dur=3),
            'player/run': Animation(load_images('entities/player/run'), img_dur=2),
            'player/jump': Animation(load_images('entities/player/jump')),
            'player/jump': Animation(load_images('entities/player/slide')),
            'player/jump': Animation(load_images('entities/player/wall_slide')),
        }

        self.tilemap = Tilemap(self, tile_size=16)
        try:
            self.tilemap.load('map.json')
        except FileNotFoundError:
            print("[ERROR]: Map data not found.")

        self.player = Player(self, pos=(150,50), size=(8, 15))

        self.scroll = [0,0]

    def run(self):
        while True:
            self.display.fill((0, 0, 0))
            self.display.blit(self.assets['background'], (0,0))

            self.scroll[0] += (self.player.rect().centerx - self.display.get_width() / 2 - self.scroll[0]) / 5
            self.scroll[1] += (self.player.rect().centery - self.display.get_height() / 2 - self.scroll[1]) / 5

            render_scroll = (int(self.scroll[0]), int(self.scroll[1]))

            self.tilemap.render(self.display, render_scroll)

            # Update player
            self.player.update(self.tilemap, ((self.movement[1] - self.movement[0]), 0))
            self.player.render(self.display, render_scroll)


            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_LEFT:
                        self.movement[0] = True
                    if event.key == pygame.K_RIGHT:
                        self.movement[1] = True
                    if event.key == pygame.K_UP:
                        # self.movement[2] = True
                        self.player.velocity[1] = self.player.JUMP_HEIGHT
                    if event.key == pygame.K_DOWN:
                        # self.movement[3] = True
                        pass
                if event.type == pygame.KEYUP:
                    if event.key == pygame.K_LEFT:
                        self.movement[0] = False
                    if event.key == pygame.K_RIGHT:
                        self.movement[1] = False
                    if event.key == pygame.K_UP:
                        self.movement[2] = False
                    if event.key == pygame.K_DOWN:
                        self.movement[3] = False

            self.screen.blit(pygame.transform.scale(self.display, self.screen.get_size()), (0, 0))          
            pygame.display.flip()
            self.clock.tick(60)


Game().run()