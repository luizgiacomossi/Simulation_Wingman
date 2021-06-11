from constants import SCREEN_WIDTH, SCREEN_HEIGHT, PIX2M, M2PIX,SIZE_DRONE, RED
import pygame as pg
from math import atan2, pi, exp
import random
import copy 
import numpy as np
vec = pg.math.Vector2 

def normalFunction(omega,center,position):
    f = exp( -omega*((position.x - center.x) + (position.y - center.y)))
    return f

def bivariateFunction(alpha,beta,center,position):
    '''
        Calculates the bivariate function
        
        position: (x,y)
        center of the function: (xc,yc)
        control variables: Alpha and Beta will control the stringthof the vectors in x and y directions
        return: point in the bivariate function
    '''
    k = 10
    f = exp( -alpha*(position.x - center.x)/k**2 - beta*(position.y - center.y)/k**2 )
    #print(f)
    return f
 
def derivativeBivariate(alpha,beta,center,position):
    '''
        Calculates the bivariate function
        
        position: (x,y)
        center of the function: (xc,yc)
        control variables: Alpha and Beta will control the stringthof the vectors in x and y directions
        return: point in the bivariate function
    '''
    f = bivariateFunction(alpha,beta,center,position)
    dx = f * (-2*alpha*(position.x-center.x))
    dy = f * (-2*beta*(position.y-center.y))
    return vec(dx,dy)

def constrain_ang(ang,min,max):
    if ang > max:
        ang = max
    if ang < min:
        ang = min
    return ang

def random_color():
    """"
        Picks a random color R,G or B

        :return: color picked
        :rtype : tuple
    """
    a = random.uniform(0,255)
    b = random.uniform(0,255)
    c = random.uniform(0,255)
    rgbl=[a,b,c]
    random.shuffle(rgbl)
    return tuple(rgbl)

def limit(v2, max):
    """
        Limits magnitude of vector2

        :param v2: Vector2 to be normalized
        :type v2: pygame.Vector2
        :param max: maximum length of vector
        :type max: int
        :return v: returns vector 
        :rtype v: vector2
    """
    v = copy.deepcopy(v2)
    if v.length() > max:
        v.scale_to_length(max)
    return v

def limit3d(v3, max):
    """
        Limits magnitude of vector2

        :param v2: Vector2 to be normalized
        :type v2: pygame.Vector2
        :param max: maximum length of vector
        :type max: int
        :return v: returns vector 
        :rtype v: vector2
    """
    v = copy.deepcopy(v3)
    if v.length() > max:
        v /= v.length()
        v *= max
    return v
    
def constrain(v2,w,h):
    """
        Constrains movement of drone inside the canvas

        :param v2: Vector2 to be constrained
        :type v2: pygame.Vector2
        :param w: maximum width
        :type w: int
        :param h: maximum height
        :type h: int
        :return v2: returns vector within the limits
        :rtype v2: vector2
    """
    if v2.x > w:
        v2.x = w
    if v2.x < 0:
        v2.x = 0 
    if v2.y > h:
        v2.y = h
    if v2.y < 0:
        v2.y = 0
    return v2

def constrain3d(v3,w,h,alt):
    """
        Constrains movement of drone inside the canvas

        :param v2: Vector2 to be constrained
        :type v2: pygame.Vector2
        :param w: maximum width
        :type w: int
        :param h: maximum height
        :type h: int
        :return v2: returns vector within the limits
        :rtype v2: vector2
    """
    if v3.x > w:
        v3.x = w
    if v3.x < -w:
        v3.x = -w 
    if v3.y > alt:
        v3.y = alt
    if v3.y < 0.2:
        v3.y = 0.2
    if v3.z > h:
        v3.z = h
    if v3.z < -h:
        v3.z = -h
    return v3

def generate_coordenates_kamikaze():
    alpha_random = random.uniform(0,1)
    
    if alpha_random < 0.5:
        if alpha_random < 0.25:
            # x = 0 y = random
            position = vec(0, random.uniform(0,SCREEN_HEIGHT))
        else:
            # x = random y = 0
            position = vec(random.uniform(0,SCREEN_WIDTH), 0)
    else:
        if alpha_random < 0.75:
            # y = SCREEN_HEIGHT x = ramdom
            position = vec(random.uniform(0,SCREEN_WIDTH), SCREEN_HEIGHT)
        else:
            # y = 0 x = SCREEN_WIDTH
            position = vec(SCREEN_WIDTH, random.uniform(0,SCREEN_HEIGHT))

    return position



class FlowField():
    def __init__(self, resolution):

        self.cols =int(SCREEN_WIDTH/resolution)  # Columns of the grid
        self.rows = int(SCREEN_HEIGHT/resolution)  # Rows of the grid
        self.resolution = resolution # Resolution of grid relative to window width and height in pixels

        self.field = [[vec(random.uniform(0,1),random.uniform(0,1)) for col in range(self.cols)] for row in range(self.rows)] # create matrix 
        
    def draw(self, screen):

        blockSize = self.resolution #Set the size of the grid block
        #print(self.cols,self.rows)
        for x in range(0, SCREEN_WIDTH, blockSize):
            for y in range(0, SCREEN_HEIGHT, blockSize):
                rect = pg.Rect(x, y, blockSize, blockSize)
                pg.draw.rect(screen, (200,200,200), rect, 1)

