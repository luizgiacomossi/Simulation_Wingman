import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from pygame.math import Vector2

try:
    from scipy.optimize import linear_sum_assignment
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

class TargetAllocator:
    """
    Cooperative Target Allocation System for Loyal Wingman Swarm.
    Uses the Hungarian (Kuhn-Munkres) algorithm to solve the linear sum
    assignment problem, mapping defenders to hostile threats optimally
    without duplicate targeting.
    """
    def __init__(self,
                 weight_dist: float = 1.0,
                 weight_base_threat: float = 2.5,
                 weight_leader_threat: float = 1.5,
                 reassign_interval: float = 0.25):
        """
        :param weight_dist: Cost weight for distance between defender and threat.
        :param weight_base_threat: Priority weight for threats closing in on the base.
        :param weight_leader_threat: Priority weight for threats targeting the leader.
        :param reassign_interval: Seconds between full Hungarian reassignments.
        """
        self.weight_dist = weight_dist
        self.weight_base_threat = weight_base_threat
        self.weight_leader_threat = weight_leader_threat
        self.reassign_interval = reassign_interval
        self.time_since_reassign = 0.0

        # Telemetry metrics
        self.total_assignments_made = 0
        self.redundant_conflicts_prevented = 0

    def compute_cost_matrix(self,
                            wingmen: List[Any],
                            kamikazes: List[Any],
                            base_pos: Optional[Vector2] = None,
                            leader_pos: Optional[Vector2] = None) -> np.ndarray:
        """
        Constructs the M x N cost matrix C_ij where:
          C_ij = w_d * dist(W_i, K_j) - w_b * (max_dist - dist(K_j, Base)) - w_l * (max_dist - dist(K_j, Leader))
        
        Lower cost indicates higher suitability and urgency for W_i to engage K_j.
        """
        M = len(wingmen)
        N = len(kamikazes)
        if M == 0 or N == 0:
            return np.empty((0, 0))

        cost_matrix = np.zeros((M, N), dtype=np.float64)
        max_diagonal = 2500.0  # reference world diagonal bound

        for j, k in enumerate(kamikazes):
            k_loc = getattr(k, 'location', Vector2(0, 0))

            # Threat urgency to Base
            urgency_base = 0.0
            if base_pos is not None:
                dist_base = k_loc.distance_to(base_pos)
                urgency_base = max(0.0, max_diagonal - dist_base)

            # Threat urgency to Leader
            urgency_leader = 0.0
            if leader_pos is not None:
                dist_leader = k_loc.distance_to(leader_pos)
                urgency_leader = max(0.0, max_diagonal - dist_leader)

            for i, w in enumerate(wingmen):
                w_loc = getattr(w, 'location', Vector2(0, 0))
                dist_w = w_loc.distance_to(k_loc)

                # Ammo / weapon readiness discount
                ammo_factor = 0.0
                if hasattr(w, 'vaporizer_gun') and hasattr(w.vaporizer_gun, 'available') and w.vaporizer_gun.available:
                    ammo_factor += 100.0

                # Composite cost (minimized by Hungarian solver)
                cost = (self.weight_dist * dist_w
                        - (self.weight_base_threat * urgency_base * 0.4)
                        - (self.weight_leader_threat * urgency_leader * 0.3)
                        - ammo_factor)
                cost_matrix[i, j] = cost

        # Shift all costs so matrix is strictly positive (required by assignment algorithms)
        min_val = np.min(cost_matrix)
        if min_val < 0:
            cost_matrix -= min_val

        return cost_matrix

    def solve_assignment(self,
                         wingmen: List[Any],
                         kamikazes: List[Any],
                         base_pos: Optional[Vector2] = None,
                         leader_pos: Optional[Vector2] = None) -> Dict[Any, Optional[Any]]:
        """
        Computes optimal 1-to-1 matching from wingmen to threats.
        Returns: Dict mapping each wingman instance to its assigned threat (or None if unassigned).
        """
        assignments: Dict[Any, Optional[Any]] = {w: None for w in wingmen}
        M = len(wingmen)
        N = len(kamikazes)

        if M == 0 or N == 0:
            return assignments

        cost_matrix = self.compute_cost_matrix(wingmen, kamikazes, base_pos, leader_pos)

        if HAS_SCIPY:
            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            for r, c in zip(row_ind, col_ind):
                w = wingmen[r]
                k = kamikazes[c]
                assignments[w] = k
        else:
            # Greedy unique fallback if SciPy is not available
            used_cols = set()
            sorted_indices = np.argsort(cost_matrix, axis=None)
            for flat_idx in sorted_indices:
                r, c = divmod(flat_idx, N)
                if r not in [wingmen.index(w) for w, target in assignments.items() if target is not None] and c not in used_cols:
                    assignments[wingmen[r]] = kamikazes[c]
                    used_cols.add(c)
                if len(used_cols) >= min(M, N):
                    break

        self.total_assignments_made += len([t for t in assignments.values() if t is not None])
        return assignments

    def update_cooperative_targeting(self,
                                     wingmen: List[Any],
                                     kamikazes: List[Any],
                                     dt: float,
                                     base_pos: Optional[Vector2] = None,
                                     leader_pos: Optional[Vector2] = None,
                                     force: bool = False):
        """
        Orchestrates periodic reassignment and distributes target handles to each wingman.
        """
        self.time_since_reassign += dt

        # Reassign periodically or immediately if threat population changed
        if force or self.time_since_reassign >= self.reassign_interval:
            self.time_since_reassign = 0.0

            # Filter valid living threats
            valid_kamikazes = [k for k in kamikazes if not getattr(k, 'explode', False)]
            valid_wingmen = [w for w in wingmen if not getattr(w, 'destroyed', False)]

            assignments = self.solve_assignment(valid_wingmen, valid_kamikazes, base_pos, leader_pos)

            # Assign targets and roles to agents
            for w in valid_wingmen:
                assigned_threat = assignments.get(w, None)
                w.assigned_threat = assigned_threat
                if assigned_threat is not None:
                    w.tactical_role = "INTERCEPTOR"
                else:
                    w.tactical_role = "CLOSE_ESCORT"
