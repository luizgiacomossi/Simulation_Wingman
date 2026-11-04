import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
os.environ['SDL_VIDEODRIVER'] = 'dummy'

import time
import pytest
import numpy as np
import pygame as pg
from pygame.math import Vector2
from formation import (
    FormationManager, CircleFormation, WedgeFormation,
    WallFormation, EchelonFormation
)
from swarm_manager import SwarmManager
from constants import SIZE_DRONE, AVOID_DISTANCE

def test_analytical_geometries():
    print("=== [TEST 1] Testing Analytical Formation Geometries ===")
    leader_pos = Vector2(500, 500)
    heading_east = 0.0  # Facing East along +X axis
    spacing = 100.0
    num_drones = 6

    # 1. Circle Formation
    circle = CircleFormation()
    c_slots = circle.compute_slots(leader_pos, heading_east, num_drones, spacing)
    assert len(c_slots) == 6
    for s in c_slots:
        dist = (s - leader_pos).length()
        assert dist == pytest.approx(spacing, rel=1e-3)
    print("✓ CircleFormation: All slots are strictly equidistant from leader center.")

    # 2. Wedge Formation
    wedge = WedgeFormation(sweep_angle_deg=45.0)
    w_slots = wedge.compute_slots(leader_pos, heading_east, num_drones, spacing)
    assert len(w_slots) == 6
    # When facing East, wingmen must be behind leader (X < 500)
    for s in w_slots:
        assert s.x < leader_pos.x
    # Right and left wings must be symmetric along Y axis
    y_offsets = [s.y - leader_pos.y for s in w_slots]
    assert pytest.approx(sum(y_offsets), abs=1e-3) == 0.0
    print("✓ WedgeFormation: Symmetrical 45° swept-back V-escort trailing behind leader.")

    # 3. Wall Formation
    wall = WallFormation(setback_distance=50.0)
    wall_slots = wall.compute_slots(leader_pos, heading_east, num_drones, spacing)
    assert len(wall_slots) == 6
    # When facing East, wall is perpendicular (aligned along Y axis at X = 500 - 50 = 450)
    for s in wall_slots:
        assert s.x == pytest.approx(450.0, rel=1e-3)
    print("✓ WallFormation: Linear defensive barrier strictly perpendicular to heading.")

    # 4. Echelon Formation
    echelon = EchelonFormation(side="RIGHT", angle_deg=45.0)
    e_slots = echelon.compute_slots(leader_pos, heading_east, num_drones, spacing)
    assert len(e_slots) == 6
    for i, s in enumerate(e_slots, start=1):
        assert s.x < leader_pos.x  # Trailing
        assert s.y > leader_pos.y  # Stepped to the right flank
    print("✓ EchelonFormation: Stepped diagonal column protecting leader's flank.")

def test_formation_manager_and_strategy_switching():
    print("=== [TEST 2] Testing FormationManager & Strategy Switching ===")
    fm = FormationManager(default_strategy="CIRCLE")
    assert fm.active_strategy_name == "CIRCLE"
    assert isinstance(fm.current_strategy, CircleFormation)

    assert fm.set_strategy("WEDGE") is True
    assert fm.active_strategy_name == "WEDGE"
    assert isinstance(fm.current_strategy, WedgeFormation)

    assert fm.set_strategy("WALL") is True
    assert fm.active_strategy_name == "WALL"

    assert fm.set_strategy("ECHELON") is True
    assert fm.active_strategy_name == "ECHELON"

    # Invalid strategy rejection
    assert fm.set_strategy("INVALID_FORM") is False
    assert fm.active_strategy_name == "ECHELON"
    print("✓ FormationManager: Dynamic strategy dispatch and robust error handling verified.")

def test_hungarian_optimal_slot_assignment():
    print("=== [TEST 3] Testing Hungarian Optimal Slot Assignment ===")
    fm = FormationManager()

    class MockWingman:
        def __init__(self, x, y, name):
            self.location = Vector2(x, y)
            self.agent_id = name

    wingmen = [
        MockWingman(100, 100, "W0"),
        MockWingman(100, 200, "W1"),
        MockWingman(300, 100, "W2"),
        MockWingman(300, 200, "W3")
    ]

    slots = [
        Vector2(105, 102),  # Closest to W0
        Vector2(102, 198),  # Closest to W1
        Vector2(295, 105),  # Closest to W2
        Vector2(305, 205)   # Closest to W3
    ]

    assignments = fm.assign_optimal_slots(wingmen, slots)
    assert len(assignments) == 4
    # Unique 1-to-1 matching
    assert assignments["W0"] == slots[0]
    assert assignments["W1"] == slots[1]
    assert assignments["W2"] == slots[2]
    assert assignments["W3"] == slots[3]
    print("✓ Hungarian Slot Matching minimizes total displacement and eliminates trajectory crossing.")

def test_rapid_reformation_anti_collision_simulation():
    print("=== [TEST 4] Testing Rapid Re-Formation Anti-Collision (300 frames) ===")
    sm = SwarmManager(window=None)
    sm.create_swarm(num_loyal=8, num_kamikazes=0)  # Pure escort test

    # Allow initial frames to launch into formation
    for _ in range(30):
        sm.update([])

    formations = ["CIRCLE", "WEDGE", "WALL", "ECHELON"]
    t0 = time.time()

    min_recorded_distance = float('inf')

    for frame in range(300):
        # Switch formation every 50 frames
        if frame % 50 == 0:
            target_form = formations[(frame // 50) % len(formations)]
            sm.set_formation_strategy(target_form)
            assert sm.leadingdrone.current_formation_name == target_form

        sm.update([])

        # Check inter-wingman distances
        for i in range(len(sm.swarm)):
            for j in range(i + 1, len(sm.swarm)):
                dist = (sm.swarm[i].location - sm.swarm[j].location).length()
                if dist < min_recorded_distance:
                    min_recorded_distance = dist

    elapsed = time.time() - t0
    print(f"✓ 300 frames executed with 6 tactical re-formations in {elapsed*1000:.1f}ms ({300/elapsed:.0f} FPS).")
    print(f"✓ Minimum recorded wingman separation during transitions: {min_recorded_distance:.1f}px (Collision threshold: {AVOID_DISTANCE}px).")
    assert min_recorded_distance >= AVOID_DISTANCE, f"Separation dropped below collision avoidance distance: {min_recorded_distance:.1f}px < {AVOID_DISTANCE}px"
    print("✓ Zero mid-air collisions occurred during aggressive tactical re-formations.")

def test_dynamic_formation_guide_rendering():
    print("=== [TEST 5] Testing Dynamic Formation Guide Rendering ===")
    pg.init()
    surface = pg.Surface((1200, 900))

    sm = SwarmManager()
    sm.create_swarm(num_loyal=6, num_kamikazes=0, distance_formation=100)

    for form_name in ["CIRCLE", "WEDGE", "WALL", "ECHELON"]:
        ok = sm.set_formation_strategy(form_name)
        assert ok is True
        assert sm.leadingdrone.current_formation_name == form_name

        # Ensure draw_formation_guide executes cleanly onto surface
        sm.leadingdrone.draw_formation_guide(surface, num_drones=len(sm.swarm))

        # Ensure full swarm draw renders the dynamic formation guide
        sm.draw(surface)

    print("✓ Dynamic formation guide rendering verified across all 4 tactical formations.")

if __name__ == "__main__":
    test_analytical_geometries()
    test_formation_manager_and_strategy_switching()
    test_hungarian_optimal_slot_assignment()
    test_rapid_reformation_anti_collision_simulation()
    test_dynamic_formation_guide_rendering()
    print("\n★★★ ALL FORMATION ENGINE & ANTI-COLLISION TESTS PASSED! ★★★")
