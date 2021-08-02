# Loyal Wingman Simulation

This project is an implementation of the loyal wingman concept.

There is a leading drone, controlled by the user, and anutonomous loyal wingman drones protecting the leading drone from kamikaze attacks.

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
 
	Main.py 	 		- Main file
	simulation.py			- Simulation controller and evaluation.
	utils.py 	 		- useful functions
	constants.py 	 		- Fixed parameters used in the simulation
	state_machine.py 		- Kamikaze's decision making code (state machine used to control the kamikaze behaviors)
	vehicle.py	 		- MAV logic and basic behaviors
	obstacle.py  	 		- Used to generate obstacles in the scenario (this code is working but was not used.)
	particle_swarm_optimization.py  - PSO implementation, used for params optimization
	weapons.py	 		- Weapons (freezing gun and vaporizer gun) logic
	decision_making.py 		- Loyal wingman decision-making logic.
	behavior_tree.py		- framework for a behavior tree.
	animation.py			- Animation (2D graphics) logic
	/experimentos			- Folder with the result graphs of optimizations.
	/Model 				- The sprites developed for the animations present.
