import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
# Ensure headless Pygame
os.environ['SDL_VIDEODRIVER'] = 'dummy'

import time
import random
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, Any, List
from constants import (
    NUM_DRONES, NUM_KAMIKAZES, SAMPLE_TIME,
    WORLD_WIDTH, WORLD_HEIGHT
)
from swarm_manager import SwarmManager
from experiment_manager import ExperimentManager

def run_headless_episode(chase_distance: float,
                         formation_distance: float,
                         distance_rings: float = 1.2,
                         max_steps: int = 1800,
                         num_loyal: int = NUM_DRONES,
                         num_kamikazes: int = NUM_KAMIKAZES,
                         seed: int = None) -> Dict[str, Any]:
    """
    Executes a single headless combat simulation at maximum CPU speed without GUI rendering.
    
    :param chase_distance: Threat engagement radius for wingmen
    :param formation_distance: Escort radius from leader
    :param distance_rings: Multi-ring formation spacing
    :param max_steps: Maximum simulation steps (1800 steps = 30 seconds at 60Hz)
    :param num_loyal: Number of defending wingmen
    :param num_kamikazes: Number of hostile kamikazes
    :param seed: Random seed for reproducibility
    :return: Telemetry results dictionary
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    swarm = SwarmManager(window=None)
    swarm.create_swarm(
        num_loyal=num_loyal,
        num_kamikazes=num_kamikazes,
        distance_chase=chase_distance,
        distance_formation=formation_distance,
        distance_rings_formation=distance_rings
    )

    step = 0
    end_reason = "Max Time Reached"

    for step in range(1, max_steps + 1):
        swarm.update([])
        finished, reason = swarm.check_mission_status()
        if finished:
            end_reason = reason
            break

    time_elapsed = step * SAMPLE_TIME
    enemies_destroyed = swarm.counter_kamikazes_destroyed
    loyal_survived = len(swarm.swarm)
    leader_alive = (swarm.leadingdrone is not None and getattr(swarm.leadingdrone, 'destroyed', False) is not True)
    protected_life = swarm.protected_area.life if swarm.protected_area else 0

    # PSO Fitness function
    quality = (enemies_destroyed ** 2) + 10.0 * time_elapsed - loyal_survived * 1000.0

    return {
        "chase_distance": chase_distance,
        "formation_distance": formation_distance,
        "distance_rings": distance_rings,
        "steps": step,
        "time_elapsed": time_elapsed,
        "enemies_destroyed": enemies_destroyed,
        "loyal_survived": loyal_survived,
        "leader_alive": leader_alive,
        "protected_area_life": protected_life,
        "end_reason": end_reason,
        "quality": quality
    }

def _worker_eval_particle(task_args):
    """Worker function for ProcessPoolExecutor."""
    p_idx, position, max_steps, num_drones, num_kamikazes, seed = task_args
    chase = float(position[0])
    formation = float(position[1])
    rings = float(position[2]) if len(position) > 2 else 1.2

    res = run_headless_episode(
        chase_distance=chase,
        formation_distance=formation,
        distance_rings=rings,
        max_steps=max_steps,
        num_loyal=num_drones,
        num_kamikazes=num_kamikazes,
        seed=seed
    )
    return p_idx, res

class ParallelPSOOptimizer:
    """
    Orchestrates high-speed parallel Particle Swarm Optimization (PSO)
    across all CPU cores using ProcessPoolExecutor.
    """
    def __init__(self, pso_instance, max_workers=None, csv_filename="pso_parallel_results.csv"):
        self.pso = pso_instance
        self.max_workers = max_workers
        self.csv_filename = csv_filename
        self.experiment_manager = ExperimentManager(filename=csv_filename, save_results=True)

    def optimize(self, generations: int = 50, max_steps_per_sim: int = 1800,
                 num_drones: int = NUM_DRONES, num_kamikazes: int = NUM_KAMIKAZES):
        """
        Executes parallel multi-core PSO across all generations.
        """
        num_particles = self.pso.hyperparams.num_particles
        print(f"=== Starting Parallel PSO ===")
        print(f"Generations: {generations} | Particles: {num_particles} | Workers: {self.max_workers or os.cpu_count()}")
        print(f"Total Evaluations: {generations * num_particles}")

        total_t0 = time.time()

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            for gen in range(1, generations + 1):
                gen_t0 = time.time()
                # 1. Prepare evaluation batch for the current generation
                tasks = []
                for p_idx in range(num_particles):
                    pos = self.pso.particles[p_idx].position
                    seed = gen * 1000 + p_idx
                    tasks.append((p_idx, pos, max_steps_per_sim, num_drones, num_kamikazes, seed))

                # 2. Run all particles of this generation concurrently
                results = list(executor.map(_worker_eval_particle, tasks))

                # 3. Notify PSO in original particle order
                results.sort(key=lambda x: x[0])
                gen_qualities = []
                for p_idx, res in results:
                    quality = res["quality"]
                    gen_qualities.append(quality)
                    self.pso.notify_evaluation(quality)

                    # Log to CSV
                    self.experiment_manager.record_iteration(
                        enemies_destroyed=res["enemies_destroyed"],
                        time_elapsed=res["time_elapsed"],
                        loyal_wingman_survived=res["loyal_survived"],
                        quality=quality,
                        leader_alive=res["leader_alive"],
                        protected_area_life=res["protected_area_life"],
                        end_reason=res["end_reason"],
                        distance_chase=res["chase_distance"],
                        distance_formation=res["formation_distance"]
                    )

                gen_dt = time.time() - gen_t0
                best_val = self.pso.get_best_value()
                best_pos = self.pso.get_best_position()
                print(f"Gen {gen:02d}/{generations:02d} [{gen_dt:.2f}s] | Avg Quality: {np.mean(gen_qualities):.1f} | Best Quality: {best_val:.1f} | Best Params: chase={best_pos[0]:.1f}, formation={best_pos[1]:.1f}")

        total_dt = time.time() - total_t0
        print(f"\n=== Parallel PSO Finished in {total_dt:.2f} seconds ===")
        print(f"Global Best Quality: {self.pso.get_best_value():.2f}")
        print(f"Global Best Params: {self.pso.get_best_position()}")
        print(f"Telemetry saved to: {self.csv_filename}")
