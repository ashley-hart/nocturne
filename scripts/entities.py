import pygame

class PhysicsEntity():
    def __init__(self, game, e_type, pos, size):
        self.game = game
        self.type = e_type
        self.pos = list(pos)
        self.size = size
        self.facing_right = False

        self.velocity = [0, 0] # rate of change in pos
        self.collisions = {'left': False, 'right': False, 'up': False, 'down': False}

        self.action = ""
        self.anim_offset = (
            -4,
            -1,
        )  # accounts for padding in images. Typically should be changed per entity.
        self.flip = False  # flipping images
        self.set_action("idle")

        self.collectbles = []
    

    def update(self, tilemap, movement=(0, 0)):
        # Collisions get reset each frame
        self.collisions = {"up": False, "down": False, "right": False, "left": False}

        frame_movement = (
            movement[0] + self.velocity[0],
            movement[1] + self.velocity[1],
        )

        # Doing the physics processing per dimension is important.
        self.pos[0] += frame_movement[0]

        # We handle to collisions twice per frame so we can control for collisions
        # caused by going L/R or U/D.
        # Handle L/R collisions
        entity_rect = self.rect()
        for rect in tilemap.physics_rects_around(self.pos):
            if entity_rect.colliderect(rect):
                if frame_movement[0] > 0:  # moving right
                    # Make the right edge of the entity snap to the left edge
                    # of the tile.
                    entity_rect.right = rect.left
                    self.collisions["right"] = True
                elif frame_movement[0] < 0:
                    # Make the left edge of the entity snap to the right edge
                    # of the tile.
                    entity_rect.left = rect.right
                    self.collisions["left"] = True
                self.pos[0] = entity_rect.x


        self.pos[1] += frame_movement[1]

        # Handle U/D collisions
        entity_rect = self.rect()
        for rect in tilemap.physics_rects_around(self.pos):
            if entity_rect.colliderect(rect):
                if frame_movement[1] > 0:  # moving down
                    entity_rect.bottom = rect.top
                    self.collisions["down"] = True
                    # print("IS GROUNDED = {True}")
                elif frame_movement[1] < 0:
                    entity_rect.top = rect.bottom
                    self.collisions["up"] = True
                self.pos[1] = entity_rect.y

        if movement[0] > 0:  # moving right
            self.flip = False
        if movement[0] < 0:  # moving left
            self.flip = True

        # Acceleration is applied by modifying velocity.
        if self.collisions["down"] or self.collisions["up"]:
            self.velocity[1] = 0

        # 5 is a placeholder for the upper limit on our velociry.
        # We add a cap to apply the idea of terminal velocity to our system.
        self.velocity[1] = min(5, self.velocity[1] + 0.1)

        self.animation.update()

    def render(self, surf, offset):
        # # Debug rect
        # pygame.draw.rect(surf, (47, 57, 169), (int(self.rect().x - offset[0]), int(self.rect().y - offset[1]), self.size[0], self.size[1]))
        surf.blit(
            pygame.transform.flip(self.animation.img(), self.flip, False),
            (
            self.pos[0] - offset[0] + self.anim_offset[0],
            self.pos[1] - offset[1] + self.anim_offset[1]
            ),
        )

    def set_pos(self, x, y):
        self.pos[0] = x
        self.pos[1] = y

    def rect(self):
        return pygame.Rect(self.pos[0], self.pos[1], self.size[0], self.size[1])

    def set_action(self, action):
        if action != self.action:  # has it changed.
            self.action = action
            self.animation = self.game.assets[self.type + "/" + self.action].copy()


# Using inheritance to give specific qualitites to our Player
class Player(PhysicsEntity):
    GRAVITY = 2
    FALL_GRAVITY = 4
    MOVE_SPEED = 5
    NUM_JUMPS = 3
    JUMP_HEIGHT = -3.9

    def __init__(self, game, pos, size):
        super().__init__(game, "player", pos, size)
        self.air_time = 0
        self.jumps = self.NUM_JUMPS
        self.score = 0

    def update(self, tilemap, movement=(0, 0)):
        super().update(tilemap, movement=movement)

        # print(
        #     "down", self.collisions['down'],
        #     "air_time:", self.air_time,
        #     "velocity_y:", self.velocity[1],
        #     "pos_y:", self.pos[1]
        # )
        # print(self.is_on_ground())
        # TODO: is_grounded()
        # Investigate what it would take to persistently detect 
        # if the player is standing on a ground tile. I think I
        # would need rects that function as raycasts/non-physics 
        # colliders with other tiles to help the player respond 
        # to the env.
        if self.collisions["down"]:
            self.air_time = 0
            self.jumps = self.NUM_JUMPS
        else:
            self.air_time += 1
            if self.velocity[1] > 0:
                self.velocity[1] += (self.velocity[1] * self.get_gravity()) / 60

        # Hnadle Animations
        if self.air_time > 4 and self.velocity[1] < 0:
            self.set_action("jump")
        elif self.air_time > 4 and self.velocity[1] < 0:
            self.set_action["fall"]
        elif movement[0] != 0:
            self.set_action("run")
        else:
            self.set_action("idle")

    def is_on_ground(self):
        return self.collisions['down'] 

    def get_gravity(self):
        if self.velocity[1] < 0:
            return self.GRAVITY
        return self.FALL_GRAVITY

    # - if on ground, permit a jump
    # - if not on ground, but jump key is pressed, and we havent dbl jumped yet, do double jump
    # - if the double jump flag is true, no more jumps are allowed
    # - when the player contacts the ground again, restore dbl jump flag
    def jump(self):
        if self.jumps:
            self.jumps -= 1
            self.velocity[1] = self.JUMP_HEIGHT
            self.air_time = 5 # set to trigger jump animation (thresholf for which is 4)
            return

    def release_jump(self):
        # If still rising, then do jump cut
        if self.velocity[1] < 0:
            self.velocity[1] = self.velocity[1] / 4 # 4 = jump cut factor
            # self.set_action('fall')

    def update_score(self, value):
        self.score += value
        print(f"Updated Player Score: {self.score}")

    def player_win(self):
        print("DO PLAYER WIN EVENT")

    def player_death(self):
        print("DO PLAYER DEATH EVENT")


