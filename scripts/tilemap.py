import pygame
import json
import random

NEIGHBOR_OFFSETS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1), (0, 0), (0, 1),
    (1, -1), (1, 0), (1, 1),
]

PHYSICS_TILES = {"grass", "stone"}

MAX_HEIGHT_FROM_PLAYER = 4
PLATFORM_TYPES = {
    'left': (1, 5),
    'middle': (6, 10),
    'right': (11, 15),
    'final': (3, 13)
}

MAX_PLATFORM_HEIGHT = -20
FINAL_AREA_HEIGHT = 10
RUBY_CHANCE = 0.75

class Tilemap:
    def __init__(self, game, tile_size=16, seed=42):
        self.game = game
        self.tile_size = tile_size
        self.tilemap = {}
        self.offgrid_tiles = []
        self.platforms = {} # {"y": 14, "type": 'left', "has_ruby": False}

        random.seed()

    def render(self, surf, offset=(0, 0)):
        for tile in self.offgrid_tiles:
            surf.blit(self.game.assets[tile["type"]][tile["variant"]],
                (tile["pos"][0] - offset[0], tile["pos"][1] - offset[1]),)

        for x in range(
            offset[0] // self.tile_size,
            (offset[0] + surf.get_width()) // self.tile_size + 1,
        ):
            for y in range(
                offset[1] // self.tile_size,
                (offset[1] + surf.get_height()) // self.tile_size + 1,
            ):
                loc = str(x) + ";" + str(y)
                if loc in self.tilemap:
                    tile = self.tilemap[loc]
                    surf.blit(self.game.assets[tile['type']][tile['variant']], (tile['pos'][0] * self.tile_size - offset[0], tile['pos'][1] * self.tile_size - offset[1]))

    def save(self, path):
        f = open(path, 'w')
        json.dump({'tilemap': self.tilemap, 'tile_size': self.tile_size, 'offgrid': self.offgrid_tiles}, f)
        f.close()

    def load(self, path):
        f = open(path, 'r')
        map_data = json.load(f)
        f.close()

        self.tilemap = map_data['tilemap']
        self.tile_size = map_data['tile_size']
        self.offgrid_tiles = map_data['offgrid']

    # Looking up vals in a dict is also very fast.
    def tiles_around(self, pos):
        tiles = []
        # This converts te pixel position into a grid position
        tile_loc = (int(pos[0] // self.tile_size), int(pos[1] // self.tile_size))
        for offset in NEIGHBOR_OFFSETS:
            check_loc = str(tile_loc[0] + offset[0]) + ";" + str(tile_loc[1] + offset[1])
            if check_loc in self.tilemap: # if a tile is actually there
                tiles.append(self.tilemap[check_loc])
        return tiles

    # Return rects that we can use for physics!
    def physics_rects_around(self, pos):
        rects = []
        for tile in self.tiles_around(pos):
            if tile['type'] in PHYSICS_TILES:
                rects.append(pygame.Rect(tile['pos'][0] * self.tile_size, tile['pos'][1] * self.tile_size, self.tile_size, self.tile_size))
        return rects

    def get_tile_loc(self, pos):
        return (int(pos[0] // self.tile_size), int(pos[1] // self.tile_size))

    def level_init(self, surf, lvl_height, offset, seed=42):

        left_wall_x = (offset[0] // self.tile_size)
        # left_wall_x = 5
        right_wall_x = (offset[0] + surf.get_width() // self.tile_size)

        # Floors
        for x in range((offset[0] // self.tile_size) - 1, (offset[0] + surf.get_width()) // self.tile_size + 1):
            for y in range(18,20):
                loc = str(x) + ';' + str(y)
                self.tilemap[loc] = {'type': 'stone', 'variant': 1, 'pos': [x, y]}

        # Walls
        for y in range(lvl_height, 20):
            for x in [left_wall_x, left_wall_x - 1, right_wall_x + 1, right_wall_x]:
                    loc = str(x) + ';' + str(y)
                    self.tilemap[loc] = {'type': 'stone', 'variant': 1, 'pos': [x, y]}

        # Ceiling
        for x in range((offset[0] // self.tile_size) - 1, (offset[0] + surf.get_width()) // self.tile_size + 1):
            for y in range(lvl_height-20, lvl_height):
                loc = str(x) + ';' + str(y)
                self.tilemap[loc] = {'type': 'stone', 'variant': 1, 'pos': [x, y]}

    possible_platform_min = 4 # y-tile coordinate for minimum possible tile position.

    # TODO: Refactor -> Move all level set up code into a function/Level class
    # TODO: Determine what level parameters I need.
    # TODO: Write level validation code
    # if level score req < num rubies on platforms - (difficulty threshold int),
    # add more rubies to a as randomly selected platforms that are needed
    # some/several should still be empty
    def generate_level(self, player_pos, surf, lvl_height, offset=(0,0)):
        player_y = int(player_pos[1] // self.tile_size)
        print("player_y = ", player_y)

        # y = player_y - random.randint(1, MAX_HEIGHT_FROM_PLAYER + 1)
        y = random.randint(14, 15)
        print("SPAWN PLATFORMS")
        print("Spawning platform at y =", y)
        print(PLATFORM_TYPES['left'])

        p_types = list(PLATFORM_TYPES.keys())
        p_types.remove('final')
        p_last_spawned = None

        while y > lvl_height + FINAL_AREA_HEIGHT:
            if y > (lvl_height - FINAL_AREA_HEIGHT + 4):
                if p_last_spawned:
                    if p_last_spawned == 'left':
                        p_types = ['middle', 'right']
                    elif p_last_spawned == 'middle':
                        p_types = ['left', 'right']
                    elif p_last_spawned == 'right':
                        p_types = ['left', 'middle']

                curr_p_type = random.choice(p_types)
                self.create_platform(curr_p_type, y)
                y = self.get_platform_height(y)
                p_last_spawned = curr_p_type

            # No platforms in middle can spawn under the final area.
            elif y < (MAX_PLATFORM_HEIGHT - FINAL_AREA_HEIGHT + 4): 
                curr_p_type = random.choice(['left', 'right'])
                self.create_platform(curr_p_type, y)
                y = self.get_platform_height(y)

        self.create_platform('final', y)
        ed_pos = self.get_platform_midpoint('final', y)
        ed_pos = (ed_pos[0] - (self.tile_size * 1), ed_pos[1] - (self.tile_size * 2))
        self.game.zones.append(ExitDoor(self.game, ed_pos))


    def create_platform(self, platform_type, y, has_item=False, has_enemy=False):
        for x in range(PLATFORM_TYPES[platform_type][0], PLATFORM_TYPES[platform_type][1]):
            loc = str(x) + ';' + str(y)
            self.tilemap[loc] = {'type': 'stone', 'variant': 1, 'pos': [x, y]}

        # Decide on if this platform gets a ruby.
        if platform_type != 'final' and random.random() < RUBY_CHANCE:
            self.spawn_ruby(platform_type, y)
            self.platforms[y] = {'p_type': platform_type, 'has_ruby': True, 'has_enemy': False}
        else: 
            self.platforms[y] = {'p_type': platform_type, 'has_ruby': False, 'has_enemy': False}


    def get_platform_height(self, last_y=17):
        # print("Spawning NEXT platform at y =", y)
        return last_y - random.randint(2, MAX_HEIGHT_FROM_PLAYER + 1)

    def spawn_final_area(self, y):
        # TODO: Add rect for game_over event.
        pass

    def spawn_ruby(self, platform_type, y):
        self.game.rubies.append(Ruby(self.game, self.get_platform_midpoint(platform_type, y)))

    def get_platform_midpoint(self, platform_type, platform_y):
        platform_tile_range = PLATFORM_TYPES[platform_type]
        # Convert tile numbers to world coords.
        center_offset = 8
        x1 = (platform_tile_range[0] * self.tile_size) - center_offset
        x2 = (platform_tile_range[1] * self.tile_size) - center_offset
        y1 = y2 = ((platform_y - 1) * self.tile_size)
        return  (x1 + x2) // 2, (y1 + y2) // 2


class Ruby():
    def __init__(self, game, pos, size=16):
        self.game = game
        self.pos = pos
        self.size = size
        self.rect = pygame.Rect((self.pos[0], self.pos[1]), (self.size, self.size))
        self.image = None # using a red rect for now

    def render(self, surf, offset):
        surf.blit(self.game.assets['ruby'], (self.rect.x - offset[0], self.rect.y - offset[1], self.size, self.size))
        # pygame.draw.rect(surf, (255, 0, 0), (self.rect.x - offset[0], self.rect.y - offset[1], self.size, self.size))

    def check_collisions(self, rect):
        return self.rect.colliderect(rect)


class ExitDoor():
    def __init__(self, game, pos, size=48):
        self.game = game
        self.pos = pos
        self.size = size
        self.rect = pygame.Rect((self.pos[0], self.pos[1]), (self.size, self.size))
        self.image = None # using a red rect for now

    def render(self, surf, offset):
        # surf.blit(self.game.get)
        pygame.draw.rect(surf, (255, 0, 255), (self.rect.x - offset[0], self.rect.y - offset[1], self.size, self.size))

    def check_collisions(self, rect):
        return self.rect.colliderect(rect)