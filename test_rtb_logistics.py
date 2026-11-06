import pytest
import pygame as pg
from decision_making import ReturnToBaseNode, SacrificialRammingNode, LoyalWingmanBehaviorTree
from behavior_tree import ExecutionStatus
from animation import ProtectedArea
from weapons import Vaporizer, Freezing

vec2 = pg.math.Vector2


class MockGun:
    def __init__(self, ammo=10, max_ammo=10):
        self.ammo = ammo
        self.max_cartridges = max_ammo
        self.available = True

    def get_ammo_available(self):
        return self.ammo

    def rearm(self, amount=None):
        self.ammo = amount if amount is not None else self.max_cartridges
        self.available = True


class MockKamikaze:
    def __init__(self, x, y, vx=0.0, vy=0.0):
        self.location = vec2(x, y)
        self.velocity = vec2(vx, vy)
        self.destroyed = False
        self.explode = False


class MockLeader:
    def __init__(self, x, y):
        self.location = vec2(x, y)
        self.destroyed = False


class MockWingman:
    def __init__(self, x, y, vap_ammo=10, frz_ammo=10, enable_rtb=False):
        self.location = vec2(x, y)
        self.velocity = vec2(0.1, 0)
        self.acceleration = vec2(0, 0)
        self.max_speed = 3.0
        self.max_force = 0.5
        self.vaporizer_gun = MockGun(vap_ammo, 10)
        self.freezing_gun = MockGun(frz_ammo, 10)
        self.kamikazes = []
        self.leader = MockLeader(500, 500)
        self.protected_area = ProtectedArea(radius=150, coordenates=vec2(1000, 500))
        self.enable_rtb = enable_rtb
        self.is_rtb = False
        self.rtb_status = ""
        self.is_rearming = False
        self.rtb_progress = 0.0
        self.is_sacrificing = False
        self.sacrificial_target = None
        self.last_arrived_target = None

    def arrive(self, target):
        self.last_arrived_target = target

    def seek(self, target):
        pass


def test_rtb_disabled_by_default_preserves_legacy():
    """When enable_rtb is False, node immediately fails, preserving legacy baseline."""
    node = ReturnToBaseNode(rearm_duration=2.0)
    drone = MockWingman(500, 500, vap_ammo=0, frz_ammo=0, enable_rtb=False)

    status = node.execute(drone)
    assert status == ExecutionStatus.FAILURE
    assert drone.is_rtb is False


def test_rtb_inhibits_when_armed():
    """When drone still has ammo, RTB does not trigger."""
    node = ReturnToBaseNode(rearm_duration=2.0)
    drone = MockWingman(500, 500, vap_ammo=4, frz_ammo=0, enable_rtb=True)

    status = node.execute(drone)
    assert status == ExecutionStatus.FAILURE
    assert drone.is_rtb is False


def test_rtb_transit_inbound_when_far_from_base():
    """When out of ammo and far from base, steers toward base with RTB INBOUND."""
    node = ReturnToBaseNode(rearm_duration=2.0)
    drone = MockWingman(200, 500, vap_ammo=0, frz_ammo=0, enable_rtb=True)

    status = node.execute(drone)
    assert status == ExecutionStatus.RUNNING
    assert drone.is_rtb is True
    assert drone.is_rearming is False
    assert drone.rtb_status == "RTB INBOUND"
    assert drone.last_arrived_target == drone.protected_area.coordenates


def test_rtb_rearming_and_replenishment():
    """Inside base, rearming timer increments and fully restocks ammo upon completion."""
    duration = 0.1  # Fast for unit test
    node = ReturnToBaseNode(rearm_duration=duration)
    # Base is at (1000, 500) with radius 150. Place drone at (1010, 500) inside base.
    drone = MockWingman(1010, 500, vap_ammo=0, frz_ammo=0, enable_rtb=True)

    # 1. First tick: should be rearming
    status = node.execute(drone)
    assert status == ExecutionStatus.RUNNING
    assert drone.is_rtb is True
    assert drone.is_rearming is True
    assert "REARMING" in drone.rtb_status
    assert drone.rtb_progress > 0.0

    # 2. Simulate ticks until timer elapses
    for _ in range(15):
        status = node.execute(drone)
        if status == ExecutionStatus.SUCCESS:
            break

    assert status == ExecutionStatus.SUCCESS
    assert drone.rtb_status == "REARMED"
    assert drone.vaporizer_gun.get_ammo_available() == 10
    assert drone.freezing_gun.get_ammo_available() == 10
