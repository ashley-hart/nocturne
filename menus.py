import pygame
import sys
from scripts.utils import load_image

class MainMenu:
    def __init__(self):
        pygame.init()
        pygame.font.init()

        self.screen = pygame.display.set_mode((1280, 960))
        self.display = pygame.Surface((240, 320))

        pygame.display.set_caption("Mini Jam - Nocturne")

        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.click = False

        self.assets = {'background': load_image('my_art/backgrounds/background.png')}

        self.scaled_width = 720
        self.scaled_height = 960

    def draw_text(self, text, font, color, surf, x, y):
        text_surf = font.render(text, True, color)
        text_rect = text_surf.get_rect()
        text_rect.topleft = (x, y)
        surf.blit(text_surf, text_rect)

    def draw_button(self, text, button_rect):
        mouse_pos = pygame.mouse.get_pos()

        if button_rect.collidepoint(mouse_pos):
            color = (200, 0, 0)
        else:
            color = (255, 0, 0)

        pygame.draw.rect(self.display, color, button_rect)

        text_surface = self.font.render(text, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=button_rect.center)
        self.display.blit(text_surface, text_rect)

    def run(self):
        while True:
            self.screen.fill((0, 0, 0))
            self.display.blit(self.assets['background'], (0,0))
            # self.draw_text('Ruby Moon', self.font, (255, 255, 255), self.display, self.display.get_width()//4 - 7, 20)
            self.draw_text('Bloodgems', self.font, (255, 255, 255), self.display, self.display.get_width()//4 - 7, 20)


            mx, my = pygame.mouse.get_pos()

            scale_x = self.scaled_width / self.display.get_width()
            scale_y = self.scaled_height / self.display.get_height()

            offset_x = (self.screen.get_width() - self.scaled_width) // 2

            display_x = (mx - offset_x) / scale_x
            display_y = my / scale_y

            button_1 = pygame.Rect((self.display.get_width()//4 + 10, 160), (100, 40))

            b1_color = (180, 0, 0)
            if button_1.collidepoint((display_x, display_y)):
                b1_color = (255, 0, 0)
                if self.click:
                    print("START GAME")
                    return "play"

            pygame.draw.rect(self.display, b1_color, button_1)

            play_text = self.font.render('Play', True, (255, 255, 255))

            play_rect = play_text.get_rect(center=button_1.center)

            self.display.blit(play_text, play_rect)

            self.click = False # reset click var
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1: # left click
                        self.click = True
                    if event.button == 3: # right click
                        pass

            scaled_display = pygame.transform.scale(self.display, (self.scaled_width, self.scaled_height))

            self.screen.blit(scaled_display, ((self.screen.get_width() - self.scaled_width) // 2, 0))  
            pygame.display.flip()
            self.clock.tick(60)

class WinScreen:
    def __init__(self, mode="win"):
        pygame.init()
        pygame.font.init()

        self.screen = pygame.display.set_mode((1280, 960))
        self.display = pygame.Surface((240, 320))
        self.mode = mode # valid modes: "win" / "lose"

        pygame.display.set_caption("Mini Jam - Nocturne")

        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.click = False

        self.assets = {'background': load_image('my_art/backgrounds/background.png')}

        self.scaled_width = 720
        self.scaled_height = 960

    def draw_text(self, text, font, color, surf, x, y):
        text_surf = font.render(text, True, color)
        text_rect = text_surf.get_rect()
        text_rect.topleft = (x, y)
        surf.blit(text_surf, text_rect)

    def draw_button(self, text, button_rect):
        mouse_pos = pygame.mouse.get_pos()

        if button_rect.collidepoint(mouse_pos):
            color = (200, 0, 0)
        else:
            color = (255, 0, 0)

        pygame.draw.rect(self.display, color, button_rect)

        text_surface = self.font.render(text, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=button_rect.center)
        self.display.blit(text_surface, text_rect)

    def run(self):
        while True:
            self.screen.fill((0, 0, 0))
            # self.display.fill((128, 128, 128))
            self.display.blit(self.assets['background'], (0,0))

            mx, my = pygame.mouse.get_pos()

            scale_x = self.scaled_width / self.display.get_width()
            scale_y = self.scaled_height / self.display.get_height()

            offset_x = (self.screen.get_width() - self.scaled_width) // 2

            display_x = (mx - offset_x) / scale_x
            display_y = my / scale_y

            if self.mode == "win":
                self.draw_text('Win Screen', self.font, (255, 255, 255), self.display, self.display.get_width()//4 - 7, 20)
            if self.mode == "lose":
                self.draw_text('Game Over', self.font, (255, 255, 255), self.display, self.display.get_width()//4 - 7, 20)

            button_1 = pygame.Rect((self.display.get_width()//4 + 10, 120), (100, 40))
            button_2 = pygame.Rect((self.display.get_width()//4 + 10, 180), (100, 40))

            b1_color = (180, 0, 0)
            b2_color = (180, 0, 0)
            if button_1.collidepoint((display_x, display_y)):
                b1_color = (255, 0, 0)
                if self.click:
                    print("Button 1 clicked! --> Go to level 1")
                    return "retry"
            if button_2.collidepoint((display_x, display_y)):
                b2_color = (255, 0, 0)
                if self.click:
                    return "quit"

            pygame.draw.rect(self.display, b1_color, button_1)
            pygame.draw.rect(self.display, b2_color, button_2)

            replay_text = self.font.render('Replay', True, (255, 255, 255))
            quit_text = self.font.render('Quit', True, (255, 255, 255))

            replay_rect = replay_text.get_rect(center=button_1.center)
            quit_rect = quit_text.get_rect(center=button_2.center)

            self.display.blit(replay_text, replay_rect)
            self.display.blit(quit_text, quit_rect)

            self.click = False # reset click var
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1: # left click
                        self.click = True
                    if event.button == 3: # right click
                        pass

            scaled_display = pygame.transform.scale(self.display, (self.scaled_width, self.scaled_height))

            self.screen.blit(scaled_display, ((self.screen.get_width() - self.scaled_width) // 2, 0))  
            pygame.display.flip()
            self.clock.tick(60)
MainMenu().run()
# WinScreen().run()