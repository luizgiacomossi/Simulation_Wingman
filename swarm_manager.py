import random
from random import uniform
from typing import List, Tuple
import pygame
from constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT, WORLD_WIDTH, WORLD_HEIGHT,
    NUM_DRONES, NUM_KAMIKAZES, DISTANCE_LEADER, RESOLUTION,
    SIZE_DRONE, LIGHT_BLUE, TIME_EXPLOSION, SAMPLE_TIME
)
from quadtree import Quadtree, Rect
from vehicle import Vehicle, LoyalWingman, Kamikaze, LeadingDrone
from state_machine import (
    FiniteStateMachine, SeekState, WaitState, AttackLeaderState,
    AttackLoyalWingmanState, AttackProtectedAreaState, AttackKamikazeState
)
from decision_making import LoyalWingmanBehaviorTree
from animation import Explosion_kamikaze, ProtectedArea
from utils import generate_coordenates_kamikaze
from target_allocator import TargetAllocator
from message_manager import MessageManager, TacticalMessage, MessageTopic

vec2 = pygame.math.Vector2

class SwarmManager(object):
    """
    Manages all drone entities, swarm formations, spatial Quadtrees,
    and update lifecycle for Loyal Wingman and Kamikaze swarms.
    Works seamlessly in both graphical mode and high-speed headless mode.
    """
    def __init__(self, window=None):
        self.window = window
        self.swarm: List[LoyalWingman] = []
        self.kamikazes: List[Kamikaze] = []
        self.explosions: List[Explosion_kamikaze] = []
        self.projectiles: List[Any] = []
        self.leadingdrone: LeadingDrone = None
        self.protected_area: ProtectedArea = None

        self.behaviors = []
        self.counter_kamikazes_destroyed = 0
        self.num_kamikazes = NUM_KAMIKAZES
        self.num_loyalwingman = NUM_DRONES
        self.distance_formation = DISTANCE_LEADER
        self.distance_rings_formation = 1.2
        self.distance_chase = 306.6
        self.target_allocator = TargetAllocator()
        self.allocation_mode = "hungarian"
        self.message_manager = MessageManager()
        self.simulation_time = 0.0

    def create_swarm(self, num_loyal=NUM_DRONES, num_kamikazes=NUM_KAMIKAZES,
                     distance_chase=306.6, kp=0.625, kv=4.5,
                     distance_formation=DISTANCE_LEADER, distance_rings_formation=1.2,
                     protected_area_pos=None, protected_area_radius=None):
        """
        Initializes the entire multi-UAV battlefield with leader, wingmen, kamikazes, and protected area.
        """
        if protected_area_pos is None:
            protected_area_pos = vec2(WORLD_WIDTH - 100, min(170, WORLD_HEIGHT * 0.2))
        if protected_area_radius is None:
            protected_area_radius = min(240, int(WORLD_HEIGHT * 0.26))

        self.num_loyalwingman = num_loyal
        self.num_kamikazes = num_kamikazes
        self.distance_chase = distance_chase
        self.distance_formation = distance_formation
        self.distance_rings_formation = distance_rings_formation
        self.counter_kamikazes_destroyed = 0
        self.message_manager.clear()
        self.simulation_time = 0.0

        self.swarm = []
        self.kamikazes = []
        self.explosions = []
        self.projectiles = []
        self.behaviors = []

        # Create Protected Area
        self.protected_area = ProtectedArea(
            radius=protected_area_radius,
            coordenates=protected_area_pos,
            window=self.window
        )

        # Create Leading Drone
        self.create_leading_drone(distance_formation=distance_formation)
        if self.leadingdrone is not None:
            self.leadingdrone.set_message_bus(self.message_manager, agent_id="LEADER")

        # Create Loyal Wingman Swarm
        spacing_spawn = max(35.0, (WORLD_WIDTH * 0.25) / max(1, num_loyal))
        for d in range(num_loyal):
            bt = LoyalWingmanBehaviorTree()
            self.behaviors.append(bt)
            spawn_x = WORLD_WIDTH - 50 - (d * spacing_spawn)
            spawn_y = 30 + (d % 2) * 40
            drone = LoyalWingman(
                spawn_x,
                spawn_y,
                bt,
                self.window,
                self.protected_area,
                distance_chase=distance_chase,
                kp=kp,
                kv=kv
            )
            drone.index = d
            drone.projectiles_pool = self.projectiles
            drone.set_message_bus(self.message_manager, agent_id=f"WINGMAN_{d}")
            self.swarm.append(drone)

        # Create Kamikaze Swarm
        for d in range(num_kamikazes):
            fsm = FiniteStateMachine(WaitState())
            self.behaviors.append(fsm)
            drone = Kamikaze(
                random.uniform(0, 50),
                random.uniform(0, 50),
                fsm,
                self.window,
                LoyalWingmen=self.swarm,
                leader=self.leadingdrone,
                protected_area=self.protected_area
            )
            self.kamikazes.append(drone)

    def create_leading_drone(self, distance_formation):
        self.leadingdrone = LeadingDrone(
            WORLD_WIDTH / 2,
            WORLD_HEIGHT / 2,
            FiniteStateMachine(SeekState()),
            self.window,
            distance_leader=distance_formation,
            distance_rings_formation=self.distance_rings_formation
        )

    def create_kamikaze(self):
        """Spawns a new kamikaze targeting leader, loyal wingmen, or protected area."""
        prob = uniform(0, 1)
        if prob < 0.33:
            fsm = FiniteStateMachine(AttackLeaderState())
        elif prob < 0.66:
            fsm = FiniteStateMachine(AttackLoyalWingmanState())
        else:
            fsm = FiniteStateMachine(AttackProtectedAreaState())

        self.behaviors.append(fsm)
        pos = generate_coordenates_kamikaze()
        drone = Kamikaze(
            pos[0], pos[1],
            fsm,
            self.window,
            LoyalWingmen=self.swarm,
            leader=self.leadingdrone,
            protected_area=self.protected_area
        )
        self.kamikazes.append(drone)

    def add_kamikaze(self, pos=None):
        fsm = FiniteStateMachine(AttackKamikazeState())
        self.behaviors.append(fsm)
        if pos is None:
            pos = vec2(0, random.uniform(0, WORLD_HEIGHT))
        drone = Kamikaze(
            pos.x, pos.y,
            fsm,
            self.window,
            LoyalWingmen=self.swarm,
            leader=self.leadingdrone,
            protected_area=self.protected_area
        )
        self.kamikazes.append(drone)

    def set_target_leader(self, target):
        if self.leadingdrone is not None:
            self.leadingdrone.set_target(target)
            list_pos = self.leadingdrone.set_formation()
            self.goto_formation(list_pos)

    def set_formation_strategy(self, name: str) -> bool:
        """Changes active formation geometry (CIRCLE, WEDGE, WALL, ECHELON)."""
        if self.leadingdrone is not None:
            return self.leadingdrone.set_formation_strategy(name)
        return False

    def goto_formation(self, targets):
        if not self.swarm or not targets:
            return

        slots_dict = {}
        if self.leadingdrone is not None and hasattr(self.leadingdrone, 'formation_manager'):
            # Optimal Hungarian 1-to-1 matching to prevent crossing trajectories during re-formation
            assigned = self.leadingdrone.formation_manager.assign_optimal_slots(self.swarm, targets)
            for drone in self.swarm:
                slot_pos = assigned.get(drone.agent_id)
                if slot_pos is not None:
                    drone.set_target(slot_pos)
                    slots_dict[drone.agent_id] = slot_pos
        else:
            for i, drone in enumerate(self.swarm):
                if i < len(targets):
                    drone.set_target(targets[i])
                    slots_dict[drone.agent_id or f"WINGMAN_{i}"] = targets[i]

        if self.leadingdrone is not None:
            self.leadingdrone.broadcast_formation_command(
                slots_dict=slots_dict,
                formation_type=getattr(self.leadingdrone, 'current_formation_name', 'CIRCLE'),
                current_time=self.simulation_time
            )

    def update(self, list_obst=[]):
        """
        Executes one physics and tactical decision step:
        1. Updates leader position.
        2. Builds dynamic spatial Quadtrees for Wingmen and Kamikazes.
        3. Updates Loyal Wingmen (alignment, avoidance, weapons, attacks).
        4. Updates Kamikazes (targeting, strikes, explosions).
        5. Updates formation targets and active explosions.
        """
        self.simulation_time += SAMPLE_TIME
        self.message_manager.update(self.simulation_time)

        # 1. Leading drone
        self.leadingdrone.update()
        pos_leader = [self.leadingdrone.location]

        # 2. Build Quadtrees
        boundary = Rect(WORLD_WIDTH / 2, WORLD_HEIGHT / 2, WORLD_WIDTH / 2, WORLD_HEIGHT / 2)
        quadtree_loyal = Quadtree(boundary, 4)
        for drone in self.swarm:
            quadtree_loyal.insert(drone.location, drone)

        quadtree_kamikazes = Quadtree(boundary, 4)
        for k in self.kamikazes:
            quadtree_kamikazes.insert(k.location, k)

        # 2.5. Cooperative Target Allocation (Hungarian Algorithm)
        if self.allocation_mode == "hungarian" and self.target_allocator is not None:
            base_pos = self.protected_area.coordenates if self.protected_area else None
            leader_pos = self.leadingdrone.location if self.leadingdrone else None
            self.target_allocator.update_cooperative_targeting(
                wingmen=self.swarm,
                kamikazes=self.kamikazes,
                dt=SAMPLE_TIME,
                base_pos=base_pos,
                leader_pos=leader_pos
            )

        # 3. Update Loyal Wingmen
        for index, drone in enumerate(self.swarm):
            drone.process_tactical_messages(self.simulation_time)
            drone.align_swarm(quadtree_loyal, index)
            drone.collision_avoidance(quadtree_loyal, list_obst, index)
            drone.collision_avoidance_leader(pos_leader)
            drone.update()
            drone.receive_list_kamikazes(self.kamikazes, quadtree_kamikazes)

            # Attack logic
            attack_status = drone.check_attack()
            if attack_status[1]:
                drone.update_attack_status()

        # 3.5. Update In-Flight Projectiles & Ballistic Interception
        for proj in self.projectiles:
            proj.update(SAMPLE_TIME)
            if not proj.alive:
                continue

            search_box = Rect(proj.position.x, proj.position.y, proj.radius + SIZE_DRONE, proj.radius + SIZE_DRONE)
            candidate_kamikazes = quadtree_kamikazes.query(search_box)
            if not candidate_kamikazes:
                candidate_kamikazes = self.kamikazes

            for k in candidate_kamikazes:
                if not getattr(k, 'destroyed', False) and not getattr(k, 'explode', False):
                    dist = (proj.position - k.location).length()
                    if dist <= proj.radius + SIZE_DRONE:
                        proj.on_hit(k, self)
                        break

        # Purge inactive projectiles
        self.projectiles[:] = [p for p in self.projectiles if p.alive]

        # 4. Update Kamikazes
        exploded_indices = []
        for index, kamikaze in enumerate(self.kamikazes):
            if kamikaze.get_explode_state() or getattr(kamikaze, 'destroyed', False):
                self.explosions.append(Explosion_kamikaze(kamikaze.location, self.window))
                exploded_indices.append(index)
                continue

            kamikaze.set_leader_position(pos_leader[-1])
            kamikaze.set_quadtree_loyal(quadtree_loyal)
            kamikaze.align_swarm(quadtree_kamikazes, index)
            kamikaze.collision_avoidance(quadtree_kamikazes, list_obst, index)
            kamikaze.update()
            kamikaze.check_collisions()
            kamikaze.check_protected_area()

            if kamikaze.get_explode_state() or getattr(kamikaze, 'destroyed', False):
                self.explosions.append(Explosion_kamikaze(kamikaze.location, self.window))
                exploded_indices.append(index)

        # Remove exploded kamikazes
        for idx in reversed(exploded_indices):
            if idx < len(self.kamikazes):
                self.kamikazes.pop(idx)

        # Clean up destroyed loyal wingmen
        destroyed_wingmen = [w for w in self.swarm if getattr(w, 'destroyed', False)]
        for w in destroyed_wingmen:
            self.explosions.append(Explosion_kamikaze(w.location, self.window))
            if getattr(w, 'message_bus', None) is not None:
                w.broadcast_message("CASUALTY_ALERT", {"casualty_id": w.agent_id, "position": (w.location.x, w.location.y)}, self.simulation_time)
                self.message_manager.unregister_agent(w.agent_id)
        self.swarm[:] = [w for w in self.swarm if not getattr(w, 'destroyed', False)]

        # Maintain constant number of threats
        while len(self.kamikazes) < self.num_kamikazes:
            self.counter_kamikazes_destroyed += 1
            self.create_kamikaze()

        # 5. Update formation targets
        list_pos = self.leadingdrone.set_formation(num_drones=len(self.swarm))
        self.goto_formation(list_pos)

        # 6. Update explosions
        for idx in reversed(range(len(self.explosions))):
            exp = self.explosions[idx]
            exp.draw()
            if exp.delete_explosion_status():
                self.explosions.pop(idx)

    def check_mission_status(self) -> Tuple[bool, str]:
        """
        Determines if simulation episode has reached a terminal condition.
        Returns: (is_finished, end_reason)
        """
        if self.leadingdrone is not None and getattr(self.leadingdrone, 'destroyed', False) is True:
            return True, "Leader Destroyed"
        if self.protected_area is not None and not self.protected_area.is_active():
            return True, "Protected Area Destroyed"
        if len(self.swarm) < 1:
            return True, "All Loyal Destroyed"
        if len(self.kamikazes) == 0:
            return True, "All Kamikazes Destroyed"
        return False, "Running"

    def draw(self, surface, display_manager=None):
        """
        Renders all swarm entities, formation perimeters, HUD markers, and protected area.
        """
        if surface is None:
            return

        # Draw leader and dynamic formation guide
        if self.leadingdrone is not None:
            if hasattr(self.leadingdrone, 'draw_formation_guide'):
                self.leadingdrone.draw_formation_guide(surface, num_drones=len(self.swarm))
            self.leadingdrone.draw(surface)
            if display_manager is not None:
                img = display_manager.get_rendered_text(display_manager.font20, 'Leading Drone', LIGHT_BLUE)
                surface.blit(img, self.leadingdrone.get_position() + (0, 20))

        # Draw Loyal Wingmen
        for index, drone in enumerate(self.swarm):
            drone.draw(surface)
            if display_manager is not None:
                img = display_manager.get_rendered_text(display_manager.font20, f'LoyalWingman {index+1}', LIGHT_BLUE)
                surface.blit(img, drone.get_position() + (0, 20))
                ammo_vap = drone.vaporizer_gun.get_ammo_available()
                ammo_frz = drone.freezing_gun.get_ammo_available()
                img_ammo = display_manager.get_rendered_text(display_manager.font15, f'V: {ammo_vap} F:{ammo_frz}', LIGHT_BLUE)
                surface.blit(img_ammo, drone.get_position() + (0, 30))

        # Draw Protected Area
        if self.protected_area is not None:
            self.protected_area.draw()

        # Draw Kamikazes
        for index, k in enumerate(self.kamikazes):
            k.draw(surface)
            if display_manager is not None:
                img = display_manager.get_rendered_text(display_manager.font20, f'Kamikaze {index+1}', LIGHT_BLUE)
                surface.blit(img, k.get_position() + (0, 20))
                state_name = k.behavior.get_current_state()
                img_state = display_manager.get_rendered_text(display_manager.font15, state_name, LIGHT_BLUE)
                surface.blit(img_state, k.get_position() + (0, 30))

        # Draw Projectile Tracers
        for proj in self.projectiles:
            proj.draw(surface, display_manager)
