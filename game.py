import pygame 
import sys
from scripts.entities import Player
from menus import MainMenu, WinScreen
from scripts.tilemap import Tilemap, Ruby
from scripts.utils import load_image, load_images, resource_path, Animation
from pprint import pprint

# There is an issue with the timer not beign at the amax limit when the level 
# starts, i think this has to do with how the menus and the main game loop 
# interact. Implementing a game state manager should resolve this...

class Game:
    MARGIN_SIZE = 70
    def __init__(self):
        pygame.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((1280, 960))
        self.display = pygame.Surface((240, 320))
        pygame.display.set_caption("Bloodgems")
        self.clock = pygame.time.Clock()

        self.movement = [False, False, False, False]
        self.assets = {
            'decor': load_images('tiles/decor'),
            'grass': load_images('tiles/grass'),
            'large_decor': load_images('tiles/large_decor'),
            'spawners': load_images('tiles/spawners'),
            'stone': load_images('tiles/stone'),
            'player': load_image('entities/player.png'),
            'ruby': load_image('my_art/ruby/ruby.png'),
            'exit_door': load_image('my_art/decor/castle_door.png'),
            # 'background': load_image('background.png'),
            'background': load_image('my_art/backgrounds/background.png'),
            'clouds': load_images('clouds'),
            'player/run': Animation(load_images('my_art/vampy/run'), img_dur=2),
            'player/idle': Animation(load_images('my_art/vampy/idle'), img_dur=5, loop=True),
            'player/jump': Animation(load_images('my_art/vampy/jump')),
            'player/fall': Animation(load_images('my_art/vampy/fall')),
        }

        self.sfx = {
            'jump': pygame.mixer.Sound(resource_path('data/sfx/jump.wav')),
            'ruby_get': pygame.mixer.Sound(resource_path('data/item_pickup.wav'))
        }

        self.sfx['jump'].set_volume(0.6)
        self.sfx['ruby_get'].set_volume(0.4)

        self.player = Player(self, pos=(self.display.get_width()// 2 + 4, 272), size=(8, 15))

        self.level_data = {
            1: {"time_limit": 60, "req_score": 60, "level_height": -40, 'ruby_chance': 0.8},
            2: {"time_limit": 60, "req_score": 80, "level_height": -60, 'ruby_chance': 0.75},
            3: {"time_limit": 60, "req_score": 120, "level_height": -80, 'ruby_chance': 0.7},
        }
        self.level = 1
        self.level_timer = float(self.level_data[1]['time_limit'])
        self.level_score_goal = int(self.level_data[1]['req_score'])

        self.rubies = []
        self.zones = []
        self.tilemap = Tilemap(self, tile_size=16)
        self.generate_level(self.level)

        self.font = pygame.font.Font(None, 36)
        self.scroll = [0, 0] # camera's offset from OG world coords 

    def go_to_main_menu(self):
        main_menu = MainMenu()
        mm_retval = main_menu.run()
        if mm_retval == "play":
            self.generate_level(level_num=1)

    def game_over(self):
        win_screen = WinScreen(mode="lose")
        retval = win_screen.run()

        if retval == "retry":
            self.generate_level(level_num=1)
        if retval == "quit":
            self.go_to_main_menu()
            # self.generate_level(level_num=1)

    def advance_level(self):
        print(f"Level Total {len(self.level_data.keys())}")
        self.level = self.level + 1

        if self.level > len(self.level_data):
            print("[ALL LEVELS COMPLETE] You win!")

            win_screen = WinScreen(mode="win")
            retval = win_screen.run()
            if retval == "retry":
                self.generate_level(level_num=1)
            if retval == "quit":
                print("You pressed quit")
                self.go_to_main_menu()
            return
 
        print(f"Advancing to Level {self.level}")
        self.generate_level(self.level)
        print("Done!")


    def generate_level(self, level_num):
        print(f"Generating Level {level_num}")
        self.rubies.clear()
        self.zones.clear()
        self.tilemap.tilemap.clear()
        self.tilemap.tilemap = {}
        self.tilemap.platforms.clear()
        self.tilemap.platforms = {}

        self.level = level_num
        self.level_timer = float(self.level_data[self.level]['time_limit'])
        self.level_score_goal = float(self.level_data[self.level]['req_score'])
        self.rubies = []
        self.zones = []
        print(self.rubies)
        print(self.zones)
         
        self.tilemap.level_init(self.display, self.level_data[self.level]['level_height'], (0,0))
        self.tilemap.generate_level(self.player.pos, self.display, self.level_data[self.level]['level_height'])
        self.rubies.append(Ruby(self, (100, 272)))

        # repositon and reset the player
        self.player.jumps = self.player.NUM_JUMPS
        self.player.score = 0
        self.player.pos = [self.display.get_width()// 2 + 4, 272]
        self.movement = [False, False, False, False]

        # For testing purposes
        # # ! REMOVE BEFORE SUBMISSION
        # self.player.score = 100


    def run(self):
        pygame.mixer.music.load(resource_path('data/music.wav'))
        pygame.mixer.music.set_volume(0.5)
        pygame.mixer.music.play(-1) # -1 loops for ever

        while True:
            self.display.fill((0, 0, 0))
            self.display.blit(self.assets['background'], (0,0))

            # UI region fill
            self.screen.fill((0,0,0), pygame.Rect(0, 0, 1280, 150))
            # pygame.draw.rect(self.screen, (200, 248, 135), pygame.Rect(0, 0, 1280, 150))

            render_scroll = (int(self.scroll[0]), int(self.scroll[1]))
            # render_scroll = (0,0) # disables camera

            # Update player
            self.player.update(self.tilemap, ((self.movement[1] - self.movement[0]), 0))

            # Update camera
            self.scroll[0] += (self.player.rect().centerx - self.display.get_width() / 2 - self.scroll[0]) / 5
            self.scroll[1] += (self.player.rect().centery - self.display.get_height() / 1.25  - self.scroll[1]) / 5

            # TODO: Add upper bound to vertical scrolling based on level height
            self.scroll[0] = min(max(self.scroll[0], 0), 16)
            self.scroll[1] = min(self.scroll[1], 0) # Vertical scrolling is primary direction

            # Handle Game Environment
            self.tilemap.render(self.display, render_scroll)

            if self.level_timer <= 0:
                print("[LOSS] Player ran out of time!")
                print(f"Regenerating level {self.level}")
                self.player.player_death()
                self.game_over()
                # self.generate_level(self.level)
                # self.advance_level()

            player_rect = self.player.rect()
            # TODO: add 'z_type' to zones
            # Update game-event zones / trigger areas
            for z in self.zones:
                if z.check_collisions(player_rect) and self.level_timer > 0:
                    self.player.player_win()
                    if self.player.score >= self.level_data[self.level]['req_score']:
                        print("[WIN] Player reached exit with enough points!")
                        self.advance_level()
                z.render(self.display, render_scroll)

            # Update rubies.
            # Look into ways to improve this later.
            remove_rubies = []
            for r in self.rubies:
                if r.check_collisions(player_rect):
                    remove_rubies.append(r)
                    self.sfx['ruby_get'].play()
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
            goal_surf = self.font.render(f"GOAL: {self.level_data[self.level]['req_score']}", False, (255, 255, 255))
            self.screen.blit(goal_surf, (20, 50))
            time_surf = self.font.render(f"TIME: {int(self.level_timer)}", False, (255, 255, 255))
            self.screen.blit(time_surf, (20,80))
            lvl_surf = self.font.render(f"LEVEL {self.level}", False, (255, 255, 255))
            self.screen.blit(lvl_surf, (1020,20))

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key in [pygame.K_LEFT, pygame.K_a]:
                        self.movement[0] = True
                    if event.key in [pygame.K_RIGHT, pygame.K_d]:
                        self.movement[1] = True
                    # if event.key == pygame.K_UP:
                    if event.key == pygame.K_SPACE:
                        self.player.jump()
                        # if self.player.air_time > 0 and self.player.did_double_jump == False:
                        #     self.player.did_double_jump = True
                    if event.key == pygame.K_DOWN:
                        # self.movement[3] = True
                        pass
                if event.type == pygame.KEYUP:
                    if event.key in [pygame.K_LEFT, pygame.K_a]:
                        self.movement[0] = False
                    if event.key in [pygame.K_RIGHT, pygame.K_d]:
                        self.movement[1] = False
                    # if event.key == pygame.K_UP:
                    if event.key == pygame.K_SPACE:
                        self.movement[2] = False
                        self.player.release_jump()
                    if event.key == pygame.K_DOWN:
                        self.movement[3] = False

            scaled_width = 720
            scaled_height = 960
            scaled_display = pygame.transform.scale(self.display, (scaled_width, scaled_height))

            self.screen.blit(scaled_display, ((self.screen.get_width() - scaled_width) // 2, 0))  
            pygame.display.flip()
            dt = self.clock.tick(60) / 1000
            self.level_timer -= dt

retval = MainMenu().run()
if retval == 'play':
    Game().run()

# self.screen.blit(pygame.transform.scale(self.display, (self.screen.get_height(), self.screen.get_width() - 20), (0, 0)))   
# # Scale down the width by 20 pixels total
# scaled_width = self.screen.get_width() - (self.MARGIN_SIZE * 2) # uses screen
# scaled_height = int(scaled_width * self.display.get_height() 
#                     / self.display.get_width()) 

# x = (self.screen.get_width() - scaled_width) // 2
# y = (self.screen.get_height() - scaled_height) // 2
