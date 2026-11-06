import pygame as pg
from utils import random_color, limit, constrain, bivariateFunction, derivativeBivariate, normalFunction
from constants import *
from animation import Aircraft, Kamikaze_drone, ProtectedArea
from math import cos, sin, atan2, pi, inf
import random
import copy 
from weapons import *
import numpy as np
from quadtree import Quadtree, Rect
from message_manager import MessageManager, TacticalMessage, MessageTopic
from formation import FormationManager

vec2 = pg.math.Vector2

class Vehicle(object):

    def __init__(self, x,y, behavior, window):
        """
            idealized vehicle representing a drone

            :param x and y: represents inicial target 
            :param behavior: State Machine 
            :param window: pygame screen were it will be draw
        """

        self.debug = True #  debug lines is Off

        # Variables used to move drone 
        self.location = vec2(x,y) # Random position in screen
        self.velocity = vec2(0.1,0) # Inicial speed
        self.target = vec2(x,y)
        self.acceleration = vec2(0,0)
        self.radius = SIZE_DRONE # Drone Size
        self.desired = vec2()
        self.team = []
        self.index = None

        self.memory_location = [] # To draw track
        self.rotation = atan2(self.location.y,self.location.x) # inicital rotation

        # Arbitrary values
        self.max_speed = FORWARD_SPEED
        self.max_force = SEEK_FORCE
        self.angular_speed = ANGULAR_SPEED

        # Picks a random color for target, is used to differentiate visually during simulation
        self.color_target = random_color() 

        # Datalink and messaging
        self.agent_id = None
        self.message_bus = None

        # Variables related to State Machine
        self.behavior = behavior

        self.window = window # tela em que esta acontecendo a simulaçao
        self.theta = 0 # variavel para o eight somada no seek_around
        self.count = 0

        # Variables to draw drone using Sprites
        if self.window is not None:
            self.drone = Aircraft() 
            self.all_sprites = pg.sprite.Group()
            self.all_sprites.add(self.drone)
        else:
            self.drone = None
            self.all_sprites = None
    
    def update(self):
        """
            Standart Euler integration
            Updates bahavior tree
        """
        # updates behavior in machine state
        self.behavior.update(self)
        # Updates velocity at every step and limits it to max_speed
        self.velocity += self.acceleration * 1 
        self.velocity = limit(self.velocity, self.max_speed) 
        # updates position
        self.location += self.velocity 
        # Prevents it from crazy spinning due to very low noise speeds
        if self.velocity.length() > 0.35:
            k = 2/3
            self.rotation = (atan2(self.velocity.y, self.velocity.x) - self.rotation) * k + self.rotation
        # Constrains position to limits of world 
        self.location = constrain(self.location,WORLD_WIDTH,WORLD_HEIGHT)
        self.acceleration *= 0

        # Memory of positions to draw Track
        self.memory_location.append((self.location.x,self.location.y))
        # size of track 
        if len(self.memory_location) > SIZE_TRACK:
            self.memory_location.pop(0)

    def applyForce(self, force):
        """
            Applies vetor force to vehicle 
            Newton's second law -> F=m.a
            You can divide by mass
        """
        self.acceleration += force/MASS 

    def seek(self, target):
        """
            Seek Steering force Algorithm
        """
        try:
            self.desired  = (target - self.location).normalize()*self.max_speed
        except: # if you try to normalize a null vector it will catch
            self.desired  = (target - self.location)*self.max_speed
        
        # Calculates steering force
        steer = self.desired  - self.velocity
        # Limit the magnitude of the steering force.
        steer = limit(steer,self.max_force)
        # Applies steering force to drone
        self.applyForce(steer)
        # Draws current target being seeked 
        if self.window is not None:
            pg.draw.circle(self.window, self.color_target ,target ,5, 0)
    
    def arrive_new_dynamic(self, target_leader):
        """
            Arrive using potential fields 
        """

        # Calculates vector desired 
        velocity_attract = vec2(0,0)
        # drone need to keep distance from leader, so the distance to arrive is DISTANCE_LEADER
        try:
            target = target_leader + (self.location - target_leader).normalize()*DISTANCE_LEADER
        except:
            target = target_leader
        f_attract = derivativeBivariate(.05,.05,target,self.location)/ SAMPLE_TIME 

        #error = (velocity_attract - self.velocity) / SAMPLE_TIME 
        
        accelerate = limit(f_attract, self.max_force)
        self.applyForce(accelerate)
        # Draws current target as a point 
        if self.window is not None:
            pg.draw.circle(self.window, self.color_target ,target ,5, 0)

    def arrive(self, target):
        """
            Arrive Steering Behavior
        """
        # Calculates vector desired 
        self.desired = (target - self.location)
        # get the distance to the target
        d = self.desired.magnitude() 

        # Deadband and smooth damping near target to prevent hunting/spinning
        if d < 12.0:
            self.velocity *= 0.85
            self.acceleration *= 0.0
            return

        try:
            dist = self.desired.normalize() # get direction
        except: # If magnitude of desired is zero it cant be normalized
            dist = vec2(self.desired)
        
        r = RADIUS_TARGET
        # Modulates the force
        if d < r : # close to target it will reduce velocty till stops
            # interpolation
            dist *= self.max_speed*(1 + 1/r*(d-r))
        else:
            dist *= self.max_speed

        # Steering force
        steer = dist - self.velocity
        #Limit the magnitude of the steering force.
        steer = limit(steer, self.max_force)
        # apply force to the vehicle
        self.applyForce(steer)
        # Simulates Wind - random Noise
        #wind = vec2(random.uniform(-0.15,0.15) , random.uniform(-0.15,0.15)  )
        #self.applyForce(wind)

        # Draws current target as a point 
        if self.window is not None:
            pg.draw.circle(self.window, self.color_target ,target ,5, 0)

    def stay_at(self, center, r = RADIUS_TARGET):
        """
           Drone Behavior - it will orbit a given target (center)
        """
        posToCenter = center - self.location 
        #ok
        if self.debug == True:
            pg.draw.line(self.window,BLACK, self.location , center,1)

        # se o veiculo se encontra mais longue q o raio de rotaçao
        if posToCenter.length() > r :
            self.seek(center)
            #self.target =copy.deepcopy(center) 
        else: # se ele esta dentro do raio de rotaçao
            # reinicia forças
            centerToPerimeter = posToCenter.normalize()*(-1*r )
            #ok
            pg.draw.line(self.window,(0,0,255),center,center+centerToPerimeter,5 )
            
            posToPerimeter = centerToPerimeter + posToCenter 
            #pg.draw.line(window,(255,0,0),center,center+posToPerimeter,5 )

            #print(f'distancia até perimetro {posToPerimeter.length()}')

            # new target is on the radius
                # theta is the angle of the vector center to perimeter
            theta = atan2(centerToPerimeter.y, centerToPerimeter.x)
            theta += self.angular_speed
            new_target = vec2(0,0)

            # new target
            new_target.x += r  * cos(theta)
            new_target.y += r  * sin(theta)
            new_target += center

            if self.debug == True:
                pg.draw.line(self.window,(0,255,0), center,  new_target ,5)# verde é o target
                pg.draw.line(self.window,BLACK, self.location, new_target, 2 )
            
            self.seek(new_target)

    def seek_around(self, center, radius_target = RADIUS_TARGET):
        """
           Drone Behavior - it will orbit a given target (center) with prevision 

           :param center: position of target to  orbite
           :param radius_target: distance till center, default = RADIUS_TARGET from constants
        """
        # Calculating the max speed
        self.angular_speed = FORWARD_SPEED / radius_target

        # future positiom
        hop_ahead = HOP_AHEAD #o quanto se ve a frente
        fut_pos = self.velocity.normalize()*(hop_ahead)
        fut_pos += self.location

        if self.debug == True:
            pg.draw.line(self.window,(0,255,50),self.location,fut_pos,5)
        #print(f'center: {center}')
        posToCenter = center - fut_pos
        # line from drone to center
        if self.debug == True:
            pg.draw.line(self.window,BLACK, self.location ,center,1)

        # se o veiculo se encontra mais longue q o raio de rotaçao
        if posToCenter.length() > radius_target:
            self.seek(center)
            #self.target =copy.deepcopy(center) 
        else: # se ele esta dentro do raio de rotaçao
            # reinicia forças
            centerToPerimeter = posToCenter.normalize()*(-1*radius_target)
            #ok
            if self.debug == True:
                pg.draw.line(self.window,(0,0,255),center,center+centerToPerimeter,5 )
            
            posToPerimeter = centerToPerimeter + posToCenter 
            #pg.draw.line(window,(255,0,0),center,center+posToPerimeter,5 )

            #print(f'distancia até perimetro {posToPerimeter.length()}')

            # new target is on the radius
                # theta is the angle of the vector center to perimeter
            self.theta = atan2(centerToPerimeter.y, centerToPerimeter.x)
            self.theta += self.angular_speed
            new_target = vec2(0,0)

            # new target
            new_target.x += radius_target * cos(self.theta)
            new_target.y += radius_target * sin(self.theta)
            new_target += center
            if self.debug == True:
                pg.draw.line(self.window,(0,255,0), center,  new_target ,5)# verde é o target
                pg.draw.line(self.window,BLACK, self.location, new_target, 2 )
            self.seek(new_target)

    def get_position(self):
        return self.location

    def set_target(self, target):
        self.target = target
    
    def get_target(self):
        try:
            return self.target
        except: 
            return None

    def set_message_bus(self, bus, agent_id=None):
        """Connects this vehicle to the tactical datalink message bus."""
        self.message_bus = bus
        if agent_id is not None:
            self.agent_id = agent_id
        if self.message_bus is not None and self.agent_id is not None:
            self.message_bus.register_agent(self.agent_id)

    def send_message(self, recipient_id, topic, payload, current_time=0.0) -> bool:
        """Transmits a targeted datalink message via the bus."""
        if self.message_bus is None or self.agent_id is None:
            return False
        return self.message_bus.send_message(self.agent_id, recipient_id, topic, payload, current_time)

    def broadcast_message(self, topic, payload, current_time=0.0) -> bool:
        """Transmits a broadcast datalink message to all network nodes."""
        if self.message_bus is None or self.agent_id is None:
            return False
        return self.message_bus.broadcast(self.agent_id, topic, payload, current_time)

    def poll_messages(self) -> list:
        """Retrieves and clears all pending messages from this vehicle's datalink inbox."""
        if self.message_bus is None or self.agent_id is None:
            return []
        return self.message_bus.receive_messages(self.agent_id)

    def set_debug(self):
        """
        Method to view debug lines . Assists the developer.
        """
        self.debug = not self.debug

    def get_debug(self):
        return str(self.debug)

    def align_swarm(self, all_positions, index):
        """
         This method avoids collisions with other drones
         During simulation it receives either a Quadtree or a list of drones.
         index: is the current id of drone being checked 
        """
        # gets all positions of simultaneous drones
        self.index = index
        self.team = all_positions
        separation_factor = 2.2
        search_radius = AVOID_DISTANCE * separation_factor

        if isinstance(all_positions, Quadtree):
            range_rect = Rect(self.location.x, self.location.y, search_radius, search_radius)
            nearby_drones = []
            all_positions.query(range_rect, nearby_drones)
        else:
            nearby_drones = all_positions

        soma = vec2(0,0) # sums up all directions of close drones
        count = 0 # counts the number of drones that are close
        for p in nearby_drones:
            # compares current position to nearby drones
            # p != self -> avoids auto-collision check
            if p is self:
                continue
            d = (self.location - p.location).magnitude()
            if ( (d > 0) and (d < search_radius) ):
                diff = (self.location - p.location).normalize()
                diff = diff/d # proportional to distance
                soma += diff
                count += 1 # p drone is close 
            
        if count > 0:
            media = soma / count
            media = media.normalize()
            media *= self.max_speed
            steer = (media - self.velocity)
            steer = limit(steer,self.max_force)
            self.applyForce(steer)
                  
    def draw(self, window=None):
        """
            Defines shape of vehicle and draw it to screen
        """
        target_win = window if window is not None else self.window
        if target_win is None:
            return

        # draws track
        if len(self.memory_location) >= 2:
            pg.draw.lines(target_win, self.color_target, False, self.memory_location, 1)
        # Drawing drone's outer circle as a hitbox?
        if self.debug == True:
            pg.draw.circle(target_win, (100, 100, 100), self.location, AVOID_DISTANCE, 1)
            v = self.velocity.length()
            if v > 0:
                pg.draw.line(target_win, (255, 0, 0), self.location, self.location + self.velocity.normalize()*v*20 , 1)

        # usar sprite para desenhar drone
        if self.all_sprites is not None:
            self.all_sprites.draw(target_win)
            self.all_sprites.update(self.location,self.rotation)

    def collision_avoidance(self, positions_drones , pos_obstacles , index):
        """
            Detects obstacles and collision with other drones using Quadtree or list
        """
        factor_distance = 2
        dist_avoid = AVOID_DISTANCE * factor_distance

        if isinstance(positions_drones, Quadtree):
            range_rect = Rect(self.location.x, self.location.y, dist_avoid, dist_avoid)
            nearby_drones = []
            positions_drones.query(range_rect, nearby_drones)
        else:
            nearby_drones = positions_drones

        for p in nearby_drones:
            if p is self:
                continue
            d = (self.location - p.location).length()
            if 0 < d < dist_avoid:
                f_repulsion = derivativeBivariate(0.001, .001, p.location, self.location) / SAMPLE_TIME
                f_repulsion = limit(f_repulsion, self.max_force * 1.8)
                self.applyForce(-f_repulsion)
                break

        # --- Repulsion From obstacles
        for p in pos_obstacles:
            d = (self.location - p).length()
            factor_repulsion = 0.005
            dist_avoid_obst = RADIUS_OBSTACLES * 1.6 + AVOID_DISTANCE
            if ( d < dist_avoid_obst ) :
                f_repulsion = derivativeBivariate(factor_repulsion, factor_repulsion, p, self.location) / SAMPLE_TIME
                f_repulsion = limit(f_repulsion, self.max_force * 1.8)
                if (d < AVOID_DISTANCE):
                    self.applyForce(- self.velocity.normalize() * self.max_speed)
                self.applyForce(-f_repulsion)

class VehiclePF(object):

    def __init__(self, x,y, behavior, window):
        """
            This is a class that can be used to test new methods

            :param x and y: represents inicial target 
            :param behavior: State Machine 
            :param window: pygame screen were it will be draw
        """

        self.debug = False #  debug lines is Off

        # Variables used to move drone 
        self.location = vec2(x,y) # Random position in screen
        self.velocity = vec2(0.1,0) # Inicial speed
        self.target = vec2(x,y)
        self.acceleration = vec2(0,0)
        self.radius = SIZE_DRONE # Drone Size
        self.desired = vec2()

        self.memory_location = [] # To draw track
        self.rotation = atan2(self.location.y,self.location.x) # inicital rotation

        # Arbitrary values
        self.max_speed = FORWARD_SPEED
        self.max_force = SEEK_FORCE
        self.angular_speed = ANGULAR_SPEED

        # Picks a random color for target, is used to differentiate visually during simulation
        self.color_target = random_color() 

        # Datalink and messaging
        self.agent_id = None
        self.message_bus = None

        # Variables related to State Machine
        self.behavior = behavior
        self.window = window # tela em que esta acontecendo a simulaçao
        self.theta = 0 # variavel para o eight somada no seek_around
        self.count = 0

        # Variables to draw drone using Sprites
        if self.window is not None:
            self.drone = Aircraft() 
            self.all_sprites = pg.sprite.Group()
            self.all_sprites.add(self.drone)
        else:
            self.drone = None
            self.all_sprites = None
    
    def update(self):
        """
            Standart Euler integration
            Updates bahavior tree
        """
        # updates behavior in machine state
        self.behavior.update(self)
        # Updates velocity at every step and limits it to max_speed
        self.velocity += self.acceleration * 1 
        self.velocity = limit(self.velocity, self.max_speed) 
        # updates position
        self.location += self.velocity 
        # Prevents it from crazy spinning due to very low noise speeds
        if self.velocity.length() > 0.8:
            self.rotation = atan2(self.velocity.y,self.velocity.x)
        # Constrains position to limits of world 
        self.location = constrain(self.location,WORLD_WIDTH,WORLD_HEIGHT)
        self.acceleration *= 0

        # Memory of positions to draw Track
        self.memory_location.append((self.location.x,self.location.y))
        # size of track 
        if len(self.memory_location) > SIZE_TRACK:
            self.memory_location.pop(0)

    def applyForce(self, force):
        """
            Applies vetor force to vehicle 
            Newton's second law -> F=m.a
            You can divide by mass
        """
        self.acceleration += force/MASS 

    def seek(self, target):
        """
            Seek Steering force Algorithm
        """
        try:
            self.desired  = (target - self.location).normalize()*self.max_speed
        except: # if you try to normalize a null vector it will catch
            self.desired  = (target - self.location)*self.max_speed
        
        # Calculates steering force
        steer = self.desired  - self.velocity
        # Limit the magnitude of the steering force.
        steer = limit(steer,self.max_force)
        # Applies steering force to drone
        self.applyForce(steer)
        # Draws current target being seeked 
        if self.window is not None:
            pg.draw.circle(self.window, self.color_target ,target ,5, 0)
    
    def arrive(self, target):
        """
            Arrive using potential fields 
        """
        # Calculates vector desired 
        velocity_attract = vec2(0,0)
        velocity_repulsion= vec2(0,0)

        velocity_attract = derivativeBivariate(.1,.1,target,self.location)
        #acc_atract = ( desired_velocity - self.velocity )/SAMPLE_TIME

        distance = (target - self.location).length()
        #calculates repulsion
        if distance < RADIUS_TARGET:
            omega = 0.3
            f = normalFunction(omega,target,self.location)
            velocity_repulsion = f * (-2*omega*(self.location-target))
            #acc_repulsion = (d - self.velocity) / SAMPLE_TIME

        desired_velocity = (velocity_attract - velocity_repulsion) 
        error = (desired_velocity - self.velocity) / SAMPLE_TIME 
        
        accelerate = limit(error, self.max_force)
        self.applyForce(accelerate)
        # Draws current target as a point 
        if self.window is not None:
            pg.draw.circle(self.window, self.color_target ,target ,5, 0)
       
    def arrive_old(self, target):
        """
            Arrive Steering Behavior
        """
        # Calculates vector desired 
        self.desired = (target - self.location)
        # get the distance to the target
        d = self.desired.magnitude() 

        try:
            dist = self.desired.normalize() # get direction
        except: # If magnitude of desired is zero it cant be normalized
            dist = vec2(self.desired)
        
        r = RADIUS_TARGET
        # Modulates the force
        if d < r : # close to target it will reduce velocty till stops
            # interpolation
            dist *= self.max_speed*(1 + 1/r*(d-r))
        else:
            dist *= self.max_speed

        # Steering force
        steer = dist - self.velocity
        #Limit the magnitude of the steering force.
        steer = limit(steer, self.max_force)
        # apply force to the vehicle
        self.applyForce(steer)
        # Simulates Wind - random Noise
        wind = vec2(random.uniform(-0.15,0.15) , random.uniform(-0.15,0.15)  )
        self.applyForce(wind)
        # Draws current target as a point 
        if self.window is not None:
            pg.draw.circle(self.window, self.color_target ,target ,5, 0)
    
    def stay_at(self, center, r = RADIUS_TARGET):
        """
           Drone Behavior - it will orbit a given target (center)
        """
        posToCenter = center - self.location 
        #ok
        if self.debug == True:
            pg.draw.line(self.window,BLACK, self.location ,center,1)

        # se o veiculo se encontra mais longue q o raio de rotaçao
        if posToCenter.length() > r :
            self.seek(center)
            #self.target =copy.deepcopy(center) 
        else: # se ele esta dentro do raio de rotaçao
            # reinicia forças
            centerToPerimeter = posToCenter.normalize()*(-1*r )
            #ok
            pg.draw.line(self.window,(0,0,255),center,center+centerToPerimeter,5 )
            
            posToPerimeter = centerToPerimeter + posToCenter 
            #pg.draw.line(window,(255,0,0),center,center+posToPerimeter,5 )

            #print(f'distancia até perimetro {posToPerimeter.length()}')

            # new target is on the radius
                # theta is the angle of the vector center to perimeter
            theta = atan2(centerToPerimeter.y, centerToPerimeter.x)
            theta += self.angular_speed
            new_target = vec2(0,0)

            # new target
            new_target.x += r  * cos(theta)
            new_target.y += r  * sin(theta)
            new_target += center

            if self.debug == True:
                pg.draw.line(self.window,(0,255,0), center,  new_target ,5)# verde é o target
                pg.draw.line(self.window,BLACK, self.location, new_target, 2 )
            
            self.seek(new_target)

    def seek_around(self, center, radius_target = RADIUS_TARGET):
        """
           Drone Behavior - it will orbit a given target (center) with prevision 

           :param center: position of target to  orbite
           :param radius_target: distance till center, default = RADIUS_TARGET from constants
        """
        # Calculating the max speed
        self.angular_speed = FORWARD_SPEED / radius_target

        # future positiom
        hop_ahead = HOP_AHEAD #o quanto se ve a frente
        fut_pos = self.velocity.normalize()*(hop_ahead)
        fut_pos += self.location

        if self.debug == True:
            pg.draw.line(self.window,(0,255,50),self.location,fut_pos,5)
        #print(f'center: {center}')
        posToCenter = center - fut_pos
        # line from drone to center
        if self.debug == True:
            pg.draw.line(self.window,BLACK, self.location ,center,1)

        # se o veiculo se encontra mais longue q o raio de rotaçao
        if posToCenter.length() > radius_target:
            self.seek(center)
            #self.target =copy.deepcopy(center) 
        else: # se ele esta dentro do raio de rotaçao
            # reinicia forças
            centerToPerimeter = posToCenter.normalize()*(-1*radius_target)
            #ok
            if self.debug == True:
                pg.draw.line(self.window,(0,0,255),center,center+centerToPerimeter,5 )
            
            posToPerimeter = centerToPerimeter + posToCenter 
            #pg.draw.line(window,(255,0,0),center,center+posToPerimeter,5 )

            #print(f'distancia até perimetro {posToPerimeter.length()}')

            # new target is on the radius
                # theta is the angle of the vector center to perimeter
            self.theta = atan2(centerToPerimeter.y, centerToPerimeter.x)
            self.theta += self.angular_speed
            new_target = vec2(0,0)

            # new target
            new_target.x += radius_target * cos(self.theta)
            new_target.y += radius_target * sin(self.theta)
            new_target += center
            if self.debug == True:
                pg.draw.line(self.window,(0,255,0), center,  new_target ,5)# verde é o target
                pg.draw.line(self.window,BLACK, self.location, new_target, 2 )
            self.seek(new_target)

    def get_position(self):
        return self.location

    def set_target(self, target):
        self.target = target
    
    def get_target(self):
        try:
            return self.target
        except: 
            return None

    def set_message_bus(self, bus, agent_id=None):
        """Connects this vehicle to the tactical datalink message bus."""
        self.message_bus = bus
        if agent_id is not None:
            self.agent_id = agent_id
        if self.message_bus is not None and self.agent_id is not None:
            self.message_bus.register_agent(self.agent_id)

    def send_message(self, recipient_id, topic, payload, current_time=0.0) -> bool:
        """Transmits a targeted datalink message via the bus."""
        if self.message_bus is None or self.agent_id is None:
            return False
        return self.message_bus.send_message(self.agent_id, recipient_id, topic, payload, current_time)

    def broadcast_message(self, topic, payload, current_time=0.0) -> bool:
        """Transmits a broadcast datalink message to all network nodes."""
        if self.message_bus is None or self.agent_id is None:
            return False
        return self.message_bus.broadcast(self.agent_id, topic, payload, current_time)

    def poll_messages(self) -> list:
        """Retrieves and clears all pending messages from this vehicle's datalink inbox."""
        if self.message_bus is None or self.agent_id is None:
            return []
        return self.message_bus.receive_messages(self.agent_id)

    def set_debug(self):
        """
        Method to view debug lines . Assists the developer.
        """
        self.debug = not self.debug

    def get_debug(self):
        return str(self.debug)

    def collision_avoidance(self, all_positions, index):
        """
         This method avoids collisions with other drones
         During simulation it receives all the positions from all drones 
         index: is the current id of drone being checked 
        """
        # gets all positions of simultaneos drones
        aux = 0 
        soma = vec2(0,0) # sums up all directions of close drones
        count = 0 # counts the number of drones that are close
        for p in all_positions:
        # compares current position to all the drones
        # aux != index -> avoids the auto-collision check
            d = (self.location - p.location).magnitude()
            separation_factor = 2
            if ( (d > 0) and (d < AVOID_DISTANCE*separation_factor) and (aux != index) ) :
                diff = (self.location - p.location).normalize()
                diff = diff/d # proporcional to the distance. The closer the stronger needs to be
                soma += diff
                count += 1 # p drone is close 
            aux+=1
            
        if count > 0:
            media = soma / count
            media = media.normalize()
            media *= self.max_speed
            steer = (media - self.velocity)
            steer = limit(steer,self.max_force)
            #----
            #----
            self.applyForce(steer)

    def check_collision(self, positions_drones , pos_obstacles , index):
        # check drones
        f = 1
        aux = 0 
        for p in positions_drones:
            d = (self.location - p.location).length()
            factor_distance = 1.8
            dist_avoid = AVOID_DISTANCE*factor_distance
            if ( d < dist_avoid )  and (aux != index):
                f = (self.velocity - self.velocity.normalize()*self.max_speed )/ SAMPLE_TIME
                f = limit(f,self.max_force)
                #self.velocity *= d/(AVOID_DISTANCE*factor_distance)
                self.applyForce(f)
                #print(f'Alerta de colisão drone {index} com drone {aux}')
                break
            aux +=1
        # check obstacles 

        for p in pos_obstacles:
            d = (self.location - p).length()
            factor_distance = 1.3
            dist_avoid = 100 * factor_distance
            if ( d < dist_avoid ) :
                diff = (self.location - p).normalize()
                #f = -self.velocity/ SAMPLE_TIME
                diff *= self.max_speed
                steer = (diff - self.velocity)
                steer = limit(steer,self.max_force)
            #----
            #----
                self.applyForce(steer)
                #self.velocity *= d/(AVOID_DISTANCE*factor_distance)
                #self.applyForce(f)

    def draw(self, window):

        """
            Defines shape of vehicle and draw it to screen
        """

        # draws track
  
        # Drawing drone's outer circle as a hitbox?
        if self.debug == True:
            pg.draw.circle(self.window, (100, 100, 100), self.location, AVOID_DISTANCE, 1)
            if len(self.memory_location) >= 2:
                pg.draw.lines(self.window, self.color_target, False, self.memory_location, 1)

            #pg.draw.line(self.window, (100, 100, 100), self.location, self.location+self.desired , 1)
            # Draw Direction
            pg.draw.line(self.window, (100, 100, 100), self.location, self.location + self.velocity.normalize()*50 , 1)

        # usar sprite para desenhar drone
        self.all_sprites.draw(self.window)
        self.all_sprites.update(self.location,self.rotation)

    # Deleting (Calling destructor)
    def __del__(self):
        print('Drone Deleted')

class LeadingDrone(Vehicle):
    def __init__(self, x, y, behavior, window, distance_leader = DISTANCE_LEADER, distance_rings_formation = 1.2):

        super().__init__(x, y, behavior, window)
        self.distance_formation = distance_leader
        self.distance_rings_formation = distance_rings_formation
        self.destroyed = False
        self.formation_manager = FormationManager(default_strategy="CIRCLE")
        self.current_formation_name = "CIRCLE"

    def destroy(self):
        self.destroyed = True

    def arrive_new(self, target):
        """
            Arrive using potential fields 
        """
        # Calculates vector desired 
        velocity_attract = vec2(0,0)
        velocity_repulsion= vec2(0,0)

        velocity_attract = derivativeBivariate(.05,.05,target,self.location)

        desired_velocity = (velocity_attract - velocity_repulsion) 
        error = (desired_velocity - self.velocity) / SAMPLE_TIME 
        
        accelerate = limit(error, self.max_force)
        self.applyForce(accelerate)
        # Draws current target as a point 
        if self.window is not None:
            pg.draw.circle(self.window, self.color_target ,target ,5, 0)

    def arrive(self, target):
        """
            Arrive Steering Behavior
        """
        # Calculates vector desired 
        self.desired = (target - self.location)
        # get the distance to the target
        d = self.desired.magnitude() 

        # Deadband and smooth damping near target to prevent hunting/spinning
        if d < 12.0:
            self.velocity *= 0.85
            self.acceleration *= 0.0
            return

        try:
            dist = self.desired.normalize() # get direction
        except: # If magnitude of desired is zero it cant be normalized
            dist = vec2(self.desired)
        
        r = RADIUS_TARGET
        # Modulates the force
        if d < r : # close to target it will reduce velocty till stops
            # interpolation
            dist *= self.max_speed*(1 + 1/r*(d-r))
        else:
            dist *= self.max_speed

        # Steering force
        steer = dist - self.velocity
        #Limit the magnitude of the steering force.
        steer = limit(steer, self.max_force)
        # apply force to the vehicle
        self.applyForce(steer)
        # Simulates Wind - random Noise
        #wind = vec2(random.uniform(-0.15,0.15) , random.uniform(-0.15,0.15)  )
        #self.applyForce(wind)
        # Draws current target as a point 
        if self.window is not None:
            pg.draw.circle(self.window, self.color_target ,target ,5, 0)

    def set_formation(self, num_drones = NUM_DRONES):
        '''
        Calculates slots using the active FormationStrategy (CIRCLE, WEDGE, WALL, ECHELON).
        '''
        slots = self.formation_manager.compute_formation_slots(
            leader_pos=self.location,
            leader_heading=self.rotation,
            num_drones=num_drones,
            spacing=self.distance_formation
        )
        return slots

    def set_formation_strategy(self, name: str) -> bool:
        """Switches active tactical formation strategy."""
        ok = self.formation_manager.set_strategy(name)
        if ok:
            self.current_formation_name = self.formation_manager.active_strategy_name
        return ok

    def draw_formation_guide(self, surface, num_drones=NUM_DRONES, color=(160, 225, 175), width=2):
        """
        Renders the active formation's dynamic geometry (Circle, Wedge, Wall, Echelon)
        and target slot reticles around the leader drone.
        """
        if hasattr(self, 'formation_manager') and surface is not None:
            slots = self.formation_manager.compute_formation_slots(
                leader_pos=self.location,
                leader_heading=self.rotation,
                num_drones=num_drones,
                spacing=self.distance_formation
            )
            self.formation_manager.draw_formation_guide(
                surface=surface,
                leader_pos=self.location,
                leader_heading=self.rotation,
                slots=slots,
                spacing=self.distance_formation,
                color=color,
                width=width
            )

    def set_formation_2rings(self, num_drones = NUM_DRONES):
        '''
            This method returns the positions for the loyal wingman surrounding the leading drone
            using 2 rings

            input: number of drones in formation
            return: list of positions
        '''
        even = None 
        if (num_drones % 2) == 0:  
            even = True
        else:  
            even = False

        distance_leader = self.distance_formation
        if num_drones > 1: # check if there is still loyalwingmen
            half_drones = int(num_drones/2) 
            step_angle = 2 * pi / int(half_drones) 
        else:
            step_angle = 0
            half_drones = 0

        pos = self.get_position()
        #print(f'position leader:{pos}')
        ang = 0
        list_positions = []
        
        # calculates position of drone in formation
        for _ in range(half_drones):
            x = pos[0] + distance_leader*cos(ang)
            y = pos[1] + distance_leader*sin(ang)

            ang += step_angle
            
            list_positions.append( vec2( x, y ) )

        ang = +90 # defasagem entre rings
        distance_rings = self.distance_rings_formation *distance_leader
        pg.draw.circle(self.window,(200, 250, 200), pos, radius= distance_rings*self.distance_formation , width = 3)

        if even == False:
            half_drones+=1
        for _ in range(half_drones):
            x = pos[0] + distance_rings*cos(ang)
            y = pos[1] + distance_rings*sin(ang)
 
            ang += step_angle
            
            list_positions.append( vec2( x, y ) )

        return list_positions

    def set_formation_2rings_new(self, num_drones = NUM_DRONES):
        '''
            This method returns the positions for the loyal wingman surrounding the leading drone
            using 2 rings

            input: number of drones in formation
            return: list of positions
        '''
        even = None 
        if (num_drones % 2) == 0:  
            even = True
        else:  
            even = False

        distance_leader = self.distance_formation
        if num_drones > 1: # check if there is still loyalwingmen
            half_drones = int(num_drones/2) 
            step_angle = 2 * pi / int(half_drones) # inner angle
            step_angle2 = 2 * pi / (int(half_drones) - num_drones) # outter angle
        else:
            step_angle = 0
            step_angle2 = 0 
            half_drones = 0

        pos = self.get_position()
        #print(f'position leader:{pos}')
        ang = 0
        list_positions = []
        ang2 = +pi/4# defasagem entre rings
        distance_rings = self.distance_rings_formation *distance_leader
        # calculates position of drone in formation
        for _ in range(half_drones):
            x = pos[0] + distance_leader*cos(ang)
            y = pos[1] + distance_leader*sin(ang)

            ang += step_angle
            
            list_positions.append( vec2( x, y ) )
            # outter rings

            x = pos[0] + distance_rings*cos(ang2)
            y = pos[1] + distance_rings*sin(ang2)
            ang2 += step_angle2
            list_positions.append( vec2( x, y ) )

        if even == False:
                # for the last dorne if number is odd    
            x = pos[0] + distance_rings*cos(ang2)
            y = pos[1] + distance_rings*sin(ang2)
            ang2 += step_angle2
            list_positions.append( vec2( x, y ) )
                
        pg.draw.circle(self.window,(200, 250, 200), pos, radius= distance_rings , width = 3)

        return list_positions

    def broadcast_formation_command(self, slots_dict, formation_type="CIRCLE", current_time=0.0):
        """
        Transmits tactical formation coordinates over the datalink message bus to all wingmen.
        """
        payload = {
            "formation_type": formation_type,
            "slots": slots_dict,
            "leader_pos": (self.location.x, self.location.y),
            "leader_velocity": (self.velocity.x, self.velocity.y)
        }
        return self.broadcast_message("FORMATION_COMMAND", payload, current_time)

    def destroyed_legacy(self):
        self.destroyed = True

class LoyalWingman(Vehicle):
    def __init__(self, x, y, behavior, window, protected_area, distance_chase = 400, kp= 0.625, kv= 4.5, enable_rtb: bool = ENABLE_WINGMAN_RTB):
        super().__init__(x, y, behavior, window)
        self.destroyed = False
        self.error = vec2(0,0)
        self.kamikazes = None
        self.projectiles_pool = None
        self.vaporizer_gun = Vaporizer(1, 10, 1, 100, self.kamikazes, owner=self)
        self.freezing_gun  = Freezing(1, 10, 1, 300, self.kamikazes, owner=self)
        self.closest_kamikaze = vec2(inf,inf)
        self.distance_closest_kamikaze = inf
        self.attack_status = ( vec2(0,0) , False ) # position attacked and sucessfull or not
        self.kamikaze_to_attack = None
        self.protected_area = protected_area
        self.leader = None
        self.kp = kp
        self.kv = kv
        # param for chase a threat 
        self.distance_chase = distance_chase
        self.enable_rtb = enable_rtb
        self.is_rtb = False
        self.rtb_status = ""
        self.is_sacrificing = False
        self.sacrificial_target = None

    def destroy(self):
        self.destroyed = True

    def process_tactical_messages(self, current_time: float = 0.0):
        """
        Polls and processes incoming datalink messages from leader or peers.
        """
        messages = self.poll_messages()
        for msg in messages:
            if msg.topic == "FORMATION_COMMAND":
                slots = msg.payload.get("slots", {})
                my_slot = slots.get(self.agent_id)
                if my_slot is not None:
                    target_vec = vec2(my_slot[0], my_slot[1]) if not isinstance(my_slot, vec2) else my_slot
                    self.set_target(target_vec)
                self.formation_type = msg.payload.get("formation_type", "CIRCLE")
            elif msg.topic == "TARGET_ASSIGNMENT":
                threat = msg.payload.get("threat")
                role = msg.payload.get("role")
                if threat is not None:
                    self.assigned_threat = threat
                    self.kamikaze_to_attack = threat
                if role is not None:
                    self.tactical_role = role

    def receive_list_kamikazes(self, kamikazes, quadtree_kamikazes=None):
        self.kamikazes = kamikazes
        self.quadtree_kamikazes = quadtree_kamikazes
        self.check_distance_kamikazes()
        self.vaporizer_gun.receive_list_kamikazes(kamikazes)
        self.freezing_gun.receive_list_kamikazes(kamikazes)

    def check_distance_kamikazes(self):
        p = self.location 
        closest = vec2(inf,inf)
        closest_distance = inf
        self.index_closest = 0
        self.kamikaze_to_attack = None

        if hasattr(self, 'quadtree_kamikazes') and isinstance(self.quadtree_kamikazes, Quadtree):
            search_radius = max(self.distance_chase, 150)
            range_rect = Rect(p.x, p.y, search_radius, search_radius)
            candidate_kamikazes = []
            self.quadtree_kamikazes.query(range_rect, candidate_kamikazes)
        else:
            candidate_kamikazes = self.kamikazes if self.kamikazes else []

        for k in candidate_kamikazes:
            distance = (p - k.location).magnitude()
            if distance < closest_distance:
                closest_distance = distance
                closest = k.location
                if self.kamikazes and k in self.kamikazes:
                    self.index_closest = self.kamikazes.index(k)
                self.kamikaze_to_attack = k

        self.closest_kamikaze = closest
        self.distance_closest_kamikaze = closest_distance

    def arrive(self, target):
        """
        Arrive steering behavior using proportional-derivative (PD) position control.
        """
        desired_force = self.kp * (target - self.location) - self.kv * self.velocity
        a_desired = limit(desired_force, self.max_force)
        self.applyForce(a_desired)
        if self.window is not None:
            pg.draw.circle(self.window, self.color_target, target, 5, 0)

    def collision_avoidance_leader(self, pos_leader):
        """
          avoid collision with leader drones
        """
        # check drones

        # --- Repulsion From obstacles
        for p in pos_leader:
            d = (self.location - p).length()
            factor_repulsion = 0.5
            dist_avoid = AVOID_DISTANCE + SIZE_DRONE*2
            if ( d < dist_avoid ) :
                f_repulsion = derivativeBivariate(factor_repulsion,factor_repulsion, p , self.location  )/SAMPLE_TIME
                #print(f_repulsion)
                f_repulsion = limit(f_repulsion,self.max_force*1.8)
             #----
                # This condition checks if drone collided with wall
                # if collided, this avoids that the drone goes over the obstacle
                if (d < AVOID_DISTANCE):
                    #self.applyForce(- self.velocity.normalize()*self.max_speed) 
                    self.velocity *= -1

                self.applyForce(-f_repulsion)

    def fire_vaporizer(self, kamikaze_position):
        target = getattr(self, 'kamikaze_to_attack', self.index_closest)
        bolt = self.vaporizer_gun.fire(target=target, origin=self.location)
        if bolt is not None:
            self.attack_status = (kamikaze_position, True)
            if getattr(self, 'projectiles_pool', None) is not None:
                self.projectiles_pool.append(bolt)
        else:
            self.attack_status = (kamikaze_position, False)

    def fire_freezing(self, kamikaze_position):
        target = getattr(self, 'kamikaze_to_attack', self.index_closest)
        bolt = self.freezing_gun.fire(target=target, origin=self.location)
        if bolt is not None:
            self.attack_status = (kamikaze_position, True)
            if getattr(self, 'projectiles_pool', None) is not None:
                self.projectiles_pool.append(bolt)
        else:
            self.attack_status = (kamikaze_position, False)

    def check_attack(self):
        return self.attack_status

    def update_attack_status(self):
        self.attack_status = (self.attack_status[1], False)

   # Deleting (Calling destructor)
    def __del__(self):
        #print('Loyalwingman destroyed')
        pass

class Kamikaze(Vehicle):
    '''
        The kamikaze drones are using behavior tree to operate
    '''
    def __init__(self, x, y, behavior, window, LoyalWingmen = [], leader = [], protected_area = None):
        super().__init__(x, y, behavior, window)

        # Variables to draw drone using Sprites
        if self.window is not None:
            self.drone = Kamikaze_drone() 
            self.all_sprites = pg.sprite.Group()
            self.all_sprites.add(self.drone)
        else:
            self.drone = None
            self.all_sprites = None
        self.loyalwingmen = LoyalWingmen
        self.closest_loyal = self.get_position()
        self.explode = False
        self.timer_explotion = 0
        self.leader_loyal = leader
        self.leader_position = leader.location
        self.protected_area = protected_area
        self.quadtree_loyal = None

        #timer for slowdown after freezing gun
        self.freezing_timer = TIME_FROZEN
        self.freezing = False

        self.debug = False

    def update(self):
        """
            Standart Euler integration
            Updates state machine
        """
        # updates behavior in machine state
        self.behavior.update(self)
        # Updates velocity at every step and limits it to max_speed
        self.velocity += self.acceleration * 1 
        self.velocity = limit(self.velocity, self.max_speed ) 
        # updates position
        # FREEZING LOGIC
        if self.freezing and self.freezing_timer > 0 :
            self.location += self.velocity * FREEZING_FACTOR 
            self.freezing_timer -= SAMPLE_TIME
        else:
            self.location += self.velocity

        # Prevents it from crazy spinning due to very low noise speeds
        if self.velocity.length() > 0.35:
            k = 2/3
            self.rotation = (atan2(self.velocity.y, self.velocity.x) - self.rotation) * k + self.rotation
        # Constrains position to limits of world 
        self.location = constrain(self.location,WORLD_WIDTH,WORLD_HEIGHT)
        self.acceleration *= 0

        # Memory of positions to draw Track
        self.memory_location.append((self.location.x,self.location.y))
        # size of track 
        if len(self.memory_location) > SIZE_TRACK:
            self.memory_location.pop(0)    

    def set_quadtree_loyal(self, quadtree_loyal):
        self.quadtree_loyal = quadtree_loyal

    def define_target(self):
        '''
            Criteria to select a loyal wingman to attack
        '''
        closest_loyal = vec2(inf, inf)
        distance_closest = inf

        if hasattr(self, 'quadtree_loyal') and isinstance(self.quadtree_loyal, Quadtree):
            search_radius = 400
            range_rect = Rect(self.location.x, self.location.y, search_radius, search_radius)
            candidate_loyal = []
            self.quadtree_loyal.query(range_rect, candidate_loyal)
        else:
            candidate_loyal = self.loyalwingmen if self.loyalwingmen else []

        valid_loyal = [l for l in candidate_loyal if not getattr(l, 'destroyed', False)]

        if len(valid_loyal) > 0:
            for l in valid_loyal:
                pos = l.get_position()
                distance_to_loyalwingman = (self.get_position() - pos).length()

                if distance_to_loyalwingman < distance_closest:
                    distance_closest = distance_to_loyalwingman
                    closest_loyal = pos
        elif self.leader_position:
            closest_loyal = self.leader_position
        else:
            closest_loyal = self.get_position()

        self.closest_loyal = closest_loyal
        return self.closest_loyal

    def get_closest_target(self):
        '''
            Return target to attack
        '''
        return self.closest_loyal
           
    def explode_loyalwingman(self, index):
        if self.loyalwingmen and index < len(self.loyalwingmen):
            drone = self.loyalwingmen[index]
            drone.destroyed = True
            self.loyalwingmen.pop(index)
    
    def explode_leader(self):
        if self.leader_loyal is not None:
            if hasattr(self.leader_loyal, 'destroy'):
                self.leader_loyal.destroy()
            else:
                self.leader_loyal.destroyed = True

    def check_collisions(self):
        """
        Detects physical impact with Loyal Wingmen and the Leader Drone.
        If contact occurs (within 2 * SIZE_DRONE), detonates kamikaze and destroys victim.
        """
        # 1. Collision with Loyal Wingmen
        if hasattr(self, 'quadtree_loyal') and isinstance(self.quadtree_loyal, Quadtree):
            search_radius = SIZE_DRONE * 2.5
            range_rect = Rect(self.location.x, self.location.y, search_radius, search_radius)
            candidate_loyal = []
            self.quadtree_loyal.query(range_rect, candidate_loyal)
        else:
            candidate_loyal = self.loyalwingmen if self.loyalwingmen else []

        for drone in candidate_loyal:
            if not getattr(drone, 'destroyed', False):
                dist = (self.location - drone.location).length()
                if dist <= SIZE_DRONE * 2:
                    drone.destroyed = True
                    if self.loyalwingmen and drone in self.loyalwingmen:
                        self.loyalwingmen.remove(drone)
                    self.explode = True
                    return

        # 2. Collision with Leader Drone
        if self.leader_loyal is not None and not getattr(self.leader_loyal, 'destroyed', False):
            dist_to_leader = (self.location - self.leader_loyal.location).length()
            if dist_to_leader <= SIZE_DRONE * 2:
                self.explode_leader()
                self.explode = True
                return

    def check_protected_area(self):
        # explode protected_area
        distance_to_protected_area = self.location.distance_to(self.protected_area.coordenates)
        if distance_to_protected_area <  self.protected_area.radius: 
            self.explode_protected_area()

    def explode_protected_area(self):
        self.explode = True # Self destruction command
        if self.protected_area.is_active():
            self.protected_area.attacked()
        else:
            print('Area Already destroyed')

    def get_explode_state(self):
        '''
            Return drone explosion state to delete simulation
        '''
        return self.explode

    def set_leader_position(self, leader_position):
        self.leader_position = leader_position      
        
    def slow_down(self, time = 5):
        self.freezing = True

    def arrive(self, target):
        """
            Arrive using position controler PV
        """
        # Calculates vector desired position
        #kp = 0.0024
        #kp = 50
        #kv = 800
        xi=0.9
        wn=15/60
        kv = 2*MASS*xi*wn
        kp = MASS*wn**2
        self.desired = kp * (target - self.location) - kv * self.velocity

        a_desired =  limit(self.desired, self.max_force)

        self.applyForce(a_desired)
        # Simulates Wind - random Noise
        #wind = vec2(random.uniform(-0.15,0.15) , random.uniform(-0.15,0.15)  )
        #self.applyForce(wind)
        # Draws current target as a point 
        if self.window is not None:
            pg.draw.circle(self.window, self.color_target ,target ,5, 0)

    def get_leader_position(self):
        return self.leader_loyal.location

    def __del__(self):
        #print('Kamikaze exploded')
        pass


