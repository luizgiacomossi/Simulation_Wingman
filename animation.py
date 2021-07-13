from constants import *
import pygame as pg
from math import atan2, pi, exp
import random
import copy 
import numpy as np
vec = pg.math.Vector2 

class Explosion_kamikaze(object):
    def __init__(self, position, window):
        super().__init__()
        self.explosion_animation =  Explosion(position)
        self.all_sprites = pg.sprite.Group()
        self.all_sprites.add(self.explosion_animation)
        self.window = window
        self.timer = 0
        self.position = position
        self.delete_explosion = False

    def count(self):
        self.timer += SAMPLE_TIME
        if self.timer > TIME_EXPLOSION:
            self.delete_explosion = True
    
    def draw(self):
        self.count()
        # usar sprite para desenhar drone
        self.all_sprites.draw(self.window)
        self.all_sprites.update(self.position, 0)
    
    def delete_explosion_status(self):
        return self.delete_explosion

class Aircraft(pg.sprite.Sprite):
    """
        Represents a simple visual animated drone 
        Can load sprites, rotate and update animation
    """
    def __init__(self):
        pg.sprite.Sprite.__init__(self)
        self.sprites = []

        for i in range(0,5):
            self.sprites.append(pg.image.load(f'models/Drone5/sprite_{i}.png'))

        self.atual = 0
        # inherited from the pygame sprite class it is the first element of the drone
        self.image = self.sprites[self.atual]
        # scales down drone sprites to (70,70)
        self.image = pg.transform.scale(self.image,(SIZE_DRONE*2,SIZE_DRONE*2))
        # rect is inherited from Sprite
        # defines the sprite's position on the screen
        # take the image size
        self.rect = self.image.get_rect()
        self.scale = 0.1
        # pega o canto superior esquerdo, posição qualquer
        #self.rect.topleft = 100,100

    def colorize(self, newColor=(40,40,40)):
            """
            Create a "colorized" copy of a surface (replaces RGB values with the given color, preserving the per-pixel alphas of
            original).
            :param image: Surface to create a colorized copy of
            :param newColor: RGB color to use (original alpha values are preserved)
            :return: New colorized Surface instance
            """
            image = self.image.copy()

            # zero out RGB values
            #image.fill((0, 0, 0, 255), None, pg.BLEND_RGBA_MULT)
            # add in new RGB values
            image.fill(newColor[0:3] + (0,), None, pg.BLEND_RGBA_ADD)
            self.image = image

    def update(self, position, angle, size = SIZE_DRONE* PIX2M):
        
        # animation update speed is controle by this parameter
        self.atual += 1
        if self.atual >= len(self.sprites):
            self.atual = 0

        self.image = self.sprites[round(self.atual)]
    
        # Rotates image -> angle should be in degrees
        # rotozoom(Surface, angle, scale) -> Surface
        self.image = pg.transform.rotozoom(self.image, -angle*180/pi - 90, self.scale)
        self.rect = self.image.get_rect()
        # positions center of rect in acual drone position
        self.rect.center = position.x,position.y

class Tree(pg.sprite.Sprite):
    """
        Represents a simple visual animated tree 
        Can load sprites, rotate and update animation
    """
    def __init__(self):
        pg.sprite.Sprite.__init__(self)
        self.sprites = []

        for i in range(1,2):
            self.sprites.append(pg.image.load(f'models/tree3/tree_{i}.png').convert())
            #self.sprites.append(pg.image.load(f'models/building/sprite0.png').convert())
            self.sprites[i-1] =  pg.transform.rotozoom(self.sprites[i-1], 0, .3)

        self.atual = 0
        # inherited from the pygame sprite class it is the first element of the drone
        self.image = self.sprites[self.atual]
        # scales down drone sprites to (70,70)
        #self.image = pg.transform.scale(self.image,(RADIUS_OBSTACLES,RADIUS_OBSTACLES))
        # rect is inherited from Sprite
        # defines the sprite's position on the screen
        # take the image size
        self.rect = self.image.get_rect()
        
        # pega o canto superior esquerdo, posição qualquer
        #self.rect.topleft = 100,100


    def update(self, position, angle, size = SIZE_DRONE* PIX2M):
        
        # animation update speed is controle by this parameter
        self.atual += .001
        if self.atual >= len(self.sprites)-1:
            self.atual = 0

        self.image = self.sprites[round(self.atual)]
    
        # Rotates image -> angle should be in degrees
        # rotozoom(Surface, angle, scale) -> Surface
        #self.image = pg.transform.rotozoom(self.image, 0, .2)
        self.rect = self.image.get_rect()
        # positions center of rect in acual drone position
        self.rect.midbottom = position.x,position.y+20

class Kamikaze_drone(Aircraft):
    """
        Represents a simple visual animated drone 
        Can load sprites, rotate and update animation
    """
    def __init__(self):
        super().__init__()
        self.sprites = []
        for i in range(0,5):
            self.sprites.append(pg.image.load(f'models/kamikaze/sprite_{i}.png'))
    
    def explode(self):
        self.sprites = []
        self.scale = 2
        for i in range(10,30):
            self.sprites.append(pg.image.load(f'models/kamikaze/explosion/explosion1_00{i}.png'))
            
class Explosion(pg.sprite.Sprite):
    """
        Represents a  animated explosion 
    """
    def __init__(self, position):
        pg.sprite.Sprite.__init__(self)
        self.sprites = []
        self.scale = 2

        for i in range(10,30):
            self.sprites.append(pg.image.load(f'models/kamikaze/explosion/explosion1_00{i}.png'))
            #self.sprites[i-1] =  pg.transform.rotozoom(self.sprites[i-1], 0, .3)

        self.current = 0
        # inherited from the pygame sprite class it is the first element of the drone
        self.image = self.sprites[self.current]
        self.rect = self.image.get_rect()
        self.rect.midbottom = position.x,position.y+20


    def update(self, position, angle, size = SIZE_DRONE* PIX2M):
        
        # animation update speed is controle by this parameter
        self.current += 1
        if self.current >= len(self.sprites)-1:
            self.current = 0

        self.image = self.sprites[round(self.current)]
        # Rotates image -> angle should be in degrees
        # rotozoom(Surface, angle, scale) -> Surface
        #self.image = pg.transform.rotozoom(self.image, 0, .2)
        self.rect = self.image.get_rect()
        # positions center of rect in acual drone position
        self.rect.midbottom = position.x,position.y+20

class ProtectedArea(object):
    def __init__(self, size = 300, coordenates = vec(300,300) ):
        super().__init__()

    def draw(self):
        pass

