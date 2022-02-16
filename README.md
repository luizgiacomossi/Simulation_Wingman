#- Loyal Wingman 2D Simulation - 

This project is the first implementation of the loyal wingman concept using simulated UAVs. 

The focus of this implementation is on the high level decision making algorithms.

The scenario is composed of a MUM-T, where there is a leading drone, controlled by the user, and loyal wingman drones protecting the leading drone and a protected area from kamikaze attacks.

For the execution of the script it is necessary:

- PYTHON 3.8 or Newer version
- Visual Studio Code (VSCode) or any other code editor

Python Dependencies: 

- PYGAME -> https://www.pygame.org/wiki/GettingStarted
	- pip install pygame
- NUMPY -> https://numpy.org/
	- pip install numpy
- MATPLOTLIB -> https://matplotlib.org/stable/users/getting_started/index.html
 	- pip install matplotlib	


## To run the simulator: you only need to run the following script: -> main.py

In main, change the following line to:

	running_PSO = False # run simulation with offline parameters

	or
	
	running_PSO = True #  run simulation with PSO optimization
	
	# change the optimization params in the following function
	
	simulation.create_swarm_uav(NUM_DRONES, 
                                NUM_KAMIKAZES, 
                                distance_chase = 306.6,
                                distance_formation = 100.1)

UI Controls: 
	* Mouse right click on desired position for the leading drone control
	* Up and Down arrows to control the simulation acceleration 

Files Description:
 
	Main.py 	 		- Main file - EXECUTE THIS FILE TO RUN SIMULATION
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
	
