"""
Tactical Formation Engine for MUM-T Multi-UAV Simulation.
Implements the Strategy Pattern for analytical multi-UAV formation geometries:
- CircleFormation: Equidistant radial ring/orbit surrounding leader.
- WedgeFormation: Symmetrical swept-back V-formation (Arrowhead) oriented along heading.
- WallFormation: Lateral linear defensive barrier perpendicular to threat/heading axis.
- EchelonFormation: Stepped diagonal escort protecting leader's flank.
Includes optimal Hungarian slot-to-wingman assignment during re-formation transitions.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple, Any
import numpy as np
import pygame as pg
from pygame.math import Vector2
from scipy.optimize import linear_sum_assignment


class FormationStrategy(ABC):
    """Abstract Strategy base class for analytical formation slot generation."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def compute_slots(self,
                      leader_pos: Vector2,
                      leader_heading: float,
                      num_drones: int,
                      spacing: float) -> List[Vector2]:
        """
        Calculates world-space target coordinates for num_drones surrounding the leader.
        :param leader_pos: 2D world position of the leading UAV.
        :param leader_heading: Orientation angle (radians) of the leader.
        :param num_drones: Total active wingmen to slot.
        :param spacing: Formation spacing / radius parameter.
        :return: List of Vector2 target coordinates.
        """
        pass


class CircleFormation(FormationStrategy):
    """Radial orbit / equidistant perimeter ring surrounding the leader."""

    def __init__(self, distance_rings_factor: float = 1.2):
        super().__init__("CIRCLE")
        self.distance_rings_factor = distance_rings_factor

    def compute_slots(self,
                      leader_pos: Vector2,
                      leader_heading: float,
                      num_drones: int,
                      spacing: float) -> List[Vector2]:
        if num_drones <= 0:
            return []

        slots = []
        # Single ring for up to 8 drones, double rings for larger swarms
        if num_drones <= 8:
            step_angle = (2.0 * np.pi) / num_drones
            for i in range(num_drones):
                angle = leader_heading + i * step_angle
                slot = leader_pos + Vector2(spacing * np.cos(angle), spacing * np.sin(angle))
                slots.append(slot)
        else:
            # Multi-ring orbital distribution
            inner_count = num_drones // 2
            outer_count = num_drones - inner_count

            # Inner ring
            step_inner = (2.0 * np.pi) / inner_count
            for i in range(inner_count):
                angle = leader_heading + i * step_inner
                slot = leader_pos + Vector2(spacing * np.cos(angle), spacing * np.sin(angle))
                slots.append(slot)

            # Outer ring (with angular offset)
            outer_radius = spacing * self.distance_rings_factor
            step_outer = (2.0 * np.pi) / outer_count
            offset_angle = np.pi / outer_count
            for j in range(outer_count):
                angle = leader_heading + j * step_outer + offset_angle
                slot = leader_pos + Vector2(outer_radius * np.cos(angle), outer_radius * np.sin(angle))
                slots.append(slot)

        return slots


class WedgeFormation(FormationStrategy):
    """
    Symmetrical swept-back V-formation (Arrowhead).
    Leader at apex; wingmen trail backwards at swept angle (default 45°).
    """

    def __init__(self, sweep_angle_deg: float = 45.0):
        super().__init__("WEDGE")
        self.sweep_angle_rad = np.radians(sweep_angle_deg)

    def compute_slots(self,
                      leader_pos: Vector2,
                      leader_heading: float,
                      num_drones: int,
                      spacing: float) -> List[Vector2]:
        if num_drones <= 0:
            return []

        slots = []
        # Heading unit vector and lateral unit vector
        fwd = Vector2(np.cos(leader_heading), np.sin(leader_heading))
        right = Vector2(-np.sin(leader_heading), np.cos(leader_heading))

        dx = spacing * np.cos(self.sweep_angle_rad)
        dy = spacing * np.sin(self.sweep_angle_rad)

        for i in range(num_drones):
            tier = (i // 2) + 1
            is_right_wing = (i % 2 == 1)

            side_mult = 1.0 if is_right_wing else -1.0
            # Step backwards along forward axis, step outward along lateral axis
            offset = (-fwd * (tier * dx)) + (right * (tier * dy * side_mult))
            slots.append(leader_pos + offset)

        return slots


class WallFormation(FormationStrategy):
    """
    Lateral linear defensive wall perpendicular to leader's heading vector.
    Acts as an impenetrable barrier shielding the leader and protected base.
    """

    def __init__(self, setback_distance: float = 60.0):
        super().__init__("WALL")
        self.setback = setback_distance

    def compute_slots(self,
                      leader_pos: Vector2,
                      leader_heading: float,
                      num_drones: int,
                      spacing: float) -> List[Vector2]:
        if num_drones <= 0:
            return []

        slots = []
        fwd = Vector2(np.cos(leader_heading), np.sin(leader_heading))
        right = Vector2(-np.sin(leader_heading), np.cos(leader_heading))

        # Centered symmetric distribution along perpendicular line
        half_span = (num_drones - 1) / 2.0
        wall_center = leader_pos - (fwd * self.setback)

        for i in range(num_drones):
            offset_lateral = (i - half_span) * spacing
            slot = wall_center + (right * offset_lateral)
            slots.append(slot)

        return slots


class EchelonFormation(FormationStrategy):
    """
    Stepped diagonal echelon escort protecting leader's flank.
    Drones trail backwards and sideways at stepped intervals.
    """

    def __init__(self, side: str = "RIGHT", angle_deg: float = 45.0):
        super().__init__("ECHELON")
        self.side = side.upper()
        self.angle_rad = np.radians(angle_deg)

    def compute_slots(self,
                      leader_pos: Vector2,
                      leader_heading: float,
                      num_drones: int,
                      spacing: float) -> List[Vector2]:
        if num_drones <= 0:
            return []

        slots = []
        fwd = Vector2(np.cos(leader_heading), np.sin(leader_heading))
        right = Vector2(-np.sin(leader_heading), np.cos(leader_heading))

        side_mult = 1.0 if self.side == "RIGHT" else -1.0
        dx = spacing * np.cos(self.angle_rad)
        dy = spacing * np.sin(self.angle_rad)

        for i in range(1, num_drones + 1):
            offset = (-fwd * (i * dx)) + (right * (i * dy * side_mult))
            slots.append(leader_pos + offset)

        return slots


class FormationManager(object):
    """
    Coordinates available formation strategies and solves optimal
    Hungarian 1-to-1 slot matching to minimize drone transit distance.
    """

    def __init__(self, default_strategy: str = "CIRCLE"):
        self.strategies: Dict[str, FormationStrategy] = {
            "CIRCLE": CircleFormation(),
            "WEDGE": WedgeFormation(),
            "WALL": WallFormation(),
            "ECHELON": EchelonFormation(side="RIGHT")
        }
        self.active_strategy_name = default_strategy.upper()

    @property
    def current_strategy(self) -> FormationStrategy:
        return self.strategies.get(self.active_strategy_name, self.strategies["CIRCLE"])

    def set_strategy(self, name: str) -> bool:
        """Switches the active formation strategy by name."""
        clean_name = name.strip().upper()
        if clean_name in self.strategies:
            self.active_strategy_name = clean_name
            return True
        return False

    def compute_formation_slots(self,
                                 leader_pos: Vector2,
                                 leader_heading: float,
                                 num_drones: int,
                                 spacing: float) -> List[Vector2]:
        """Calculates raw geometric slot coordinates for the active strategy."""
        return self.current_strategy.compute_slots(leader_pos, leader_heading, num_drones, spacing)

    def assign_optimal_slots(self,
                             wingmen: List[Any],
                             slots: List[Vector2]) -> Dict[str, Vector2]:
        """
        Solves the Kuhn-Munkres (Hungarian) linear sum assignment problem between
        wingmen current positions and formation slot positions.
        Minimizes total transition Euclidean distance, preventing trajectory crossover.
        """
        n_w = len(wingmen)
        n_s = len(slots)
        if n_w == 0 or n_s == 0:
            return {}

        cost_matrix = np.zeros((n_w, n_s), dtype=np.float64)
        for i, w in enumerate(wingmen):
            w_pos = w.location
            for j, s in enumerate(slots):
                cost_matrix[i, j] = (w_pos - s).length()

        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        assigned_slots = {}
        for r, c in zip(row_ind, col_ind):
            drone = wingmen[r]
            drone_id = getattr(drone, 'agent_id', f"WINGMAN_{r}")
            assigned_slots[drone_id] = slots[c]

        return assigned_slots
