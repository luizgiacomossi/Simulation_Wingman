import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

def get_auto_screen_resolution(margin_w=70, margin_h=100):
    """Detects current laptop/desktop screen resolution and returns optimal window size."""
    try:
        import pygame
        if not pygame.get_init():
            pygame.init()
        if not pygame.display.get_init():
            pygame.display.init()
        info = pygame.display.Info()
        if info.current_w > 0 and info.current_h > 0:
            w = max(800, int(info.current_w - margin_w))
            h = max(550, int(info.current_h - margin_h))
            return w, h
    except Exception:
        pass
    return 1600, 900

SCREEN_WIDTH, SCREEN_HEIGHT = get_auto_screen_resolution()
# World Physics Parameters (Tactical airspace: 1.6x laptop resolution, 20% more compact)
WORLD_SCALE = 1.6
WORLD_WIDTH = int(SCREEN_WIDTH * WORLD_SCALE)
WORLD_HEIGHT = int(SCREEN_HEIGHT * WORLD_SCALE)
PIX2M = 0.01  # factor to convert from pixels to meters
M2PIX = 100.0  # factor to convert from meters to pixels
NUM_DRONES = 10# Number of simultaneous drones
SIZE_DRONE = 18
SIZE_TRACK = 100
RESOLUTION = 100 # Of grid
NUM_OBSTACLES = 0
RADIUS_OBSTACLES = 40
DISTANCE_LEADER = 100
NUM_KAMIKAZES = 4
FREEZING_FACTOR = 1/3

# Sample Time Parameters
FREQUENCY = 60.0  # simulation frequency
SAMPLE_TIME = 1.0 / FREQUENCY  # simulation sample time

# Behavior Parameters
FORWARD_SPEED = 2  # default linear speed when going forward
ANGULAR_SPEED = 1.5# default angular speed
SEEK_FORCE = 0.5 # max seek force
RADIUS_TARGET = 130 
MASS = 10 # Drone Mass, used to calculate force
HOP_AHEAD = 60 # distance of prevision
AVOID_DISTANCE = 30 # distance to avoid collision

# Colors
BLACK = (0,0,0)
LIGHT_BLUE = (224, 255, 255)
BLUE = (0,0,255)
RED = (255,0,0)

# Weapons parameters
COOLDOWN_VAPORIZER = 1
CARTRIDGES_VAPORIZER = 10
COOLDOWN_FREEZING = 1
CARTRIDGES_FREEZING= 10
TIME_FROZEN = 5
PROB_VAPORIZER = 0.95
PROB_FREEZING = 0.85

# explosion parameteres
TIME_EXPLOSION = 0.3

# Logistics & Replenishment (RTB)
ENABLE_WINGMAN_RTB = False  # Opt-in toggle: wingmen return to base when out of ammo
RTB_REARM_DURATION = 3.0    # Seconds required inside base perimeter to reload weapons

# Experiment & Telemetry Saving
SAVE_RESULTS = True
