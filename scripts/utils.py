import os
import sys
import pygame

def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


BASE_IMG_PATH = resource_path("data/images")


def load_image(path, colorkey="black"):
    img = pygame.image.load(
        os.path.join(BASE_IMG_PATH, path)
    ).convert()

    img.set_colorkey(colorkey) # automatically key out the black
    return img

def load_images(path):
    images=[]
    
    directory = os.path.join(BASE_IMG_PATH, path)

    for img_name in sorted(os.listdir(directory)):
        images.append(
            load_image(os.path.join(path, img_name))
        )
        
    return images

class Animation:
    def __init__(self, images, img_dur=5, loop=True):
        self.images = images
        self.img_duration = img_dur
        self.loop = loop
        self.done = False
        self.frame = 0 # frame of the game in this context

    def copy(self):
        return Animation(self.images, self.img_duration, self.loop)

    def update(self):
        if self.loop:
            self.frame = (self.frame + 1) % (self.img_duration * len(self.images)) # no -1 here bc of how modulo works
        else:
            self.frame = min(self.frame + 1, self.img_duration * len(self.images) - 1) # -1 because of lists being 0-indexed
            if self.frame >= self.img_duration * len(self.images) - 1:
                self.done = True

    def img(self):
        return self.images[int(self.frame / self.img_duration)]