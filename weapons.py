from constants import *

class Weapon(object):
    def __init__(self, cooldown, num_cartrides , rate_of_fire, range_of_fire, swarm_kamikazes):
        self.cooldown = cooldown
        self.num_cartrides = num_cartrides 
        self.rate_of_fire = rate_of_fire
        self.range_of_fire = range_of_fire
        self.kamikazes = swarm_kamikazes
    
    def fire(self):
        print('atirei')

    def receive_list_kamikazes(self, list_kamikazes):
        self.kamikazes = list_kamikazes

    def load(self):
        print('carregando')

class Vaporizer(Weapon):

    def fire(self, index_kamikaze):
        # check distance
        #print(f' Atirei no kamikaze me {kamikaze_position}')
        try:
            self.kamikazes.pop(index_kamikaze)
        except:
            #print('All kamikazes were destroyed')
            pass

class Freezing(Weapon):
    pass
