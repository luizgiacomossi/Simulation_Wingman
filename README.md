# Loyal Wingman Simulation

This project is an implementation of the loyal wingman concept using simulated UAVs
Where there is a leading drone, controlled by the user, and loyal wingman drones protecting the leading drone from kamikaze attacks.

For the execution of the script it is necessary:

- PYTHON
- VSCode or any other code editor

Dependencies: 

- PYGAME -> https://www.pygame.org/wiki/GettingStarted
	- pip install pygame
- NUMPY -> https://numpy.org/
	- pip install numpy


Execute: main.py

Files Description:
 
	Main.py 	 - Main file - EXECUTE THIS FILE TO RUN SIMULATION
	utils.py 	 - useful functions
	constants.py 	 - parameters used in the simulation
	state_machine.py - state machine used to control behaviors
	vehicle.py	 - UAV logic and basic behaviors
	weapons.py	 - Weapons logic
	obstacle.py  	 - Not Used
	behavior_tree.py - Behavior Tree framework
	decision_making.py - Behavior Tree for the loyal wingman agents
	particle_swarm_optimization.py - PSO implementation used to optimize simulation parameters
	

The folder Model is for the sprites used in the animation
