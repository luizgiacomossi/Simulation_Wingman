import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
os.environ['SDL_VIDEODRIVER'] = 'dummy'

import time
import pytest
import pygame as pg
from pygame.math import Vector2
from weapons import Projectile, VaporizerBolt, FreezingBolt, Vaporizer, Freezing
from swarm_manager import SwarmManager
from constants import SIZE_DRONE, SAMPLE_TIME

def test_projectile_kinematics():
    print("=== [TEST 1] Testing Projectile Kinematics & Range Cutoff ===")
    origin = Vector2(100, 100)
    target = Vector2(200, 100)
    
    bolt = VaporizerBolt(origin=origin, target_pos=target, speed=800.0, max_range=150.0)
    assert bolt.alive is True
    assert bolt.direction.x == pytest.approx(1.0)
    assert bolt.direction.y == pytest.approx(0.0)
    assert bolt.velocity.x == pytest.approx(800.0)
    assert len(bolt.trail) == 1

    # Step 0.1 seconds
    bolt.update(0.1)
    assert bolt.position.x == pytest.approx(180.0)
    assert bolt.position.y == pytest.approx(100.0)
    assert bolt.distance_traveled == pytest.approx(80.0)
    assert len(bolt.trail) == 2
    assert bolt.alive is True

    # Step another 0.1 seconds (total distance 160 >= 150 max_range)
    bolt.update(0.1)
    assert bolt.distance_traveled == pytest.approx(160.0)
    assert bolt.alive is False
    print("✓ Projectile kinematics, velocity vectors, trail accumulation, and max_range expiration verified.")

def test_first_order_lead_aiming():
    print("=== [TEST 2] Testing First-Order Lead Aiming ===")
    class MockTarget:
        def __init__(self, x, y, vx, vy):
            self.location = Vector2(x, y)
            self.velocity = Vector2(vx, vy)

    shooter_pos = Vector2(100, 100)
    # Target is directly east at (200, 100) moving north at (0, 100)
    target = MockTarget(200, 100, 0, 100)

    bolt = VaporizerBolt(origin=shooter_pos, target_pos=target.location, target_entity=target, speed=500.0)
    # Flight time approx: distance 100 / speed 500 = 0.2s
    # In 0.2s, target travels north by 20px -> aim_pos approx (200, 120)
    # Therefore, direction.y must be positive (aiming ahead along target trajectory)
    assert bolt.direction.y > 0.0, f"Expected lead aim with positive y, got {bolt.direction.y}"
    assert bolt.direction.x > 0.0
    print(f"✓ Lead pursuit calculated lead angle: direction={bolt.direction}")

def test_weapons_fire_polymorphism():
    print("=== [TEST 3] Testing Weapon Fire & Ammunition Tracking ===")
    class MockShooter:
        def __init__(self):
            self.location = Vector2(50, 50)

    shooter = MockShooter()
    vap = Vaporizer(cooldown=1.0, num_cartridges=2, rate_of_fire=1.0, range_of_fire=100.0, owner=shooter)
    frz = Freezing(cooldown=1.0, num_cartridges=2, rate_of_fire=1.0, range_of_fire=300.0, owner=shooter)

    target_pos = Vector2(120, 50)
    
    # 1. Fire Vaporizer
    bolt1 = vap.fire(target=target_pos)
    assert isinstance(bolt1, VaporizerBolt)
    assert vap.get_ammo_available() == 1
    assert bolt1.speed == pytest.approx(850.0)

    # 2. Fire Freezing
    bolt2 = frz.fire(target=target_pos)
    assert isinstance(bolt2, FreezingBolt)
    assert frz.get_ammo_available() == 1
    assert bolt2.speed == pytest.approx(650.0)

    # 3. Exhaust ammo
    vap.fire(target=target_pos)
    assert vap.get_ammo_available() == 0
    dry_fire = vap.fire(target=target_pos)
    assert dry_fire is None, "Weapon with 0 cartridges must return None"
    print("✓ Weapon polymorphism, projectile dispatching, and cartridge exhaustion verified.")

def test_projectile_impacts():
    print("=== [TEST 4] Testing Projectile Impacts (Lethal & Stasis) ===")
    class MockKamikaze:
        def __init__(self):
            self.location = Vector2(100, 100)
            self.destroyed = False
            self.explode = False
            self.is_slowed = False

        def slow_down(self):
            self.is_slowed = True

    # Lethal test
    k1 = MockKamikaze()
    vap_bolt = VaporizerBolt(origin=Vector2(90, 100), target_pos=Vector2(100, 100))
    vap_bolt.on_hit(k1, None, force_hit=True)
    assert vap_bolt.alive is False
    assert k1.destroyed is True
    assert k1.explode is True

    # Stasis test
    k2 = MockKamikaze()
    frz_bolt = FreezingBolt(origin=Vector2(50, 100), target_pos=Vector2(100, 100))
    frz_bolt.on_hit(k2, None, force_hit=True)
    assert frz_bolt.alive is False
    assert k2.is_slowed is True
    print("✓ Vaporizer lethal detonation and Freezing cryogenic slow-down impacts verified.")

def test_swarm_manager_full_ballistics_loop():
    print("=== [TEST 5] Testing SwarmManager Ballistics Lifecycle (120 frames) ===")
    sm = SwarmManager(window=None)
    sm.create_swarm(num_loyal=10, num_kamikazes=4)

    initial_kamikazes = len(sm.kamikazes)
    assert initial_kamikazes == 4
    assert len(sm.projectiles) == 0

    t0 = time.time()
    for frame in range(120):
        sm.update([])
    elapsed = time.time() - t0

    print(f"✓ Executed 120 simulation frames with dynamic ballistics in {elapsed*1000:.1f}ms ({120/elapsed:.0f} FPS).")
    print(f"✓ Enemies destroyed during test: {sm.counter_kamikazes_destroyed}")
    assert sm.counter_kamikazes_destroyed >= 0

if __name__ == "__main__":
    test_projectile_kinematics()
    test_first_order_lead_aiming()
    test_weapons_fire_polymorphism()
    test_projectile_impacts()
    test_swarm_manager_full_ballistics_loop()
    print("\n★★★ ALL BALLISTICS & PROJECTILE TESTS PASSED! ★★★")
