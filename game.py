import pygame 
import sys
from scripts.entities import Player
from scripts.tilemap import Tilemap
from scripts.utils import load_image, load_images, Animation
from pprint import pprint


class Game:

    MARGIN_SIZE = 70
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((1280, 960))
        self.display = pygame.Surface((240, 320))
        # self.display = pygame.Surface((320, 240))
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
        self.tilemap.level_init(self.display, (0,0))
        # pprint(self.tilemap.tilemap)
        # try:
            # self.tilemap.load('map.json')
        #     self.tilemap.load('test.json')
        # except FileNotFoundError:
        #     print("[ERROR]: Map data not found.")

        self.player = Player(self, pos=(self.display.get_width()// 2 + 4, 272), size=(8, 15))
        # self.player = Player(self, pos=(self.display.get_width()// 2, self.display.get_height() * 0.6), size=(8, 15))
        # self.player = Player(self, pos=(0, 0), size=(8, 15))
        self.tilemap.spawn_platforms(self.player.pos, self.display)

        self.scroll = [0, 0] # camera's offset from OG world coords 

    def run(self):
        while True:
            self.display.fill((0, 0, 0))
            self.display.blit(self.assets['background'], (0,0))

            render_scroll = (int(self.scroll[0]), int(self.scroll[1]))
            # render_scroll = (0,0)

            # Update player
            self.player.update(self.tilemap, ((self.movement[1] - self.movement[0]), 0))
            self.player.render(self.display, render_scroll)

            # Update camera
            self.scroll[0] += (self.player.rect().centerx - self.display.get_width() / 2 - self.scroll[0]) / 5
            self.scroll[1] += (self.player.rect().centery - self.display.get_height() / 1.25  - self.scroll[1]) / 5

            self.scroll[0] = min(max(self.scroll[0], 0), 16)
            self.scroll[1] = min(self.scroll[1], 0) # Vertical scrolling is primary direction

            self.tilemap.render(self.display, render_scroll)

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
                        # TODO: This should call the player's jump() method
                            self.player.velocity[1] = self.player.JUMP_HEIGHT
                        # if self.player.did_double_jump == False:
                        #     self.player.velocity[1] = self.player.JUMP_HEIGHT
        
                        # if self.player.air_time > 0 and self.player.did_double_jump == False:
                        #     self.player.did_double_jump = True

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

            # self.screen.blit(pygame.transform.scale(self.display, (self.screen.get_height(), self.screen.get_width() - 20), (0, 0)))   
            # # Scale down the width by 20 pixels total
            # scaled_width = self.screen.get_width() - (self.MARGIN_SIZE * 2) # uses screen
            # scaled_height = int(scaled_width * self.display.get_height() 
            #                     / self.display.get_width()) 

            # x = (self.screen.get_width() - scaled_width) // 2
            # y = (self.screen.get_height() - scaled_height) // 2

            scaled_width = 720
            scaled_height = 960


            scaled_display = pygame.transform.scale(self.display, (scaled_width, scaled_height))
            # scaled_display = pygame.transform.scale(self.display, (scaled_width, scaled_height))

            # Shift the X coordinate by 10 to perfectly center it
            self.screen.blit(scaled_display, ((self.screen.get_width() - scaled_width) // 2, 0))  
            # self.screen.blit(scaled_display, (x, y))  
            pygame.display.flip()
            self.clock.tick(60)

Game().run()