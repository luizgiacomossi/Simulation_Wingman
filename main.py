import sys, pygame
from constants import *
import random 
import copy
from utils import FlowField
from obstacle import Obstacles
from simulation import Simulation, ScreenSimulation
from vehicle import LeadingDrone, LoyalWingman, Kamikaze
from state_machine import FiniteStateMachine, SeekState
from behavior_tree import KamikazeBehaviorTree

vec2 = pygame.math.Vector2
##=========================
screenSimulation = ScreenSimulation()
# load backgound
background_image = pygame.image.load("models/texture/camouflage.png").convert()
background_image = pygame.transform.scale(background_image,(SCREEN_WIDTH,SCREEN_HEIGHT))
# defines initial target
target = vec2(random.uniform(0,SCREEN_WIDTH/2), random.uniform(0,SCREEN_HEIGHT/2))

# Generates obstacles
list_obst = []
obst = Obstacles(NUM_OBSTACLES, (SCREEN_WIDTH,SCREEN_HEIGHT))
obst.generate_obstacles()
# To generate obstacles, uncomment following command
list_obst = obst.get_coordenates()

#creates flow field - not used neither fully implemented, flow field can be used as wind
#flow_field = FlowField(RESOLUTION)

simulation = Simulation(screenSimulation)
simulation.create_swarm_uav(NUM_DRONES)

# Creates Leading Drone 
avoid_list =[]
leadingdrone = LeadingDrone(SCREEN_WIDTH/2, SCREEN_HEIGHT/2, FiniteStateMachine( SeekState() ), screenSimulation.screen)
avoid_list.append(leadingdrone.location)


# simulation = Simulation(roomba)

run = True
while run:
    # Draws at every dt
    screenSimulation.clock.tick(FREQUENCY)

    # Pygame Events 
    for event in pygame.event.get():
        if event.type == pygame.QUIT: sys.exit()
        
        # Key 'd' pressed
        if event.type == pygame.KEYDOWN and event.key == pygame.K_d:
            for _ in simulation.swarm:
                _.set_debug()

        # Mouse Clicked -> new taget or new Drone 
        if event.type == pygame.MOUSEBUTTONDOWN:
            # left button - New Target
            if pygame.mouse.get_pressed()[0] == True:
                # moves leading drone to point clicked
                target_leading = vec2(pygame.mouse.get_pos()[0],pygame.mouse.get_pos()[1])
                leadingdrone.set_target(target_leading)
                list_pos = leadingdrone.set_formation()
                #set target for all loyal wingman
                simulation.goto_formation(list_pos) 
               
            # right button - New Drone
            if pygame.mouse.get_pressed()[2] == True:
                simulation.add_new_uav()              
                
    # Background
    #screenSimulation.screen.fill(LIGHT_BLUE)
    screenSimulation.screen.blit(background_image, [0, 0])
    # Draws obstacles:

    #updates and draws leading drone
    pygame.draw.circle(screenSimulation.screen,(200, 250, 200), leadingdrone.get_position() , radius=DISTANCE_LEADER, width = 3)

    # draw grid
    #flow_field.draw(screen)

    # updates and draws all simulations  
    simulation.run_simulation(avoid_list,list_obst)

    #set target for all loyal wingman
    list_pos = leadingdrone.set_formation()
    simulation.goto_formation(list_pos) 
    
    leadingdrone.update()
    leadingdrone.draw(screenSimulation)

    for _ in list_obst:
        pygame.draw.circle(screenSimulation.screen,(200, 250, 200), _ , radius=RADIUS_OBSTACLES, width = 2)
        pygame.draw.circle(screenSimulation.screen,(200, 250, 200), _ , radius=RADIUS_OBSTACLES*1.6 + AVOID_DISTANCE, width = 2)
        obst.all_sprites.draw(screenSimulation.screen)
        obst.all_sprites.update(_,0)
    
    # Writes the App name in screen
    img = screenSimulation.font24.render('Loyal Wingman Simulation', True, LIGHT_BLUE)
    screenSimulation.screen.blit(img, (20, 20))

    # Debug lines - only to assist the developer
    #img = screenSimulation.font24.render('Debug lines: '+ drone.get_debug(), True, BLUE)
    #screenSimulation.screen.blit(img, (20, 40))

    pygame.display.flip() 