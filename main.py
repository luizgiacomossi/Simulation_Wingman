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
from dataclasses import dataclass
from particle_swarm_optimization import *
##========================= PSO ===================================================
def convert_particle_position_to_params(position):
    """
    Converts a particle position into controller params.
    :param position: particle position.
    :type position: numpy array.
    :return: controller params.
    """
    params = Parameters()
    #params.num_loyalwingman = int(position[0])
    #params.num_kamikazes = int(position[1])
    params.distance_chase = position[0]
    params.formation_distance = position[1]
    params.distance_rings_formation = position[2]

    return params

@dataclass
class Parameters:
    """
    Represents an auxiliary class for storing parameters.
    """
    pass

# Defining PSO hyperparameters
hyperparams = Parameters()
hyperparams.num_particles = 40
hyperparams.inertia_weight = 0.7
hyperparams.cognitive_parameter = 0.6
hyperparams.social_parameter = 0.8
# distance_chase,formation_distance
lower_bound = np.array([10  ,  0 , 0])
upper_bound = np.array([1000, 300, 4])

# Particle Swarm Optimization
pso = ParticleSwarmOptimization(hyperparams, lower_bound, upper_bound)
# Number of function evaluations will be 1000 times the number of particles,
# i.e. PSO will be executed by 100 generations
num_evaluations = 100 * hyperparams.num_particles
# Initializing history
position_history = []  # history of evaluated particle positions
quality_history = []  # history of evaluated qualities

# Getting the first parameters to evaluate
position = pso.get_position_to_evaluate()
simulation_params = convert_particle_position_to_params(position)
running_PSO = False
##=================================================================================================
screenSimulation = ScreenSimulation()

# Generates obstacles
list_obst = []
obst = Obstacles(NUM_OBSTACLES, (SCREEN_WIDTH,SCREEN_HEIGHT))
obst.generate_obstacles()
# To generate obstacles, uncomment following command
#list_obst = obst.get_coordenates()

simulation = Simulation(screenSimulation)
# para testar o pso, depois retirar esse comentario !!!!!!
if running_PSO:
    simulation.create_swarm_uav(NUM_DRONES,
                                NUM_KAMIKAZES,
                                simulation_params.distance_chase,
                                #300.7,
                                #kp=29.85,
                                #kv=37.31,
                                #distance_formation = DISTANCE_LEADER)
                                #distance_formation = 69.02)
                                distance_formation = simulation_params.formation_distance)
                                #distance_rings_formation = simulation_params.distance_rings_formation)
else:
    simulation.create_swarm_uav(NUM_DRONES, 
                                NUM_KAMIKAZES, 
                                #distance_chase = 352, parameter using optimization
                                distance_chase = 306.6,
                                distance_formation = 100.1)
                                #distance_formation = 62,
                                #distance_rings_formation = 2.37)
# 306.57304199 100.1527203  # com 1 ring e distancias de engajamento e do lider

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
    if simulation.accelerated_factor>0:
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
    if simulation.get_number_running_simultations() < 1 or simulation.leadingdrone.destroyed == True or len(simulation.kamikazes) == 0 or simulation.protected_area.is_active() == False  : 
        
        enemies_destroyed = simulation.get_kamikazes_destroyed()
        # ====== PSO =======
        quality = history.evaluate(enemies_destroyed, time_running, simulation.get_number_running_simultations() )
        # save data
        history.save_iteration(enemies_destroyed,
                                time_running, 
                                simulation.get_number_running_simultations(),
                                quality)

                    # Prints the results of the current training iteration
        print('iter: ' + str(history.iterations) + ', quality: ' + str(quality))
        # Append this iteration to the optimization history
        position_history.append(np.array(position))
        quality_history.append(quality)
        # Update the optimization algorithm
        pso.notify_evaluation(quality)
        position = pso.get_position_to_evaluate()
        simulation_params = convert_particle_position_to_params(position)
        print(f'Params for iteration: {simulation_params.distance_chase} Distance from leader: {simulation_params.formation_distance}, distance_rings_formation: {simulation_params.distance_rings_formation}')
        # ==================

        # generates new iteration
        accelerated_factor = simulation.accelerated_factor
        simulation = Simulation(screenSimulation)
        if running_PSO:
            simulation.create_swarm_uav(NUM_DRONES,
                                        NUM_KAMIKAZES,
                                        simulation_params.distance_chase,
                                        #300.7,
                                        #kp=29.85,
                                        #kv=37.31,
                                        #distance_formation = DISTANCE_LEADER)
                                        #distance_formation = 69.02)
                                        distance_formation = simulation_params.formation_distance)
                                        #distance_rings_formation = simulation_params.distance_rings_formation)
        else:
            print('Running PSO OFF')
            simulation.create_swarm_uav(NUM_DRONES, 
                                        NUM_KAMIKAZES, 
                                        #distance_chase = 352, parameter using optimization
                                        distance_chase = 306.6,
                                        distance_formation = 100.1)
                                        #distance_formation = 62,
                                       #distance_rings_formation = 2.37)
        # 306.57304199 100.1527203  # com 1 ring e distancias de engajamento e do lider
        # 352.4 62 2.37  # com 2 ring e distancias de engajamento e do lider

        simulation.accelerated_factor = accelerated_factor
        input_processor = ProcessorUserInput(simulation,history)

        # reset timer
        time_running = 0
        #pygame.time.wait(1000)


        

    pygame.display.flip() 

