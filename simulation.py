import pygame
from constants import *
from vehicle import Vehicle, VehiclePF, LoyalWingman, Kamikaze
from state_machine import *
import random

vec2 = pygame.math.Vector2
##=========================

class ScreenSimulation(object):

    def __init__(self):
        pygame.init()
        self.font15 = pygame.font.SysFont(None, 15)
        self.font20 = pygame.font.SysFont(None, 20)
        self.font24 = pygame.font.SysFont(None, 24)
        self.size = SCREEN_WIDTH, SCREEN_HEIGHT 
        self.clock = pygame.time.Clock()
        self.screen = pygame.display.set_mode(self.size)

class kamikaze_control(object):
    def __init__(self, num_kamikazes, screen):
        # Creates a kamikaze
        behavior = KamikazeBehaviorTree()
        kamikaze = Kamikaze(SCREEN_WIDTH / 2.0,  SCREEN_HEIGHT / 2.0, behavior, screen)

class Simulation(object):
    
    def __init__(self, screenSimulation):
        self.screenSimulation = screenSimulation

        # state machines for each vehicle
        self.behaviors =[] 
        
        # Current simulations 
        self.swarm = []
        self.kamikazes = []

    def create_swarm_uav(self, num_swarm):
        # Create N simultaneous Drones
        for d in range(0, num_swarm):
            self.behaviors.append( FiniteStateMachine( SeekState() ) ) # Inicial state
            #Instantiate drone 
            #drone = LoyalWingman(SCREEN_WIDTH*d/num_swarm, 10, self.behaviors[-1], self.screenSimulation.screen)
            drone = LoyalWingman(random.uniform(10,SCREEN_WIDTH), 10, self.behaviors[-1], self.screenSimulation.screen)
            self.swarm.append(drone)

        for d in range(0, NUM_KAMIKAZES):
            self.behaviors.append( FiniteStateMachine( WaitState() ) ) # Inicial state
            #Instantiate kamikazes 
            drone = Kamikaze(SCREEN_WIDTH*d/num_swarm, 10, self.behaviors[-1], self.screenSimulation.screen, LoyalWingmen= self.swarm)
            self.kamikazes.append(drone)

    def add_new_uav(self):
        self.behaviors.append( FiniteStateMachine( SeekState() ) )
         #using Old vehicle: steering behavior
        drone = Vehicle(SCREEN_WIDTH/2, SCREEN_HEIGHT/2, self.behaviors[-1], self.screenSimulation.screen)

        #using potential fields
        #drone = VehiclePF(SCREEN_WIDTH*d/num_swarm, 10, self.behaviors[-1], self.screenSimulation.screen)

        drone.set_target(vec2(pygame.mouse.get_pos()[0],pygame.mouse.get_pos()[1]))
        self.append_uav(drone)
    
    def append_uav(self, drone):
        self.swarm.append(drone)

    def create_leading_drone(self):
        pass

    def set_same_target_all(self, target):
        for _ in self.swarm:
            _.set_target(target)

    def goto_formation(self, targets):
        '''
            Set position in formation for drones
        '''
        i = 0
        #print(targets)
        for _ in self.swarm:
            _.set_target(targets[i])
            i += 1

    def run_simulation(self, pos_leader ,list_obst):
        index = 0 # index is used to track current drone in the simulation list
        for _ in self.swarm:
            # checks if drones colided with eachother
            ## collision avoindance is not implemented yet
            _.align_swarm(self.swarm,index)
            _.collision_avoidance(self.swarm,list_obst,index) 
            _.collision_avoidance_leader(pos_leader)
            _.update()
            _.draw(self.screenSimulation.screen) 
            # index to keep track of  drone in the list
            index += 1
            # writes drone id
            img = self.screenSimulation.font20.render(f'LoyalWingman {index}', True, LIGHT_BLUE)
            self.screenSimulation.screen.blit(img, _.get_position()+(0,20))
            # writes drone current behavior
            #img = self.screenSimulation.font20.render(_.behavior.get_current_state(), True, BLUE)
            #self.screenSimulation.screen.blit(img, _.get_position()+(0,30))
            # writes drone current position in column and row
            p = _.get_position()
            col =  int(p.x/RESOLUTION) + 1
            row = int(p.y/RESOLUTION) + 1
            #img = self.screenSimulation.font20.render(f'Pos:{col},{row}', True, BLUE)
            #self.screenSimulation.screen.blit(img, _.get_position()+(0,40))
        
        index = 0 # index is used to track current kamikaze in the simulation list
        for _ in self.kamikazes:
            # checks if drones colided with eachother

            # saves leader position
            _.set_leader_position(pos_leader[-1])
            ## collision avoindance is not implemented yet
            _.align_swarm(self.kamikazes,index)
            _.collision_avoidance(self.kamikazes,list_obst,index) 
            #_.collision_avoidance_leader(pos_leader)
            _.update()
            _.draw(self.screenSimulation.screen) 
            # index to keep track of  drone in the list
            index += 1
            # writes drone id
            img = self.screenSimulation.font20.render(f'Kamikaze {index}', True, LIGHT_BLUE)
            self.screenSimulation.screen.blit(img, _.get_position()+(0,20))
            # writes drone current behavior
            img = self.screenSimulation.font15.render(_.behavior.get_current_state(), True, LIGHT_BLUE)
            self.screenSimulation.screen.blit(img, _.get_position()+(0,30))
            if _.get_explode_state() == True: # delete kamikaze after explotion
                self.kamikazes.pop(index-1)

    def add_new_kamikaze(self):
        self.behaviors.append( FiniteStateMachine( AttackKamikazeState() ) )
        drone = Kamikaze(0, 0, self.behaviors[-1], self.screenSimulation.screen, LoyalWingmen= self.swarm)
        self.kamikazes.append(drone)

    def get_number_running_simultations(self):
        return len(self.swarm)