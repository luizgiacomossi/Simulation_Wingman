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
            
            # Key 'd' pressed
            if event.type == pygame.KEYDOWN and event.key == pygame.K_d:
                for _ in self.simulation.swarm:
                    _.set_debug()

            # Mouse Clicked -> new taget or new Drone 
            if event.type == pygame.MOUSEBUTTONDOWN:
                # left button - New Target
                if pygame.mouse.get_pressed()[0] == True:
                    # moves leading drone to point clicked
                    target_leading = vec2(pygame.mouse.get_pos()[0],pygame.mouse.get_pos()[1])
                    self.simulation.set_target_leader(target_leading)

                # right button - New KAMIKAZE
                if pygame.mouse.get_pressed()[2] == True:
                    self.simulation.add_new_kamikaze()              
            
            if event.type == pygame.KEYDOWN and event.key == pygame.K_p:  
                # plot history
                self.history.plot_graphs()
                self.history.print()

            if event.type == pygame.KEYDOWN and event.key == pygame.K_UP:  
                self.simulation.accelerated_factor += 5

            if event.type == pygame.KEYDOWN and event.key == pygame.K_DOWN:   
                if self.simulation.accelerated_factor > 0 :
                   self.simulation.accelerated_factor -= 5

            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:   
                   self.simulation.accelerated_factor = 1

class Rate_Simulation(object):
    def __init__(self):
        super().__init__()
        self.history_enemies_destroyed = []
        self.iterations = 0
        self.time = []
        self.counter_loyalwingman_survived = []
        self.quality = []

    def print(self):

        print('=========================================||Result||========================================')
        print(f'Média de kamikazes destruidos : {statistics.mean(self.history_enemies_destroyed)} Std: {statistics.stdev(self.history_enemies_destroyed)} Var: {statistics.variance(self.history_enemies_destroyed)}')
        print(f'Média de Tempo de sobrevivencia  : {statistics.mean(self.time)} Std: {statistics.stdev(self.time)} Var: {statistics.variance(self.time)}')
        print(f'Média de loyalwingman que restaram : {statistics.mean(self.counter_loyalwingman_survived)} Std: {statistics.stdev(self.counter_loyalwingman_survived)} Var: {statistics.variance(self.counter_loyalwingman_survived)}')
        print('===========================================================================================')
  
 # 
    def plot_graphs(self):
        # x = iteration y = enemies destroyed
        # Plot the responses for different events and regions

        plt.close()
        plt.plot([y for y in range(0,self.iterations)], self.history_enemies_destroyed)
        plt.ylabel('Iteration vs Enemies Destroyed')
        plt.show()

        plt.plot([y for y in range(0,self.iterations)], self.time )
        plt.ylabel('Iteration vs Time')
        plt.show()

        plt.plot([y for y in range(0,self.iterations)], self.quality )
        plt.ylabel('Iteration vs Quality')
        plt.show()

        plt.plot([y for y in range(0,self.iterations)], self.counter_loyalwingman_survived )
        plt.ylabel('# of loyalwingman survided')
        plt.show()

    def save_iteration(self, enemies_destroyed, time_elapsed, loyal_wingman_survived , quality ):
        self.history_enemies_destroyed.append(enemies_destroyed)
        #self.history_enemies_destroyed  = np.append(self.history_enemies_destroyed,enemies_destroyed)
        self.iterations += 1
        self.time.append(time_elapsed)
        self.counter_loyalwingman_survived.append(loyal_wingman_survived)
        self.quality.append(quality)

    def evaluate(self, enemies_destroyed, time_elapsed, loyal_wingman_survived ):
        """
        Evaluates the simulation based on the metrics.

        :return: reward for the current situation.
        :rtype: float.
        """

        # reward é baseada no calculo de:
            # enemies_destroyed
            # time_elapsed
            # loyal_wingman_survived

        reward =  enemies_destroyed**2  + 10 * time_elapsed - loyal_wingman_survived*1000  
 
        # medida de qualidade:
            # medida de qualidade recompensa o robô por cumprir o caminho
            # mais rapidamente, enquanto o penaliza por desviar da linha
        return reward  #

class ScreenSimulation(object):

    def __init__(self):
        pygame.init()
        self.font15 = pygame.font.SysFont(None, 15)
        self.font20 = pygame.font.SysFont(None, 20)
        self.font24 = pygame.font.SysFont(None, 24)
        self.size = SCREEN_WIDTH, SCREEN_HEIGHT 
        self.clock = pygame.time.Clock()
        self.screen = pygame.display.set_mode(self.size,pygame.RESIZABLE,  pygame.SRCALPHA)

        # load backgound
        self.background_image = pygame.image.load("models/texture/camouflage.png").convert()
        self.background_image = pygame.transform.scale(self.background_image,(SCREEN_WIDTH,SCREEN_HEIGHT))

    def WriteLegendOnCanvas(self, simulation, accelerated_factor , time_running, history):

        # Writes the App name in screen
        img = self.font24.render('Loyal Wingman Simulation', True, LIGHT_BLUE)
        self.screen.blit(img, (20, 20))
        # Writes the App name in screen
        img = self.font20.render(f'Accelerated Factor: {accelerated_factor}', True, LIGHT_BLUE)
        self.screen.blit(img, (20, 40))
        #   Writes # Loyal in  screen
        img = self.font24.render(f'#loyal wingman: {simulation.get_number_running_simultations()}', True, LIGHT_BLUE)
        self.screen.blit(img, (20, 60))
        img = self.font24.render(f'#KamikazesDestroyed: {simulation.get_kamikazes_destroyed()}', True, LIGHT_BLUE)
        self.screen.blit(img, (20, 80))
        img = self.font24.render(f'Time: {time_running:0.2f}', True, LIGHT_BLUE)
        self.screen.blit(img, (20, 100))
        img = self.font24.render(f'Iteration: {history.iterations+1}', True, LIGHT_BLUE)
        self.screen.blit(img, (20, 120))
        img = self.font24.render(f'Iteration using: #loyal {simulation.num_loyalwingman} #kamikazes {simulation.num_kamikazes}', True, LIGHT_BLUE)
        self.screen.blit(img, (20, 140))

class kamikaze_control(object):
    def __init__(self, num_kamikazes, screen):
        # Creates a kamikaze
        behavior = KamikazeBehaviorTree()
        kamikaze = Kamikaze(SCREEN_WIDTH / 2.0,  SCREEN_HEIGHT / 2.0, behavior, screen)

class Simulation(object):
    
    def __init__(self, screenSimulation):
        self.screenSimulation = screenSimulation
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
                                            window= self.screenSimulation.screen)
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
            #drone = LoyalWingman(SCREEN_WIDTH*d/num_swarm, 10, self.behaviors[-1], self.screenSimulation.screen)
            drone = LoyalWingman(random.uniform(SCREEN_WIDTH - 300,SCREEN_WIDTH),
                                 random.uniform(0 ,30), self.behaviors[-1],
                                 self.screenSimulation.screen,
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
                            self.screenSimulation.screen, 
                            LoyalWingmen= self.swarm, 
                            leader= self.leadingdrone,
                            protected_area = self.protected_area)
                            
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
                         self.screenSimulation.screen, 
                         LoyalWingmen= self.swarm, 
                         leader= self.leadingdrone,
                         protected_area = self.protected_area)
        self.kamikazes.append(drone)  

    def create_leading_drone(self, distance_formation):
        self.leadingdrone = LeadingDrone(SCREEN_WIDTH/2, 
                                        SCREEN_HEIGHT/2, 
                                        FiniteStateMachine( SeekState() ), 
                                        self.screenSimulation.screen,
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
                # check protected area
                _.check_protected_area()
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
        pygame.draw.circle(self.screenSimulation.screen,(200, 250, 200), self.leadingdrone.get_position() , radius= self.distance_formation , width = 3)
        self.leadingdrone.draw(self.screenSimulation.screen)
        img = self.screenSimulation.font20.render(f'Leading Drone', True, LIGHT_BLUE)
        self.screenSimulation.screen.blit(img, self.leadingdrone.get_position()+(0,20))

        ## ------
        for index, _ in enumerate(self.swarm):
            _.draw(self.screenSimulation.screen)
                        # index to keep track of  drone in the list
            index += 1
                # writes drone id
            img = self.screenSimulation.font20.render(f'LoyalWingman {index}', True, LIGHT_BLUE)
            self.screenSimulation.screen.blit(img, _.get_position()+(0,20))
                # writes drone current behavior
            #img = self.screenSimulation.font20.render(_.behavior.root.node_name, True, BLUE)
            #self.screenSimulation.screen.blit(img, _.get_position()+(0,40))
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

        #draw protected area
        self.protected_area.draw()

        for index, _ in enumerate(self.kamikazes):
            _.draw(self.screenSimulation.screen) 
            index += 1
                            # writes drone id
            img = self.screenSimulation.font20.render(f'Kamikaze {index}', True, LIGHT_BLUE)
            self.screenSimulation.screen.blit(img, _.get_position()+(0,20))
                # writes drone current behavior
            img = self.screenSimulation.font15.render(_.behavior.get_current_state(), True, LIGHT_BLUE)
            self.screenSimulation.screen.blit(img, _.get_position()+(0,30))

        #-------- end draw animations ---------

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
        # Draw line to delimit were kamikazes are born
        pygame.draw.line(self.screenSimulation.screen, (100,200,100), vec2(screen_width/3,0) , vec2(screen_width/3, screen_height), 10)

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