# Simulation Parameters
SCREEN_WIDTH = 1900
SCREEN_HEIGHT = 900
PIX2M = 0.01  # factor to convert from pixels to meters
M2PIX = 100.0  # factor to convert from meters to pixels
NUM_DRONES = 7# Number of simultaneous drones
SIZE_DRONE = 18
SIZE_TRACK = 100
RESOLUTION = 100 # Of grid
NUM_OBSTACLES = 0
RADIUS_OBSTACLES = 40
DISTANCE_LEADER = 100
NUM_KAMIKAZES = 5
# Sample Time Parameters
FREQUENCY = 60.0  # simulation frequency
SAMPLE_TIME = 1.0 / FREQUENCY  # simulation sample time
FREEZING_FACTOR = 1/3
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

# explosion parameteres
TIME_EXPLOSION = 0.3