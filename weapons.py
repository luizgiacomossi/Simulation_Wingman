from constants import *

class Weapon(object):
    def __init__(self, cooldown, num_cartrides , rate_of_fire, range_of_fire):
        self.cooldown = cooldown
        self.num_cartrides = num_cartrides 
        self.rate_of_fire = rate_of_fire
        self.range_of_fire = range_of_fire
    
    def fire(self):
        print('atirei')

    def load(self):
        print('carregando')

class Vaporizer(Weapon):
    pass

class Freezing(Weapon):
    pass
