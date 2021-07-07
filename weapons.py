from constants import *

class Weapon(object):
    def __init__(self, cooldown, num_cartridges , rate_of_fire, range_of_fire, swarm_kamikazes):
        self.cooldown = cooldown
        self.num_cartridges = num_cartridges
        self.rate_of_fire = rate_of_fire
        self.range_of_fire = range_of_fire
        self.kamikazes = swarm_kamikazes
        self.available = True

    def fire(self):
        print('atirei')

    def receive_list_kamikazes(self, list_kamikazes):
        self.kamikazes = list_kamikazes

    def load(self):
        print('carregando')
    
    def get_ammo_available(self):
        return self.num_cartridges 

class Vaporizer(Weapon):
    def __init__(self, cooldown, num_cartridges, rate_of_fire, range_of_fire, swarm_kamikazes):
        super().__init__(cooldown, num_cartridges, rate_of_fire, range_of_fire, swarm_kamikazes)


    def fire(self, index_kamikaze):
        # check distance
        #print(f' Atirei no kamikaze me {kamikaze_position}')
        try:
            if self.num_cartridges > 0:
                self.kamikazes.pop(index_kamikaze)
                self.num_cartridges -= 1
                return True
            else:
                return False
        except:
            #print('All kamikazes were destroyed')
            pass


class Freezing(Weapon):
    def __init__(self, cooldown, num_cartridges, rate_of_fire, range_of_fire, swarm_kamikazes):
        super().__init__(cooldown, num_cartridges, rate_of_fire, range_of_fire, swarm_kamikazes)

    def fire(self, index_kamikaze):
        # check distance
        #print(f' Atirei no kamikaze me {kamikaze_position}')
        try:
            if self.num_cartridges > 0:
                self.kamikazes[index_kamikaze].slow_down() 
                self.num_cartridges -= 1
                return True
            else:
                return False
        except:
            #print('All kamikazes were destroyed')
            pass