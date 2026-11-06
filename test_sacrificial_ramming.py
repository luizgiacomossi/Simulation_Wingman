import pytest
import pygame as pg
from decision_making import SacrificialRammingNode, LoyalWingmanBehaviorTree
from behavior_tree import ExecutionStatus
from animation import ProtectedArea

vec2 = pg.math.Vector2


class MockGun:
    def __init__(self, ammo=10):
        self.ammo = ammo

    def get_ammo_available(self):
        return self.ammo


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
    def __init__(self, x, y, vap_ammo=10, frz_ammo=10):
        self.location = vec2(x, y)
        self.velocity = vec2(0, 0)
        self.acceleration = vec2(0, 0)
        self.max_speed = 3.0
        self.max_force = 0.5
        self.vaporizer_gun = MockGun(vap_ammo)
        self.freezing_gun = MockGun(frz_ammo)
        self.kamikazes = []
        self.leader = MockLeader(500, 500)
        self.protected_area = ProtectedArea(radius=150, coordenates=vec2(1000, 500))
        self.is_sacrificing = False
        self.sacrificial_target = None
        self.last_steered_target = None

    def seek(self, target):
        self.last_steered_target = target


def test_sacrificial_node_inhibits_when_armed():
    """Wingman with ammunition must NEVER sacrifice itself."""
    node = SacrificialRammingNode(critical_radius_leader=200.0)
    drone = MockWingman(520, 500, vap_ammo=5, frz_ammo=5)
    # Kamikaze 50px from leader (critical)
    threat = MockKamikaze(530, 500)
    drone.kamikazes = [threat]

    status = node.execute(drone)
    assert status == ExecutionStatus.FAILURE
    assert drone.is_sacrificing is False
    assert drone.sacrificial_target is None


def test_sacrificial_node_inhibits_when_out_of_ammo_but_no_breach():
    """Out-of-ammo wingman does NOT sacrifice if threats are far away."""
    node = SacrificialRammingNode(critical_radius_leader=200.0, critical_radius_base=200.0)
    drone = MockWingman(520, 500, vap_ammo=0, frz_ammo=0)
    # Kamikaze 600px away from both leader (500, 500) and base (1000, 500)
    threat = MockKamikaze(50, 50)
    drone.kamikazes = [threat]

    status = node.execute(drone)
    assert status == ExecutionStatus.FAILURE
    assert drone.is_sacrificing is False


def test_sacrificial_node_triggers_for_leader_breach():
    """Out-of-ammo wingman executes sacrificial intercept when threat breaches leader perimeter."""
    node = SacrificialRammingNode(critical_radius_leader=200.0)
    drone = MockWingman(520, 500, vap_ammo=0, frz_ammo=0)
    # Kamikaze only 100px from leader (500, 500)
    threat = MockKamikaze(550, 500, vx=-2.0, vy=0.0)
    drone.kamikazes = [threat]

    status = node.execute(drone)
    assert status == ExecutionStatus.RUNNING
    assert drone.is_sacrificing is True
    assert drone.sacrificial_target == threat
    assert drone.last_steered_target is not None


def test_sacrificial_node_triggers_for_base_breach():
    """Out-of-ammo wingman executes sacrificial intercept when threat breaches protected area perimeter."""
    node = SacrificialRammingNode(critical_radius_base=100.0)
    drone = MockWingman(900, 500, vap_ammo=0, frz_ammo=0)
    # Base is at (1000, 500) with radius 150. Total critical radius = 250px.
    # Threat is at (850, 500), distance to base = 150px (inside perimeter)
    threat = MockKamikaze(850, 500, vx=2.0, vy=0.0)
    drone.kamikazes = [threat]

    status = node.execute(drone)
    assert status == ExecutionStatus.RUNNING
    assert drone.is_sacrificing is True
    assert drone.sacrificial_target == threat
