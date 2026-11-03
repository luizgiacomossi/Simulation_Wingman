import time
import numpy as np
import pygame as pg
from pygame.math import Vector2
from target_allocator import TargetAllocator
from swarm_manager import SwarmManager
from headless_runner import run_headless_episode

def test_cost_matrix_and_uniqueness():
    """Validates STEP 1.1 and STEP 1.2: Cost matrix properties and Hungarian 1-to-1 matching."""
    print("=== [TEST 1] Testing Cost Matrix & Hungarian Uniqueness ===")
    allocator = TargetAllocator()

    class MockDrone:
        def __init__(self, x, y, name):
            self.location = Vector2(x, y)
            self.name = name
            self.explode = False
            self.destroyed = False
            self.assigned_threat = None
            self.tactical_role = None

    wingmen = [
        MockDrone(100, 100, "W1"),
        MockDrone(200, 200, "W2"),
        MockDrone(300, 300, "W3"),
        MockDrone(400, 400, "W4")
    ]

    kamikazes = [
        MockDrone(120, 110, "K1"),  # Very close to W1
        MockDrone(210, 190, "K2"),  # Very close to W2
        MockDrone(500, 500, "K3")   # Far
    ]

    base_pos = Vector2(1500, 200)
    leader_pos = Vector2(800, 400)

    # 1. Cost matrix computation
    C = allocator.compute_cost_matrix(wingmen, kamikazes, base_pos, leader_pos)
    assert C.shape == (4, 3), f"Expected shape (4, 3), got {C.shape}"
    assert np.all(C >= 0), "Cost matrix contains negative values!"
    print(f"✓ Cost Matrix shape {C.shape} computed successfully and is strictly non-negative.")

    # 2. Hungarian solving
    assignments = allocator.solve_assignment(wingmen, kamikazes, base_pos, leader_pos)
    assert len(assignments) == 4, "Every wingman must have an assignment entry"

    assigned_threats = [t for t in assignments.values() if t is not None]
    assert len(assigned_threats) == 3, f"Expected 3 threats assigned, got {len(assigned_threats)}"
    assert len(set(assigned_threats)) == len(assigned_threats), "Duplicate threat assignments detected! Hungarian matching violated."
    print("✓ Hungarian Algorithm produced 100% unique 1-to-1 assignments with zero duplicate locks.")

    # 3. Update targeting (Roles check)
    allocator.update_cooperative_targeting(wingmen, kamikazes, dt=1.0, base_pos=base_pos, leader_pos=leader_pos, force=True)
    interceptors = [w for w in wingmen if w.tactical_role == "INTERCEPTOR"]
    escorts = [w for w in wingmen if w.tactical_role == "CLOSE_ESCORT"]

    assert len(interceptors) == 3, f"Expected 3 interceptors, got {len(interceptors)}"
    assert len(escorts) == 1, f"Expected 1 close escort, got {len(escorts)}"
    print(f"✓ Role Specialization verified: {len(interceptors)} Interceptors, {len(escorts)} Close Escorts.")
    print("All mathematical unit tests passed!\n")

def run_comparative_benchmark(num_episodes=30):
    """Executes STEP 1.4: Comparative benchmark of Greedy Baseline vs. Hungarian Cooperative Swarm."""
    print(f"=== [BENCHMARK] Running {num_episodes} Episodes: Greedy vs. Hungarian Swarm ===")
    
    # Custom simulation runner comparing modes
    def evaluate_mode(mode_name, seed_start):
        base_survived_count = 0
        leader_survived_count = 0
        enemies_destroyed_list = []
        times_list = []
        redundant_locks_total = 0

        t0 = time.time()
        for i in range(num_episodes):
            seed = seed_start + i
            np.random.seed(seed)

            sm = SwarmManager(window=None)
            sm.allocation_mode = mode_name
            sm.create_swarm(num_loyal=10, num_kamikazes=4)

            # Track duplicate targeting in each frame
            for step in range(1200):
                sm.update([])
                
                # Check for redundant targeting across wingmen
                targeted_kamikazes = []
                for w in sm.swarm:
                    target_k = getattr(w, 'kamikaze_to_attack', None)
                    if target_k is not None:
                        targeted_kamikazes.append(id(target_k))
                
                # Duplicates in this frame
                if len(targeted_kamikazes) > len(set(targeted_kamikazes)):
                    redundant_locks_total += (len(targeted_kamikazes) - len(set(targeted_kamikazes)))

                finished, reason = sm.check_mission_status()
                if finished:
                    break

            base_alive = sm.protected_area.is_active() if sm.protected_area else False
            leader_alive = sm.leadingdrone is not None and getattr(sm.leadingdrone, 'destroyed', False) is not True
            if base_alive: base_survived_count += 1
            if leader_alive: leader_survived_count += 1
            enemies_destroyed_list.append(sm.counter_kamikazes_destroyed)
            times_list.append(step * 0.0166)

        dt = time.time() - t0
        return {
            "mode": mode_name,
            "base_survival": (base_survived_count / num_episodes) * 100,
            "leader_survival": (leader_survived_count / num_episodes) * 100,
            "mean_kills": np.mean(enemies_destroyed_list),
            "mean_time": np.mean(times_list),
            "redundant_locks": redundant_locks_total,
            "elapsed_wall_time": dt
        }

    greedy_res = evaluate_mode("greedy", seed_start=1000)
    hungarian_res = evaluate_mode("hungarian", seed_start=1000)

    print("\n" + "=" * 65)
    print(f"{'METRIC':<30} | {'GREEDY (BASELINE)':<15} | {'HUNGARIAN (COOP)':<15}")
    print("-" * 65)
    print(f"{'Base Survival Rate (%)':<30} | {greedy_res['base_survival']:<15.1f} | {hungarian_res['base_survival']:<15.1f}")
    print(f"{'Leader Survival Rate (%)':<30} | {greedy_res['leader_survival']:<15.1f} | {hungarian_res['leader_survival']:<15.1f}")
    print(f"{'Mean Enemies Destroyed':<30} | {greedy_res['mean_kills']:<15.2f} | {hungarian_res['mean_kills']:<15.2f}")
    print(f"{'Redundant Target Locks':<30} | {greedy_res['redundant_locks']:<15} | {hungarian_res['redundant_locks']:<15}")
    print(f"{'Execution Wall Time (s)':<30} | {greedy_res['elapsed_wall_time']:<15.2f} | {hungarian_res['elapsed_wall_time']:<15.2f}")
    print("=" * 65)

    if hungarian_res['redundant_locks'] < greedy_res['redundant_locks']:
        pct_reduction = ((greedy_res['redundant_locks'] - hungarian_res['redundant_locks']) / max(1, greedy_res['redundant_locks'])) * 100
        print(f"★ SUCCESS: Hungarian cooperative allocation reduced redundant target locks by {pct_reduction:.1f}%!")

if __name__ == '__main__':
    test_cost_matrix_and_uniqueness()
    run_comparative_benchmark(num_episodes=25)
