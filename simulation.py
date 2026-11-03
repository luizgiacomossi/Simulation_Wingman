import pygame
import sys, pygame, os
from constants import *
from vehicle import Vehicle, VehiclePF, LoyalWingman, Kamikaze, LeadingDrone
from state_machine import *
import random
from behavior_tree import *
from decision_making import *
from animation import Explosion_kamikaze, ProtectedArea
from utils import generate_coordenates_kamikaze
from quadtree import Quadtree, Rect
from display_manager import DisplayManager
from experiment_manager import ExperimentManager
import matplotlib.pyplot as plt
import statistics

vec2 = pygame.math.Vector2
##=========================

class ProcessorUserInput:
    def __init__(self, simulation, history):
        super().__init__()
        self.history = history
        self.simulation = simulation

    def read(self):
        # Pygame Events 
        for event in pygame.event.get():
            if event.type == pygame.QUIT: sys.exit()

            # Forward zoom and pan to display_manager
            if hasattr(self.simulation, 'screenSimulation') and hasattr(self.simulation.screenSimulation, 'handle_event'):
                self.simulation.screenSimulation.handle_event(event)

            # Key 'd' pressed
            if event.type == pygame.KEYDOWN and event.key == pygame.K_d:
                for _ in self.simulation.swarm:
                    _.set_debug()

            # Key 'c' pressed -> Center camera on leader
            if event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                if hasattr(self.simulation, 'leadingdrone') and hasattr(self.simulation.leadingdrone, 'location'):
                    self.simulation.screenSimulation.center_on(self.simulation.leadingdrone.location)

            # Key '0' or 'HOME' -> Reset zoom/pan
            if event.type == pygame.KEYDOWN and (event.key == pygame.K_0 or event.key == pygame.K_HOME):
                self.simulation.screenSimulation.reset_view()

            # Mouse Clicked -> new target or new Drone 
            if event.type == pygame.MOUSEBUTTONDOWN:
                raw_mouse = vec2(pygame.mouse.get_pos()[0], pygame.mouse.get_pos()[1])
                world_pos = self.simulation.screenSimulation.screen_to_world(raw_mouse)

                # left button - New Target
                if pygame.mouse.get_pressed()[0] == True:
                    # moves leading drone to point clicked in world coordinates
                    self.simulation.set_target_leader(world_pos)

                # right button - New KAMIKAZE
                if pygame.mouse.get_pressed()[2] == True:
                    self.simulation.add_new_kamikaze(pos=world_pos)              
            
            if event.type == pygame.KEYDOWN and event.key == pygame.K_p:  
                # plot history
                self.history.plot_graphs()
                self.history.print()

            if event.type == pygame.KEYDOWN and event.key == pygame.K_UP:  
                self.simulation.accelerated_factor += 3

            if event.type == pygame.KEYDOWN and event.key == pygame.K_DOWN:   
                if self.simulation.accelerated_factor > 0 :
                   self.simulation.accelerated_factor -= 3

            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:   
                   self.simulation.accelerated_factor = 1

class Rate_Simulation(ExperimentManager):
    """
    Maintains backward compatibility with Rate_Simulation while leveraging
    ExperimentManager for CSV export, telemetry, and metrics tracking.
    """
    pass

class ScreenSimulation(DisplayManager):
    """
    Maintains backward compatibility with ScreenSimulation while providing
    full DisplayManager features (zoom, pan, subsurface scaling).
    """
    pass

class kamikaze_control(object):
    def __init__(self, num_kamikazes, screen):
        # Creates a kamikaze
        behavior = KamikazeBehaviorTree()
        kamikaze = Kamikaze(SCREEN_WIDTH / 2.0,  SCREEN_HEIGHT / 2.0, behavior, screen)

class Simulation(object):
    
    def __init__(self, screenSimulation):
        self.screenSimulation = screenSimulation
        self.canvas = getattr(self.screenSimulation, 'world_surface', self.screenSimulation.screen)
        self.accelerated_factor = 1
        # state machines for each vehicle
        self.behaviors =[] 
        # Current simulations 
        self.swarm = []
        self.kamikazes = []
        self.explosions = []
        self.leadingdrone = []
        self.protected_area = ProtectedArea(radius=240,
                                            coordenates=vec2(1800,170),
                                            window= self.canvas)
        #self.create_leading_drone()
        # Counter
        self.counter_kamikazes_destroyed = 0
        # 
        self.num_kamikazes: int 
        self.num_loyalwingman: int
        self.distance_formation: float
        self.distance_rings_formation: float

    def create_swarm_uav(self, num_swarm, num_kamikazes, 
                        distance_chase = 400, 
                        kp= 0.625, 
                        kv= 4.5, 
                        distance_formation = DISTANCE_LEADER, 
                        distance_rings_formation = 1.2):

        self.distance_rings_formation = distance_rings_formation
        self.distance_formation = distance_formation
        self.create_leading_drone(distance_formation= distance_formation)
        
        # save parameters
        self.num_kamikazes = num_kamikazes 
        self.num_loyalwingman = num_swarm 


        # Create N simultaneous Drones
        for d in range(0, num_swarm):
            #self.behaviors.append( FiniteStateMachine( SeekState() ) ) # Inicial state
            self.behaviors.append( LoyalWingmanBehaviorTree() ) 
            #Instantiate drone 
            drone = LoyalWingman(random.uniform(SCREEN_WIDTH - 300,SCREEN_WIDTH),
                                 random.uniform(0 ,30), self.behaviors[-1],
                                 self.canvas,
                                 self.protected_area,
                                 distance_chase,
                                 #distance_chase[d],
                                 kp,
                                 kv)

            self.swarm.append(drone)

        for d in range(0, num_kamikazes): # creating kamikaze swarm
            self.behaviors.append( FiniteStateMachine( WaitState() ) ) # Inicial state
            #Instantiate kamikazes 
            drone = Kamikaze(random.uniform(0,50), 
                            random.uniform(0,50), 
                            self.behaviors[-1], 
                            self.canvas, 
                            LoyalWingmen= self.swarm, 
                            leader= self.leadingdrone,
                            protected_area = self.protected_area)
                            
            self.kamikazes.append(drone)

    def add_new_uav(self):
        self.behaviors.append( FiniteStateMachine( SeekState() ) )
        drone = Vehicle(SCREEN_WIDTH/2, SCREEN_HEIGHT/2, self.behaviors[-1], self.canvas)
        mouse_pos = vec2(pygame.mouse.get_pos()[0], pygame.mouse.get_pos()[1])
        world_pos = self.screenSimulation.screen_to_world(mouse_pos)
        drone.set_target(world_pos)
        self.append_uav(drone)
    
    def append_uav(self, drone):
        self.swarm.append(drone)

    def create_kamikaze(self):
        prob = uniform(0,1) # 50% will attack leader and 50% attack leader
        if prob < 0.33:
            self.behaviors.append( FiniteStateMachine( AttackLeaderState() ) ) # Inicial state
        elif prob >= 0.33 and prob < 0.66:
            self.behaviors.append( FiniteStateMachine( AttackLoyalWingmanState() ) ) # Inicial state
        else:
            self.behaviors.append( FiniteStateMachine( AttackProtectedAreaState() ) ) # Inicial state

        #Instantiate kamikazes 
        position = generate_coordenates_kamikaze()
        drone = Kamikaze(position[0], 
                         position[1], 
                         self.behaviors[-1], 
                         self.canvas, 
                         LoyalWingmen= self.swarm, 
                         leader= self.leadingdrone,
                         protected_area = self.protected_area)
        self.kamikazes.append(drone)  

    def create_leading_drone(self, distance_formation):
        self.leadingdrone = LeadingDrone(SCREEN_WIDTH/2, 
                                        SCREEN_HEIGHT/2, 
                                        FiniteStateMachine( SeekState() ), 
                                        self.canvas,
                                        distance_leader = distance_formation,
                                        distance_rings_formation= self.distance_rings_formation)

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

    def run_simulation(self, pos_leader ,list_obst, accelerated_factor = 1):
        
        # updates simulation
        for i in range(accelerated_factor): # accelerated factor 

            #--- leading drone
            self.leadingdrone.update()
            pos_leader = [self.leadingdrone.location]

            # Build Quadtrees for spatial partitioning
            boundary = Rect(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
            quadtree_loyal = Quadtree(boundary, 4)
            for drone in self.swarm:
                quadtree_loyal.insert(drone.location, drone)

            quadtree_kamikazes = Quadtree(boundary, 4)
            for k in self.kamikazes:
                quadtree_kamikazes.insert(k.location, k)

            #--- Loyal Wingman
            for index, _ in enumerate(self.swarm):
                # checks if drones collided with each other using Quadtree
                _.align_swarm(quadtree_loyal, index)
                _.collision_avoidance(quadtree_loyal, list_obst, index) 
                _.collision_avoidance_leader(pos_leader)
                _.update()
                #_.draw(self.screenSimulation.screen)
                _.receive_list_kamikazes(self.kamikazes, quadtree_kamikazes)   

                # attack logic
                attack_status = _.check_attack()
                if attack_status[1]: # create explosion of kamikaze destroyed
                        self.explosions.append(Explosion_kamikaze( attack_status[0], self.canvas ))
                        _.update_attack_status()

            #--- Kamikazes
            for index, _ in enumerate(self.kamikazes):
                # saves leader position and loyal quadtree for target selection
                _.set_leader_position(pos_leader[-1])
                _.set_quadtree_loyal(quadtree_loyal)
                _.align_swarm(quadtree_kamikazes, index)
                _.collision_avoidance(quadtree_kamikazes, list_obst, index) 
                #_.collision_avoidance_leader(pos_leader)
                _.update()
                # check protected area
                _.check_protected_area()
                #_.draw(self.canvas) 
                # getting if drone exploded 
                explode_status = _.get_explode_state()
                if explode_status: # Exploded
                    self.explosions.append(Explosion_kamikaze( _.location, self.canvas ))
                
                # index to keep track of  drone in the list
                index += 1

                if _.get_explode_state() == True: # delete kamikaze after explotion
                    self.kamikazes.pop(index-1)

            if len(self.kamikazes) < self.num_kamikazes: # Keeps contant number of kamikazes
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

        #draw leading drone
        pygame.draw.circle(self.canvas,(200, 250, 200), self.leadingdrone.get_position() , radius= self.distance_formation , width = 3)
        self.leadingdrone.draw(self.canvas)
        img = self.screenSimulation.font20.render(f'Leading Drone', True, LIGHT_BLUE)
        self.canvas.blit(img, self.leadingdrone.get_position()+(0,20))

        ## ------
        for index, _ in enumerate(self.swarm):
            _.draw(self.canvas)
            index += 1
            # writes drone id
            img = self.screenSimulation.font20.render(f'LoyalWingman {index}', True, LIGHT_BLUE)
            self.canvas.blit(img, _.get_position()+(0,20))

            # writes drone ammo available
            ammo_vaporizer = _.vaporizer_gun.get_ammo_available()
            ammo_freezing = _.vaporizer_gun.get_ammo_available()
            img = self.screenSimulation.font15.render(f'V: {ammo_vaporizer} F:{ammo_freezing} ', True, LIGHT_BLUE)
            self.canvas.blit(img, _.get_position()+(0,30))

        #draw protected area
        self.protected_area.draw()

        for index, _ in enumerate(self.kamikazes):
            _.draw(self.canvas) 
            index += 1
            # writes drone id
            img = self.screenSimulation.font20.render(f'Kamikaze {index}', True, LIGHT_BLUE)
            self.canvas.blit(img, _.get_position()+(0,20))
            # writes drone current behavior
            img = self.screenSimulation.font15.render(_.behavior.get_current_state(), True, LIGHT_BLUE)
            self.canvas.blit(img, _.get_position()+(0,30))

        #-------- end draw animations ---------

    def add_new_kamikaze(self, pos=None):
        self.behaviors.append( FiniteStateMachine( AttackKamikazeState() ) )
        if pos is None:
            pos = vec2(0, random.uniform(0, SCREEN_HEIGHT))
        drone = Kamikaze(pos.x, pos.y, self.behaviors[-1], self.canvas, LoyalWingmen= self.swarm, leader= self.leadingdrone, protected_area= self.protected_area)
        self.kamikazes.append(drone)

    def update_background(self):
        # Draw background and delimitation line on canvas
        if self.screenSimulation.background_image is not None:
            self.canvas.blit(self.screenSimulation.background_image, [0, 0])
        else:
            self.canvas.fill((40, 44, 52))
        pygame.draw.line(self.canvas, (100, 200, 100), vec2(WORLD_WIDTH / 3, 0), vec2(WORLD_WIDTH / 3, WORLD_HEIGHT), 10)

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