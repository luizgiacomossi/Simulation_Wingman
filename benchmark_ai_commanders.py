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
    end_reason = "Time Limit Reached"
    latencies = []
    formation_counts = {"CIRCLE": 0, "WALL": 0, "WEDGE": 0, "ECHELON": 0}
    decisions_count = 0

    t_start = time.perf_counter()

    for step in range(1, max_steps + 1):
        sim_time = step * SAMPLE_TIME
        sm.simulation_time = sim_time

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
                    # Enforce wall-clock pacing according to speed_factor
                    target_wall_time = sim_time / speed_factor
                    elapsed_wall = time.perf_counter() - t_start
                    delay = target_wall_time - elapsed_wall
                    if delay > 0.001:
                        time.sleep(delay)

        # Advance physics
        sm.update([])

        # Check termination condition
        finished, reason = sm.check_mission_status()
        if finished:
            end_reason = reason
            break

    wall_duration = time.perf_counter() - t_start
    enemies_destroyed = sm.counter_kamikazes_destroyed
    loyal_survived = len(sm.swarm)
    leader_alive = (sm.leadingdrone is not None and getattr(sm.leadingdrone, 'destroyed', False) is not True)
    base_life = sm.protected_area.life if sm.protected_area else 0.0
    victory = (base_life > 0 and enemies_destroyed == num_kamikazes and leader_alive)

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
        "total_threats": num_kamikazes,
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
                        num_wingmen: int = 4,
                        num_kamikazes: int = 4) -> List[Dict[str, Any]]:
    """
    Executes multiple comparative evaluation episodes across candidate engines.
    """
    print(f"\n================================================================================")
    print(f"  MUM-T TACTICAL CONTROLLER BENCHMARK SUITE")
    print(f"  Engines: {', '.join(engines).upper()} | Mode: {mode.upper()} | Episodes: {episodes_per_engine}")
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
                num_wingmen=num_wingmen,
                num_kamikazes=num_kamikazes,
                seed=seed
            )
            eng_episodes.append(data)
            results.append(data)

            stat_icon = "WIN" if data["victory"] else "LOSS"
            print(f"   Episode {ep:02d}/{episodes_per_engine:02d} | [{stat_icon}] Base HP: {data['base_life']:3.0f}% | "
                  f"KIA: {data['enemies_destroyed']}/{num_kamikazes} | Wingmen: {data['loyal_survived']}/{num_wingmen} | "
                  f"Latency: {data['avg_latency_ms']:5.1f}ms | Reason: {data['end_reason']}")

        # Summary for this engine
        wins = sum(1 for d in eng_episodes if d["victory"])
        avg_hp = np.mean([d["base_life"] for d in eng_episodes])
        avg_kia = np.mean([d["enemies_destroyed"] for d in eng_episodes])
        avg_surv = np.mean([d["loyal_survived"] for d in eng_episodes])
        avg_lat = np.mean([d["avg_latency_ms"] for d in eng_episodes if d["avg_latency_ms"] > 0] or [0])
        print(f"   => [{eng.upper()}] Win Rate: {wins/episodes_per_engine*100:.1f}% | Mean Base HP: {avg_hp:.1f}% | "
              f"Mean Threats Killed: {avg_kia:.1f}/{num_kamikazes} | Avg Latency: {avg_lat:.1f}ms\n")

    return results


def print_comparative_table(results: List[Dict[str, Any]]):
    """Prints a structured ASCII comparison table summarizing benchmark results."""
    engines = list(dict.fromkeys(r["engine"] for r in results))

    print("=" * 86)
    print(f"{'ENGINE':<12} | {'WIN RATE':<10} | {'BASE HP':<10} | {'THREATS KIA':<12} | {'WINGMEN SURV':<12} | {'LATENCY (MS)':<12}")
    print("=" * 86)

    for eng in engines:
        group = [r for r in results if r["engine"] == eng]
        n = len(group)
        win_rate = sum(1 for r in group if r["victory"]) / n * 100
        mean_hp = np.mean([r["base_life"] for r in group])
        mean_kia = np.mean([r["enemies_destroyed"] for r in group])
        mean_surv = np.mean([r["loyal_survived"] for r in group])
        lat_vals = [r["avg_latency_ms"] for r in group if r["avg_latency_ms"] > 0]
        mean_lat = np.mean(lat_vals) if lat_vals else 0.0

        print(f"{eng.upper():<12} | {win_rate:6.1f}%    | {mean_hp:6.1f}%    | {mean_kia:5.1f} / {group[0]['total_threats']:<4} | "
              f"{mean_surv:5.1f} / {group[0]['initial_loyal']:<4} | {mean_lat:6.1f} ms")
    print("=" * 86 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Headless Benchmark Suite for AI Swarm Commanders")
    parser.add_argument("--engines", nargs="+", default=["baseline", "laya"], choices=["baseline", "laya", "qwen"],
                        help="List of engines to evaluate")
    parser.add_argument("--episodes", type=int, default=3, help="Number of evaluation episodes per engine")
    parser.add_argument("--mode", type=str, default="lockstep", choices=["lockstep", "realtime"],
                        help="Evaluation mode (lockstep: virtual-time synchronized; realtime: wall-clock paced)")
    parser.add_argument("--wingmen", type=int, default=4, help="Number of Loyal Wingmen UAVs")
    parser.add_argument("--kamikazes", type=int, default=4, help="Number of Kamikaze hostiles")
    parser.add_argument("--speed-factor", type=float, default=2.0, help="Wall-clock acceleration factor (for realtime mode)")

    args = parser.parse_args()

    results = run_benchmark_suite(
        engines=args.engines,
        episodes_per_engine=args.episodes,
        mode=args.mode,
        num_wingmen=args.wingmen,
        num_kamikazes=args.kamikazes
    )

    print_comparative_table(results)
