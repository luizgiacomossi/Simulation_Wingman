import pygame
from constants import *
from vehicle import Vehicle, VehiclePF, LoyalWingman, Kamikaze, LeadingDrone
from state_machine import *
import random
from behavior_tree import *
from decision_making import *
from animation import Explosion_kamikaze
from utils import generate_coordenates_kamikaze
import matplotlib.pyplot as plt

vec2 = pygame.math.Vector2
##=========================

class Rate_Simulation(object):
    def __init__(self):
        super().__init__()
        self.history_enemies_destroyed = []
        self.iterations = 0
        self.time = []

    def print(self):
        pass

    def plot_graphs(self):
        # x = iteration y = enemies destroyed
        plt.close()
        plt.plot([y for y in range(0,self.iterations)], self.history_enemies_destroyed)
        plt.ylabel('iteration vs enemies destroyed')
        plt.show()

        plt.plot([y for y in range(0,self.iterations)], self.time )
        plt.ylabel('iteration vs time')
        plt.show()

    def save_iteration(self, enemies_destroyed, time_elapsed ):
        self.history_enemies_destroyed.append(enemies_destroyed)
        self.iterations += 1
        self.time.append(time_elapsed)


class ScreenSimulation(object):

    def __init__(self):
        pygame.init()
        self.font15 = pygame.font.SysFont(None, 15)
        self.font20 = pygame.font.SysFont(None, 20)
        self.font24 = pygame.font.SysFont(None, 24)
        self.size = SCREEN_WIDTH, SCREEN_HEIGHT 
        self.clock = pygame.time.Clock()
        self.screen = pygame.display.set_mode(self.size,pygame.RESIZABLE)

                #
        # load backgound
        self.background_image = pygame.image.load("models/texture/camouflage.png").convert()
        self.background_image = pygame.transform.scale(self.background_image,(SCREEN_WIDTH,SCREEN_HEIGHT))

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
        self.explosions = []
        self.leadingdrone = []
        #self.create_leading_drone()

        # Counter
        self.counter_kamikazes_destroyed = 0


    def create_swarm_uav(self, num_swarm):
        self.create_leading_drone()
        # Create N simultaneous Drones
        for d in range(0, num_swarm):
            #self.behaviors.append( FiniteStateMachine( SeekState() ) ) # Inicial state
            self.behaviors.append( LoyalWingmanBehaviorTree() ) 
            #Instantiate drone 
            #drone = LoyalWingman(SCREEN_WIDTH*d/num_swarm, 10, self.behaviors[-1], self.screenSimulation.screen)
            drone = LoyalWingman(random.uniform(SCREEN_WIDTH - 300,SCREEN_WIDTH), random.uniform(0 ,30), self.behaviors[-1], self.screenSimulation.screen)
            self.swarm.append(drone)

        for d in range(0, NUM_KAMIKAZES): # creating kamikaze swarm
            self.behaviors.append( FiniteStateMachine( WaitState() ) ) # Inicial state
            #Instantiate kamikazes 
            drone = Kamikaze( random.uniform(0,50), random.uniform(0,50), self.behaviors[-1], self.screenSimulation.screen, LoyalWingmen= self.swarm, leader= self.leadingdrone)
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

    def create_kamikaze(self):
        self.behaviors.append( FiniteStateMachine( AttackKamikazeState() ) ) # Inicial state
        #Instantiate kamikazes 
        position = generate_coordenates_kamikaze()
        drone = Kamikaze( position[0], position[1], self.behaviors[-1], self.screenSimulation.screen, LoyalWingmen= self.swarm, leader= self.leadingdrone)
        self.kamikazes.append(drone)  

    def create_leading_drone(self):
        self.leadingdrone = LeadingDrone(SCREEN_WIDTH/2, SCREEN_HEIGHT/2, FiniteStateMachine( SeekState() ), self.screenSimulation.screen)

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

    def run_simulation(self, pos_leader ,list_obst, time_step = 1):
        
        # updates simulation
        for i in range(time_step): # accelerated factor 

            #--- leading drone
            self.leadingdrone.update()
            pos_leader = [self.leadingdrone.location]

            #--- Loyal Wingman
            for index, _ in enumerate(self.swarm):
                # checks if drones colided with eachother
                ## collision avoindance is not implemented yet
                _.align_swarm(self.swarm,index)
                _.collision_avoidance(self.swarm,list_obst,index) 
                _.collision_avoidance_leader(pos_leader)
                _.update()
                #_.draw(self.screenSimulation.screen)
                _.receive_list_kamikazes(self.kamikazes)   

                # attack logic
                attack_status = _.check_attack()
                if attack_status[1]: # create explosion of kamikaze destroyed
                        self.explosions.append(Explosion_kamikaze( attack_status[0], self.screenSimulation.screen ))
                        _.update_attack_status()

            #--- Kamikazes
            for index, _ in enumerate(self.kamikazes):
                # checks if drones colided with eachother

                # saves leader position
                _.set_leader_position(pos_leader[-1])
                ## collision avoindance is not implemented yet
                _.align_swarm(self.kamikazes,index)
                _.collision_avoidance(self.kamikazes,list_obst,index) 
                #_.collision_avoidance_leader(pos_leader)
                _.update()
                #_.draw(self.screenSimulation.screen) 
                # getting if drone exploded 
                explode_status = _.get_explode_state()
                if explode_status: # Exploded
                    self.explosions.append(Explosion_kamikaze( _.location, self.screenSimulation.screen ))
                
                # index to keep track of  drone in the list
                index += 1
                # # writes drone id
                # img = self.screenSimulation.font20.render(f'Kamikaze {index}', True, LIGHT_BLUE)
                # self.screenSimulation.screen.blit(img, _.get_position()+(0,20))
                # # writes drone current behavior
                # img = self.screenSimulation.font15.render(_.behavior.get_current_state(), True, LIGHT_BLUE)
                # self.screenSimulation.screen.blit(img, _.get_position()+(0,30))


                if _.get_explode_state() == True: # delete kamikaze after explotion
                    self.kamikazes.pop(index-1)

            if len(self.kamikazes) < NUM_KAMIKAZES: # Keeps contant number of kamikazes
                # counts loyal destroyed
                self.counter_kamikazes_destroyed += 1

                # creates new kamikaze
                self.create_kamikaze()

            # updates positions in formation
                #set target for all loyal wingman
            list_pos = self.leadingdrone.set_formation(num_drones = self.get_number_running_simultations())
            self.goto_formation(list_pos) 

            # update explosions
            for index, _ in enumerate(self.explosions):
                _.draw() # Updates explosion on screen
                if _.delete_explosion_status(): # check if it is time to delete
                    self.explosions.pop(index)


        #-------- draw animations
        pygame.draw.circle(self.screenSimulation.screen,(200, 250, 200), self.leadingdrone.get_position() , radius=DISTANCE_LEADER, width = 3)
        self.leadingdrone.draw(self.screenSimulation.screen)
        
        for index, _ in enumerate(self.kamikazes):
            _.draw(self.screenSimulation.screen) 
            index += 1
                            # writes drone id
            img = self.screenSimulation.font20.render(f'Kamikaze {index}', True, LIGHT_BLUE)
            self.screenSimulation.screen.blit(img, _.get_position()+(0,20))
                # writes drone current behavior
            img = self.screenSimulation.font15.render(_.behavior.get_current_state(), True, LIGHT_BLUE)
            self.screenSimulation.screen.blit(img, _.get_position()+(0,30))


        for index, _ in enumerate(self.swarm):
            _.draw(self.screenSimulation.screen)
                        # index to keep track of  drone in the list
            index += 1
                # writes drone id
            img = self.screenSimulation.font20.render(f'LoyalWingman {index}', True, LIGHT_BLUE)
            self.screenSimulation.screen.blit(img, _.get_position()+(0,20))
                # writes drone current behavior
                #img = self.screenSimulation.font20.render(_.behavior.node_name, True, BLUE)
                #self.screenSimulation.screen.blit(img, _.get_position()+(0,30))
                # writes drone current position in column and row
            p = _.get_position()
            col =  int(p.x/RESOLUTION) + 1
            row = int(p.y/RESOLUTION) + 1

                # writes drone ammo available
            ammo_vaporizer = _.vaporizer_gun.get_ammo_available()
            ammo_freezing = _.vaporizer_gun.get_ammo_available()
            img = self.screenSimulation.font15.render(f'V: {ammo_vaporizer} F:{ammo_freezing} ', True, LIGHT_BLUE)
            self.screenSimulation.screen.blit(img, _.get_position()+(0,30))
                #img = self.screenSimulation.font20.render(f'Pos:{col},{row}', True, BLUE)
                #self.screenSimulation.screen.blit(img, _.get_position()+(0,40))

    def add_new_kamikaze(self):
        self.behaviors.append( FiniteStateMachine( AttackKamikazeState() ) )
        drone = Kamikaze(0, random.uniform(0,SCREEN_HEIGHT), self.behaviors[-1], self.screenSimulation.screen, LoyalWingmen= self.swarm)
        self.kamikazes.append(drone)

    def update_background(self):
        info = pygame.display.Info() # You have to call this before pygame.display.set_mode()
        screen_width,screen_height = info.current_w,info.current_h
        # Background
        background_image = self.screenSimulation.background_image
        background_image = pygame.transform.scale(background_image,(screen_width,screen_height))
        self.screenSimulation.screen.blit(background_image, [0, 0])

    def set_target_leader(self, target):
        # define new target to leader
        self.leadingdrone.set_target(target)
        # updates loyalwingman positions in formation 
        list_pos = self.leadingdrone.set_formation()
        self.goto_formation(list_pos) 

    def get_number_running_simultations(self):
        return len(self.swarm)

    def get_kamikazes_destroyed(self):
        return self.counter_kamikazes_destroyed

    def reset(self):
        pass