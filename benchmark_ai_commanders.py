"""
Automated Headless Benchmark Suite for MUM-T Autonomous Air Defense Controllers.
Compares:
1. Baseline: Static Heuristic Swarm (Circle formation, default PSO)
2. Laya: Convai Laya System-1 non-autoregressive decision model (~24ms on MPS)
3. Qwen: Qwen 3.5 9B System-2 generative SLM (via LM Studio)

Supports:
- Lockstep mode (--mode lockstep): Synchronous virtual-time evaluation for reproducible, fair comparison.
- Realtime mode (--mode realtime): Wall-clock paced evaluation testing asynchronous reaction lag.
"""

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
os.environ['SDL_VIDEODRIVER'] = 'dummy'

import sys
import time
import math
import argparse
import random
import numpy as np
from typing import Dict, Any, List
from dataclasses import dataclass, asdict

import pygame as pg
from constants import (
    NUM_DRONES, NUM_KAMIKAZES, SAMPLE_TIME,
    WORLD_WIDTH, WORLD_HEIGHT
)
from swarm_manager import SwarmManager
from llm_commander import LLMTacticalCommander


class MockDisplayWindow:
    """Headless dummy display surface for SwarmManager."""
    def __init__(self, w=1600, h=900):
        self.screen_width = w
        self.screen_height = h
        self.zoom_level = 1.0
        self.offset = pg.math.Vector2(0, 0)
        self.screen = pg.Surface((w, h))
        self.world_surface = self.screen

    def screen_to_world(self, pos):
        return pg.math.Vector2(pos[0], pos[1])


class HeadlessSimulationContext:
    """Lightweight simulation adapter for LLMTacticalCommander in headless mode."""
    def __init__(self, swarm_manager: SwarmManager):
        self.swarm_manager = swarm_manager
        self.leadingdrone = swarm_manager.leadingdrone
        self.protected_area = swarm_manager.protected_area
        self.swarm = swarm_manager.swarm
        self.kamikazes = swarm_manager.kamikazes


def run_single_episode(engine: str = "baseline",
                       mode: str = "lockstep",
                       speed_factor: float = 1.0,
                       max_steps: int = 1800,
                       max_decisions: int = None,
                       continuous_waves: bool = False,
                       decision_interval_sec: float = 1.0,
                       num_wingmen: int = NUM_DRONES,
                       num_kamikazes: int = NUM_KAMIKAZES,
                       seed: int = None) -> Dict[str, Any]:
    """
    Executes a single headless combat episode with the selected tactical commander.
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    pg.init()
    if pg.display.get_surface() is None:
        pg.display.set_mode((1, 1))

    surface = pg.Surface((1600, 900))
    sm = SwarmManager(window=surface)
    sm.create_swarm(
        num_loyal=num_wingmen,
        num_kamikazes=num_kamikazes,
        distance_chase=300.0,
        distance_formation=100.0,
        distance_rings_formation=1.2
    )

    sim_ctx = HeadlessSimulationContext(sm)

    commander: LLMTacticalCommander = None
    if engine in ("laya", "qwen"):
        commander = LLMTacticalCommander(engine=engine, decision_interval=decision_interval_sec)
        commander.enabled = True

    step = 0
    end_reason = "Limit Reached"
    latencies = []
    formation_counts = {"CIRCLE": 0, "WALL": 0, "WEDGE": 0, "ECHELON": 0}
    decisions_count = 0
    total_waves_spawned = 1

    t_start = time.perf_counter()

    while step < max_steps:
        step += 1
        sim_time = step * SAMPLE_TIME
        sm.simulation_time = sim_time

        # If continuous waves enabled and current threats are eliminated, spawn next wave
        if continuous_waves and len(sm.kamikazes) == 0:
            for _ in range(num_kamikazes):
                sm.create_kamikaze()
            total_waves_spawned += 1

        # Check if decision quota reached
        if max_decisions is not None and decisions_count >= max_decisions:
            end_reason = f"Max Decisions Reached ({max_decisions})"
            break

        # Update tactical commander
        if commander is not None:
            if mode == "lockstep":
                # In lockstep mode, query synchronously at the exact simulated decision interval
                if (sim_time - commander.last_decision_time >= decision_interval_sec) and len(sm.kamikazes) > 0:
                    commander.last_decision_time = sim_time
                    snapshot = commander.build_telemetry_snapshot(sim_ctx)
                    
                    t_inf_0 = time.perf_counter()
                    if engine == "laya":
                        commander._async_query_laya(snapshot)
                    else:
                        commander._async_query_llm(snapshot)
                    t_inf_1 = time.perf_counter()
                    
                    inf_ms = (t_inf_1 - t_inf_0) * 1000.0
                    latencies.append(inf_ms)
                    decisions_count += 1
                    
                    # Apply decision immediately to the physics loop
                    if commander._pending_decision is not None:
                        form = commander._pending_decision.get("selected_formation", "CIRCLE")
                        if form in formation_counts:
                            formation_counts[form] += 1
                        commander._apply_decision(commander._pending_decision, sim_ctx)
                        commander._pending_decision = None
            else:
                # Realtime asynchronous mode: ticks worker threads
                commander.update(sim_time, sim_ctx)
                if speed_factor > 0:
                    target_wall_time = sim_time / speed_factor
                    elapsed_wall = time.perf_counter() - t_start
                    delay = target_wall_time - elapsed_wall
                    if delay > 0.001:
                        time.sleep(delay)

        # Advance physics
        sm.update([])

        # Check terminal conditions
        if sm.leadingdrone is not None and getattr(sm.leadingdrone, 'destroyed', False) is True:
            end_reason = "Leader Destroyed"
            break
        if sm.protected_area is not None and not sm.protected_area.is_active():
            end_reason = "Base Destroyed"
            break
        if len(sm.swarm) < 1:
            end_reason = "All Loyal Destroyed"
            break
        if not continuous_waves and len(sm.kamikazes) == 0:
            end_reason = "All Threats Neutralized"
            break

    wall_duration = time.perf_counter() - t_start
    enemies_destroyed = sm.counter_kamikazes_destroyed
    loyal_survived = len(sm.swarm)
    leader_alive = (sm.leadingdrone is not None and getattr(sm.leadingdrone, 'destroyed', False) is not True)
    base_life = sm.protected_area.life if sm.protected_area else 0.0
    victory = (base_life > 0 and leader_alive and (enemies_destroyed >= num_kamikazes))

    avg_lat = float(np.mean(latencies)) if latencies else 0.0
    p95_lat = float(np.percentile(latencies, 95)) if latencies else 0.0

    return {
        "engine": engine,
        "mode": mode,
        "seed": seed,
        "victory": victory,
        "base_life": base_life,
        "leader_alive": leader_alive,
        "enemies_destroyed": enemies_destroyed,
        "total_threats": num_kamikazes * total_waves_spawned if continuous_waves else num_kamikazes,
        "loyal_survived": loyal_survived,
        "initial_loyal": num_wingmen,
        "sim_time": step * SAMPLE_TIME,
        "wall_time": wall_duration,
        "steps": step,
        "end_reason": end_reason,
        "decisions_count": decisions_count,
        "avg_latency_ms": avg_lat,
        "p95_latency_ms": p95_lat,
        "formations": formation_counts
    }


def run_benchmark_suite(engines: List[str] = ["baseline", "laya"],
                        episodes_per_engine: int = 5,
                        mode: str = "lockstep",
                        max_steps: int = 1800,
                        max_decisions: int = None,
                        continuous_waves: bool = False,
                        num_wingmen: int = 4,
                        num_kamikazes: int = 4,
                        csv_output: str = "benchmark_results.csv") -> List[Dict[str, Any]]:
    """
    Executes multiple comparative evaluation episodes across candidate engines.
    """
    import csv
    print(f"\n================================================================================")
    print(f"  MUM-T TACTICAL CONTROLLER BENCHMARK SUITE")
    print(f"  Engines: {', '.join(engines).upper()} | Mode: {mode.upper()} | Iterations: {episodes_per_engine}")
    if max_decisions:
        print(f"  Quota: {max_decisions} Decisions per episode (Continuous Waves: {continuous_waves})")
    print(f"  Forces: {num_wingmen} Loyal Wingmen vs {num_kamikazes} Kamikaze Hostiles")
    print(f"================================================================================\n")

    results = []

    for eng in engines:
        print(f">> Starting evaluation for Engine: [{eng.upper()}] ...")
        eng_episodes = []
        for ep in range(1, episodes_per_engine + 1):
            seed = 42 + ep * 10
            t0 = time.time()
            data = run_single_episode(
                engine=eng,
                mode=mode,
                max_steps=max_steps,
                max_decisions=max_decisions,
                continuous_waves=continuous_waves,
                num_wingmen=num_wingmen,
                num_kamikazes=num_kamikazes,
                seed=seed
            )
            data["iteration"] = ep
            eng_episodes.append(data)
            results.append(data)

            stat_icon = "WIN" if data["victory"] else "LOSS"
            print(f"   Iter {ep:03d}/{episodes_per_engine:03d} | [{stat_icon}] Base HP: {data['base_life']:3.0f}% | "
                  f"KIA: {data['enemies_destroyed']}/{data['total_threats']} | Decisions: {data['decisions_count']} | "
                  f"Latency: {data['avg_latency_ms']:5.1f}ms | Reason: {data['end_reason']}")

        # Summary for this engine
        wins = sum(1 for d in eng_episodes if d["victory"])
        avg_hp = np.mean([d["base_life"] for d in eng_episodes])
        std_hp = np.std([d["base_life"] for d in eng_episodes])
        avg_kia = np.mean([d["enemies_destroyed"] for d in eng_episodes])
        avg_surv = np.mean([d["loyal_survived"] for d in eng_episodes])
        avg_lat = np.mean([d["avg_latency_ms"] for d in eng_episodes if d["avg_latency_ms"] > 0] or [0])
        print(f"   => [{eng.upper()}] Win Rate: {wins/episodes_per_engine*100:.1f}% | Base HP: {avg_hp:.1f}±{std_hp:.1f}% | "
              f"Mean KIA: {avg_kia:.1f} | Avg Latency: {avg_lat:.1f}ms\n")

    # Save to CSV
    if csv_output and results:
        fieldnames = ["iteration", "engine", "mode", "victory", "base_life", "leader_alive",
                      "enemies_destroyed", "total_threats", "loyal_survived", "decisions_count",
                      "avg_latency_ms", "sim_time", "wall_time", "end_reason", "seed"]
        with open(csv_output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in results:
                writer.writerow(r)
        print(f"✓ Saved per-iteration benchmark metrics to {csv_output}\n")

    return results


def print_comparative_table(results: List[Dict[str, Any]]):
    """Prints a structured ASCII comparison table summarizing benchmark results."""
    engines = list(dict.fromkeys(r["engine"] for r in results))

    print("=" * 88)
    print(f"{'ENGINE':<12} | {'WIN RATE':<10} | {'BASE HP (MEAN±STD)':<20} | {'THREATS KIA':<12} | {'LATENCY':<12}")
    print("=" * 88)

    for eng in engines:
        group = [r for r in results if r["engine"] == eng]
        n = len(group)
        win_rate = sum(1 for r in group if r["victory"]) / n * 100
        mean_hp = np.mean([r["base_life"] for r in group])
        std_hp = np.std([r["base_life"] for r in group])
        mean_kia = np.mean([r["enemies_destroyed"] for r in group])
        mean_surv = np.mean([r["loyal_survived"] for r in group])
        lat_vals = [r["avg_latency_ms"] for r in group if r["avg_latency_ms"] > 0]
        mean_lat = np.mean(lat_vals) if lat_vals else 0.0

        print(f"{eng.upper():<12} | {win_rate:6.1f}%    | {mean_hp:5.1f}% ± {std_hp:4.1f}%     | "
              f"{mean_kia:5.1f} KIA     | {mean_lat:6.1f} ms")
    print("=" * 88 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Headless Benchmark Suite for AI Swarm Commanders")
    parser.add_argument("--engines", nargs="+", default=["baseline", "laya"], choices=["baseline", "laya", "qwen"],
                        help="List of engines to evaluate")
    parser.add_argument("--iterations", "-i", "--episodes", type=int, default=10, dest="iterations",
                        help="Number of evaluation iterations/episodes (e.g. 10, 50, 100)")
    parser.add_argument("--mode", type=str, default="lockstep", choices=["lockstep", "realtime"],
                        help="Evaluation mode (lockstep: virtual-time synchronized; realtime: wall-clock paced)")
    parser.add_argument("--duration-sec", type=float, default=30.0,
                        help="Maximum combat duration per iteration in simulated seconds (default: 30s)")
    parser.add_argument("--max-decisions", type=int, default=None,
                        help="Optional limit on decisions per iteration (e.g. 100)")
    parser.add_argument("--continuous-waves", action="store_true",
                        help="Continuously spawn new threat waves as previous ones are neutralized")
    parser.add_argument("--wingmen", type=int, default=4, help="Number of Loyal Wingmen UAVs")
    parser.add_argument("--kamikazes", type=int, default=4, help="Number of Kamikaze hostiles")
    parser.add_argument("--speed-factor", type=float, default=2.0, help="Wall-clock acceleration factor (for realtime mode)")
    parser.add_argument("--csv", type=str, default="benchmark_results.csv", help="CSV export destination")

    args = parser.parse_args()

    max_steps = int(args.duration_sec / SAMPLE_TIME)

    results = run_benchmark_suite(
        engines=args.engines,
        episodes_per_engine=args.iterations,
        mode=args.mode,
        max_steps=max_steps,
        max_decisions=args.max_decisions,
        continuous_waves=args.continuous_waves,
        num_wingmen=args.wingmen,
        num_kamikazes=args.kamikazes,
        csv_output=args.csv
    )

    print_comparative_table(results)
