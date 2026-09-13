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
            -3,
            -3,
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
        surf.blit(
            pygame.transform.flip(self.animation.img(), self.flip, False),
            (
            self.pos[0] - offset[0] + self.anim_offset[0],
            self.pos[1] - offset[1] + self.anim_offset[1]
            ),
        )
        # Debug rect
        # pygame.draw.rect(surf, (47, 57, 169), (int(self.rect().x - offset[0]), int(self.rect().y - offset[1]), self.size[0], self.size[1]))

    def rect(self):
        return pygame.Rect(self.pos[0], self.pos[1], self.size[0], self.size[1])

    def set_action(self, action):
        if action != self.action:  # has it changed.
            self.action = action
            self.animation = self.game.assets[self.type + "/" + self.action].copy()


# Using inheritance to give specific qualitites to our Player
class Player(PhysicsEntity):

    MOVE_SPEED = 5
    JUMP_HEIGHT = -3.8

    def __init__(self, game, pos, size):
        super().__init__(game, "player", pos, size)
        self.air_time = 0
        self.did_double_jump = False ## maybe we can use air_time >0
        self.score = 0

    def update(self, tilemap, movement=(0, 0)):
        super().update(tilemap, movement=movement)

        self.air_time += 1
        if self.collisions["down"]:
            self.air_time = 0
            self.did_double_jump = False

        if self.air_time > 4:
            self.set_action("jump")
        elif movement[0] != 0:
            self.set_action("run")
        else:
            self.set_action("idle")

    def jump(self, movement=(0,0)):
        # What movement params do i need?
        pass
        # TODO: Make jump more responsive, 
        # - add jump cutting 
        # - make fall faster than rise

    def update_score(self, value):
        self.score += value
        print(f"Updated Player Score: {self.score}")

    def player_win(self):
        print(f"DO PLAYER WIN EVENT")

    def player_death(self):
        print(f"DO PLAYER DEATH EVENT")





    class Moon():
        # Basically the reddening moon texture in the BG... idk if i need a class for this
        def __init__(self):
            pass