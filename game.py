import pygame 
import sys
from scripts.entities import Player
from scripts.tilemap import Tilemap, Ruby
from scripts.utils import load_image, load_images, Animation
from pprint import pprint


class Game:

    MARGIN_SIZE = 70
    def __init__(self):
        pygame.init()
        pygame.font.init()
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
            'background_flipped': load_image('background_flipped.png'),
            'clouds': load_images('clouds'),
            'player/idle': Animation(load_images('entities/player/idle'), img_dur=3),
            'player/run': Animation(load_images('entities/player/run'), img_dur=2),
            'player/jump': Animation(load_images('entities/player/jump')),
            'player/jump': Animation(load_images('entities/player/slide')),
            'player/jump': Animation(load_images('entities/player/wall_slide')),
        }

        self.current_level = 1

        self.player = Player(self, pos=(self.display.get_width()// 2 + 4, 272), size=(8, 15))
        self.zones = []

        self.rubies = []
        self.tilemap = Tilemap(self, tile_size=16)
        
        self.tilemap.level_init(self.display, (0,0))
        self.tilemap.spawn_platforms(self.player.pos, self.display)
        self.rubies.append(Ruby((100, 272)))
        pprint(self.tilemap.platforms)


        # TODO: Write level validation code, 
        # if level score req < num rubies on platforms - (difficulty threshold int),
        # add more rubies to a as randomly selected platforms that are needed
        # some/several should still be empty.
        # TODO: Refactor -> Move all level set up code into a function/Level class
        # TODO: Determine what level parameters I need.
        # pprint(self.tilemap.tilemap)
        # try:
            # self.tilemap.load('map.json')
        #     self.tilemap.load('test.json')
        # except FileNotFoundError:
        #     print("[ERROR]: Map data not found.")

        # self.player = Player(self, pos=(self.display.get_width()// 2, self.display.get_height() * 0.6), size=(8, 15))
        # self.player = Player(self, pos=(0, 0), size=(8, 15))

        self.font = pygame.font.Font(None, 36)
        self.f_surf = self.font.render(f"PLAYER SCORE: {self.player.score}", False, (255, 255, 255))
        self.screen.blit(self.f_surf , self.f_surf .get_rect(topleft=(20,20)))
        self.f_surf = self.font.render("GOAL: 100", False, (255, 255, 255))
        self.screen.blit(self.f_surf , self.f_surf .get_rect(topleft=(20, 50)))

        self.scroll = [0, 0] # camera's offset from OG world coords 

    def advance_level(self):
        print(f"Advancing to Level {self.current_level + 1}")
        # self.current_level += 1

    # TODO: Mini Jam 219
    # MVP
    # - make jump/movement feel good
    # - add roof to tower
    # - add score-based win condition
    # - add level parameters
    # - add level transition (reset/regenerate tilemap + player)

    # Reliability
    # - add generation validation
    # - export tilemaps to JSON
    # - make sure exported tilemaps are loadable

    # Polish
    # - add art assets
    # - add main menu
    # - add simple level transition/cutscene if time allows


    def run(self):
        while True:
            self.display.fill((0, 0, 0))
            self.display.blit(self.assets['background_flipped'], (0,0))

            # UI region fill
            self.screen.fill((0,0,0), pygame.Rect(0, 0, 290, 100))
            # pygame.draw.rect(self.screen, (200, 248, 135), pygame.Rect(0, 0, 290, 100))

            render_scroll = (int(self.scroll[0]), int(self.scroll[1]))
            # render_scroll = (0,0)

            # Update player
            self.player.update(self.tilemap, ((self.movement[1] - self.movement[0]), 0))

            # Update camera
            self.scroll[0] += (self.player.rect().centerx - self.display.get_width() / 2 - self.scroll[0]) / 5
            self.scroll[1] += (self.player.rect().centery - self.display.get_height() / 1.25  - self.scroll[1]) / 5

            # TODO: Add upper bound to vertical scrolling based on level height
            self.scroll[0] = min(max(self.scroll[0], 0), 16)
            self.scroll[1] = min(self.scroll[1], 0) # Vertical scrolling is primary direction

            self.tilemap.render(self.display, render_scroll)

            player_rect = self.player.rect()
            # Update game-event zones / trigger areas
            for z in self.zones:
                if z.check_collisions(player_rect):
                    print("[WIN] Player reached exit!")
                    self.player.player_win()
                    self.advance_level()
                z.render(self.display, render_scroll)

            # Update rubies.
            # Look into ways to improve this later.
            remove_rubies = []
            for r in self.rubies:
                if r.check_collisions(player_rect):
                    remove_rubies.append(r)
                    self.player.update_score(10)
                r.render(self.display, render_scroll)

            if remove_rubies:
                for r in remove_rubies:
                    self.rubies.remove(r)

            # NOW render the player so they on top
            self.player.render(self.display, render_scroll)

            # Update UI elements
            score_surf = self.font.render(f"PLAYER SCORE: {self.player.score}", False, (255, 255, 255))
            self.screen.blit(score_surf, (20,20))
            goal_surf = self.font.render("GOAL: 100", False, (255, 255, 255))
            self.screen.blit(goal_surf, (20, 50))

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