import pygame as pg
from utils import random_color, limit, constrain, bivariateFunction, derivativeBivariate, normalFunction
from constants import *
from animation import Aircraft, Kamikaze_drone
from math import cos, sin, atan2, pi, inf
import random
import copy 
from weapons import *
import numpy as np

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

        # Variables related to State Machine
        self.behavior = behavior

        self.window = window # tela em que esta acontecendo a simulaçao
        self.theta = 0 # variavel para o eight somada no seek_around
        self.count = 0

        # Variables to draw drone using Sprites
        self.drone = Aircraft() 
        self.all_sprites = pg.sprite.Group()
        self.all_sprites.add(self.drone)
    
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
        #if self.velocity.length() > 0.3:
        #self.rotation = atan2(self.velocity.y,self.velocity.x) 
        k = 2/3
        self.rotation =  (atan2(self.velocity.y,self.velocity.x) - self.rotation)*k + self.rotation
        # Constrains position to limits of screen 
        self.location = constrain(self.location,SCREEN_WIDTH,SCREEN_HEIGHT)
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
        pg.draw.circle(self.window, self.color_target ,target ,5, 0)

    def arrive(self, target):
        """
            Arrive Steering Behavior
        """
        # Calculates vector desired 
        self.desired = (target - self.location)
        # get the distance to the target
        d = self.desired.magnitude() 

        try:
            dist = copy.deepcopy(self.desired.normalize()) # obtem direção
        except: # If the magnitude of desired is zero it cant be normalized
            dist = copy.deepcopy(self.desired)
        
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
         During simulation it receives all the positions from all drones 
         index: is the current id of drone being checked 
        """
        # gets all positions of simultaneos drones
        self.index = index
        self.team = all_positions
        aux = 0 
        soma = vec2(0,0) # sums up all directions of close drones
        count = 0 # counts the number of drones that are close
        for p in all_positions:
        # compares current position to all the drones
        # aux != index -> avoids the auto-collision check
            d = (self.location - p.location).magnitude()
            separation_factor = 2.2
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
                  
    def draw(self, window):

        """
            Defines shape of vehicle and draw it to screen
        """

        # draws track
        if len(self.memory_location) >= 2:
            pg.draw.lines(self.window, self.color_target, False, self.memory_location, 1)
        # Drawing drone's outer circle as a hitbox?
        if self.debug == True:
            pg.draw.circle(self.window, (100, 100, 100), self.location, AVOID_DISTANCE, 1)
            #pg.draw.line(self.window, (100, 100, 100), self.location, self.location+self.desired , 1)
            # Draw Direction
            v = self.velocity.length()
            pg.draw.line(self.window, (255, 0, 0), self.location, self.location + self.velocity.normalize()*v*20 , 1)

        # usar sprite para desenhar drone
        self.all_sprites.draw(self.window)
        self.all_sprites.update(self.location,self.rotation)

    def collision_avoidance(self, positions_drones , pos_obstacles , index):
        """
            Not working yet, it should detect obstacles and collision with other drones
        """
        # check drones
        f = 1
        aux = 0 
        for p in positions_drones:
            d = (self.location - p.location).length()
            factor_distance = 2
            dist_avoid = AVOID_DISTANCE*factor_distance
            # Distance between loyal wingman drones

            #dist_avoid = 2 * pi * DISTANCE_LEADER / NUM_DRONES 
            if ( d < dist_avoid )  and (aux != index):
                #f = (self.velocity - self.velocity.normalize()*self.max_speed )/ SAMPLE_TIME
                #f = limit(f,self.max_force)
                #self.velocity *= d/(AVOID_DISTANCE*factor_distance)
                f_repulsion = derivativeBivariate(0.001,.001, p.location , self.location )/SAMPLE_TIME
                #print(f_repulsion)
                f_repulsion = limit(f_repulsion,self.max_force*1.8)

                self.applyForce(-f_repulsion)
                #print(f'Alerta de colisão drone {index} com drone {aux}')
                break
            aux +=1

        # --- Repulsion From obstacles
        for p in pos_obstacles:
            d = (self.location - p).length()
            factor_repulsion = 0.005
            dist_avoid = RADIUS_OBSTACLES*1.6 + AVOID_DISTANCE
            if ( d < dist_avoid ) :
                f_repulsion = derivativeBivariate(factor_repulsion,factor_repulsion, p , self.location  )/SAMPLE_TIME
                #print(f_repulsion)
                f_repulsion = limit(f_repulsion,self.max_force*1.8)
             #----
                # This condition checks if drone collided with wall
                # if collided, this avoids that the drone goes over the obstacle
                if (d < AVOID_DISTANCE):
                    self.applyForce(- self.velocity.normalize()*self.max_speed) 
                    
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

        # Variables related to State Machine
        self.behavior = behavior
        self.window = window # tela em que esta acontecendo a simulaçao
        self.theta = 0 # variavel para o eight somada no seek_around
        self.count = 0

        # Variables to draw drone using Sprites
        self.drone = Aircraft() 
        self.all_sprites = pg.sprite.Group()
        self.all_sprites.add(self.drone)
    
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
        # Constrains position to limits of screen 
        self.location = constrain(self.location,SCREEN_WIDTH,SCREEN_HEIGHT)
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
            dist = copy.deepcopy(self.desired.normalize()) # obtem direção
        except: # If the magnitude of desired is zero it cant be normalized
            dist = copy.deepcopy(self.desired)
        
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
        pg.draw.circle(self.window, self.color_target ,target ,5, 0)

    def arrive(self, target):
        """
            Arrive Steering Behavior
        """
        # Calculates vector desired 
        self.desired = (target - self.location)
        # get the distance to the target
        d = self.desired.magnitude() 

        try:
            dist = copy.deepcopy(self.desired.normalize()) # obtem direção
        except: # If the magnitude of desired is zero it cant be normalized
            dist = copy.deepcopy(self.desired)
        
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
        pg.draw.circle(self.window, self.color_target ,target ,5, 0)

    def set_formation(self, num_drones = NUM_DRONES, distance_leader = DISTANCE_LEADER):
        '''
            This method returns the positions for the loyal wingman surrounding the leading drone

            input: number of drones in formation
            return: list of positions
        '''
        if num_drones > 1: # check if there is still loyalwingmen
            step_angle = 2 * pi / num_drones 
        else:
            step_angle = 0

        pos = self.get_position()
        #print(f'position leader:{pos}')
        ang = 0
        list_positions = []
        # calculates position of drone in formation
        for _ in range(num_drones):
            x = pos[0] + distance_leader*cos(ang)
            y = pos[1] + distance_leader*sin(ang)
            #print(f'position wingman:{(x,y)}')
            #print(f'angulo: {ang*180/pi}')
            ang += step_angle
            
            list_positions.append( vec2( x, y ) )

        return list_positions

    def destroyed(self):
        self.destroyed = True

class LoyalWingman(Vehicle):
    def __init__(self, x, y, behavior, window, distance_chase = 400):
        super().__init__(x, y, behavior, window)
        self.error = vec2(0,0)
        self.kamikazes = None
        self.vaporizer_gun = Vaporizer(1,10,1,100,self.kamikazes)
        self.freezing_gun  = Freezing(1,10,1,300,self.kamikazes)
        self.closest_kamikaze = vec2(inf,inf)
        self.distance_closest_kamikaze = inf
        self.attack_status = ( vec2(0,0) , False ) # position attacked and sucessfull or not
        self.kamikaze_to_attack = None

        # param for chase a threat 
        self.distance_chase = distance_chase

    def receive_list_kamikazes(self, kamikazes):
        self.kamikazes = kamikazes
        self.check_distance_kamikazes()
        self.vaporizer_gun.receive_list_kamikazes(kamikazes)
        self.freezing_gun.receive_list_kamikazes(kamikazes)

    def check_distance_kamikazes(self):
        p = self.location 
        closest = vec2(inf,inf)
        closest_distance = inf
        self.index_closest = 0

        for index ,k in enumerate(self.kamikazes):
            distance = (p - k.location).magnitude()
            if distance < closest_distance:
                closest_distance = distance
                closest = k.location
                self.index_closest = index 
                self.kamikaze_to_attack = k

        self.closest_kamikaze = closest
        self.distance_closest_kamikaze = closest_distance
        
        # draws vaporizing gun shot
        if closest_distance < 100:
            pg.draw.line(self.window, (100, 0, 0), self.location, self.closest_kamikaze , 1)

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
        pg.draw.circle(self.window, self.color_target ,target ,5, 0)

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
                    self.applyForce(- self.velocity.normalize()*self.max_speed) 
                    
                self.applyForce(-f_repulsion)

    def fire_vaporizer(self, kamikaze_position):
        # check distanceß
        #print(f' Atirei no kamikaze me {kamikaze_position}')
        try:
            # check if attack was successful or not
            status = self.vaporizer_gun.fire(self.index_closest)
            self.attack_status = (  kamikaze_position, status )
        except:
            print('All kamikazes were destroyed')

    def fire_freezing(self, kamikaze_position):
        # check distanceß
        #print(f' Atirei no kamikaze me {kamikaze_position}')
        try:
            # check if attack was successful or not
            status = self.freezing_gun.fire(self.index_closest)
            # draws freezing gun shot if executed
            if status:
                pg.draw.line(self.window, (0, 100, 0), self.location, self.closest_kamikaze , 3)

        except:
            print('All kamikazes were destroyed')

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
    def __init__(self, x, y, behavior, window, LoyalWingmen = [], leader = []):
        super().__init__(x, y, behavior, window)

        # Variables to draw drone using Sprites
        self.drone = Kamikaze_drone() 
        self.all_sprites = pg.sprite.Group()
        self.all_sprites.add(self.drone)
        self.loyalwingmen = LoyalWingmen
        self.closest_loyal = self.get_position()
        self.explode = False
        self.timer_explotion = 0
        self.leader_loyal = leader
        self.leader_position = leader.location

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
        #if self.velocity.length() > 0.3:
        #self.rotation = atan2(self.velocity.y,self.velocity.x) 
        k = 2/3
        self.rotation =  (atan2(self.velocity.y,self.velocity.x) - self.rotation)*k + self.rotation
        # Constrains position to limits of screen 
        self.location = constrain(self.location,SCREEN_WIDTH,SCREEN_HEIGHT)
        self.acceleration *= 0

        # Memory of positions to draw Track
        self.memory_location.append((self.location.x,self.location.y))
        # size of track 
        if len(self.memory_location) > SIZE_TRACK:
            self.memory_location.pop(0)    

    def define_target(self):
        '''
            Criteria to select a loyal wingman to attack
        '''
        closest_loyal = vec2(inf,inf)
        distance_closest = inf
        index_loyal = 0

        if len(self.loyalwingmen) > 0: # check if there are loyalwingman 
            for l in self.loyalwingmen:
                pos = l.get_position() # position of loyalwingman
                distance_to_loyalwingman = (self.get_position() - pos).length()

                if distance_to_loyalwingman < distance_closest:
                    distance_closest = distance_to_loyalwingman
                    closest_loyal = pos

                if distance_to_loyalwingman < SIZE_DRONE*2: # Radius of explotion
                    self.explode_loyalwingman(index_loyal)
                    self.explode = True # Self destruction command
                
                index_loyal += 1
        #else: # no more loyalwingman left
        if self.leader_position: # leader is the last
            closest_loyal = self.leader_position
            distance_to_leader = self.location.distance_to(self.leader_position)
            if distance_to_leader < SIZE_DRONE*2: 
                self.explode_leader()
                self.explode = True #

        else:# no more drones left
            closest_loyal = self.get_position()


        self.closest_loyal = closest_loyal

    def get_closest_target(self):
        '''
            Return target to attack
        '''
        return self.closest_loyal
           
    def explode_loyalwingman(self, index):
        self.loyalwingmen.pop(index)
    
    def explode_leader(self):
        try:
            self.leader_loyal.destroyed()
        except:
            print('Leader Already destroyed')

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
        pg.draw.circle(self.window, self.color_target ,target ,5, 0)

    def get_leader_position(self):
        return self.leader_loyal.location

    def __del__(self):
        #print('Kamikaze exploded')
        pass


