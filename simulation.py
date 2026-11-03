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
from swarm_manager import SwarmManager
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
    """
    Simulation environment controller that coordinates display, background,
    and delegates multi-UAV lifecycle to SwarmManager.
    """
    def __init__(self, screenSimulation):
        self.screenSimulation = screenSimulation
        self.canvas = getattr(self.screenSimulation, 'world_surface', getattr(self.screenSimulation, 'screen', None))
        self.accelerated_factor = 1
        self.swarm_manager = SwarmManager(window=self.canvas)

    @property
    def swarm(self):
        return self.swarm_manager.swarm

    @property
    def kamikazes(self):
        return self.swarm_manager.kamikazes

    @property
    def leadingdrone(self):
        return self.swarm_manager.leadingdrone

    @property
    def protected_area(self):
        return self.swarm_manager.protected_area

    @property
    def counter_kamikazes_destroyed(self):
        return self.swarm_manager.counter_kamikazes_destroyed

    @property
    def num_kamikazes(self):
        return self.swarm_manager.num_kamikazes

    @property
    def num_loyalwingman(self):
        return self.swarm_manager.num_loyalwingman

    def create_swarm_uav(self, num_swarm, num_kamikazes, 
                        distance_chase = 400, 
                        kp= 0.625, 
                        kv= 4.5, 
                        distance_formation = DISTANCE_LEADER, 
                        distance_rings_formation = 1.2):
        self.swarm_manager.create_swarm(
            num_loyal=num_swarm,
            num_kamikazes=num_kamikazes,
            distance_chase=distance_chase,
            kp=kp,
            kv=kv,
            distance_formation=distance_formation,
            distance_rings_formation=distance_rings_formation
        )

    def add_new_kamikaze(self, pos=None):
        self.swarm_manager.add_kamikaze(pos)

    def set_target_leader(self, target):
        self.swarm_manager.set_target_leader(target)

    def get_number_running_simultations(self):
        return len(self.swarm_manager.swarm)

    def get_kamikazes_destroyed(self):
        return self.swarm_manager.counter_kamikazes_destroyed

    def run_simulation(self, pos_leader, list_obst, accelerated_factor = 1):
        for _ in range(accelerated_factor):
            self.swarm_manager.update(list_obst)

        if self.canvas is not None:
            self.swarm_manager.draw(self.canvas, self.screenSimulation)

    def update_background(self):
        if self.canvas is None:
            return
        if hasattr(self.screenSimulation, 'background_image') and self.screenSimulation.background_image is not None:
            self.canvas.blit(self.screenSimulation.background_image, [0, 0])
        else:
            self.canvas.fill((40, 44, 52))
        pygame.draw.line(self.canvas, (100, 200, 100), vec2(WORLD_WIDTH / 3, 0), vec2(WORLD_WIDTH / 3, WORLD_HEIGHT), 10)

    def reset(self):
        pass