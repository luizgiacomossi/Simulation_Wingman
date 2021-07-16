import sys, pygame, os
from constants import *
import random 
import copy
from utils import FlowField
from obstacle import Obstacles
from simulation import Simulation, ScreenSimulation, Rate_Simulation, ProcessorUserInput
from vehicle import LeadingDrone, LoyalWingman, Kamikaze
from state_machine import FiniteStateMachine, SeekState, RandomWalkState
os.environ['SDL_VIDEO_CENTERED'] = '1' 
vec2 = pygame.math.Vector2

##=================================================================================================
screenSimulation = ScreenSimulation()

# Generates obstacles
list_obst = []
obst = Obstacles(NUM_OBSTACLES, (SCREEN_WIDTH,SCREEN_HEIGHT))
obst.generate_obstacles()
# To generate obstacles, uncomment following command
#list_obst = obst.get_coordenates()

simulation = Simulation(screenSimulation)
simulation.create_swarm_uav(NUM_DRONES)
history = Rate_Simulation()

# Creates Leading Drone 
avoid_list =[]

run = True
accelerated_factor = 1
time_running = 0

# Input Processor
input_processor = ProcessorUserInput(simulation,history)

while run:
    # Draws at every dt
    time_running += SAMPLE_TIME*simulation.accelerated_factor
    screenSimulation.clock.tick(FREQUENCY)

    # Process user input - Pygame Events 
    input_processor.read()
    # Draw scenario
    simulation.update_background()
    # updates and draws all simulated UAVs  
    simulation.run_simulation(avoid_list,list_obst, simulation.accelerated_factor)
    # draw obstacles 
    for _ in list_obst:
        pygame.draw.circle(screenSimulation.screen,(200, 250, 200), _ , radius=RADIUS_OBSTACLES, width = 2)
        pygame.draw.circle(screenSimulation.screen,(200, 250, 200), _ , radius=RADIUS_OBSTACLES*1.6 + AVOID_DISTANCE, width = 2)
        obst.all_sprites.draw(screenSimulation.screen)
        obst.all_sprites.update(_,0)
    
    # Writes the App name in screen
    screenSimulation.WriteLegendOnCanvas(simulation, simulation.accelerated_factor, time_running, history)

    # Reset simulation if finnished
    if simulation.get_number_running_simultations() < 1 or simulation.leadingdrone.destroyed == True:
        # save data
        enemies_destroyed = simulation.get_kamikazes_destroyed()
        history.save_iteration(enemies_destroyed,time_running, simulation.get_number_running_simultations())

        # generates new iteration
        accelerated_factor = simulation.accelerated_factor
        simulation = Simulation(screenSimulation)
        simulation.create_swarm_uav(NUM_DRONES)
        pygame.time.wait(1000)
        time_running = 0
        simulation.accelerated_factor = accelerated_factor
        input_processor = ProcessorUserInput(simulation,history)

    pygame.display.flip() 

