import pytest
import pygame as pg
from message_manager import MessageManager, MessageTopic
from decision_making import AttackThreatNode
from weapons import Vaporizer, Freezing
from constants import SAMPLE_TIME, COOLDOWN_VAPORIZER

vec2 = pg.math.Vector2


class MockGun:
    def __init__(self, ammo=10):
        self.ammo = ammo
        self.available = True

    def get_ammo_available(self):
        return self.ammo

    def fire(self, target=None, origin=None):
        if self.ammo <= 0:
            return None
        self.ammo -= 1
        return True


class MockKamikaze:
    def __init__(self, agent_id, x, y):
        self.agent_id = agent_id
        self.location = vec2(x, y)
        self.velocity = vec2(0, 0)
        self.destroyed = False
        self.explode = False


class MockDatalinkWingman:
    def __init__(self, agent_id, x, y, bus, enable_anti_overkill=True):
        self.agent_id = agent_id
        self.location = vec2(x, y)
        self.velocity = vec2(0, 0)
        self.message_bus = bus
        self.enable_anti_overkill = enable_anti_overkill
        self.engaged_threats = {}
        self.sim_time = 0.0

        self.vaporizer_gun = MockGun(10)
        self.freezing_gun = MockGun(10)
        self.kamikazes = []
        self.kamikaze_to_attack = None
        self.closest_kamikaze = vec2(0, 0)
        self.distance_closest_kamikaze = 50.0
        self.index_closest = 0
        self.shots_fired = 0

        if bus is not None:
            bus.register_agent(agent_id)

    def poll_messages(self):
        if self.message_bus is not None:
            return self.message_bus.receive_messages(self.agent_id)
        return []

    def broadcast_message(self, topic, payload, current_time=0.0):
        if self.message_bus is not None:
            return self.message_bus.broadcast(self.agent_id, topic, payload, current_time)
        return False

    def process_tactical_messages(self, current_time: float = 0.0):
        self.sim_time = current_time
        messages = self.poll_messages()
        for msg in messages:
            if msg.topic in (MessageTopic.WEAPON_RELEASE, "WEAPON_RELEASE"):
                target_id = msg.payload.get("target_id")
                eta = msg.payload.get("eta", 0.4)
                if target_id is not None:
                    self.engaged_threats[target_id] = current_time + eta + 0.15

    def is_threat_engaged(self, threat, current_time: float = None) -> bool:
        if not self.enable_anti_overkill or threat is None:
            return False
        t_curr = self.sim_time if current_time is None else current_time
        self.engaged_threats = {tid: exp for tid, exp in self.engaged_threats.items() if exp > t_curr}
        tid = getattr(threat, 'agent_id', id(threat))
        return tid in self.engaged_threats

    def find_unengaged_candidate_threat(self, max_range: float = 120.0, current_time: float = None):
        if not self.kamikazes:
            return None
        candidate = None
        min_dist = float('inf')
        t_curr = self.sim_time if current_time is None else current_time
        for k in self.kamikazes:
            if getattr(k, 'destroyed', False) or getattr(k, 'explode', False):
                continue
            dist = (k.location - self.location).length()
            if dist <= max_range and not self.is_threat_engaged(k, t_curr):
                if dist < min_dist:
                    min_dist = dist
                    candidate = k
        return candidate

    def fire_vaporizer(self, pos):
        self.vaporizer_gun.fire()
        self.shots_fired += 1
        target = self.kamikaze_to_attack
        if target is not None and self.message_bus is not None:
            tid = getattr(target, 'agent_id', id(target))
            self.engaged_threats[tid] = self.sim_time + 0.3
            self.broadcast_message(
                topic=MessageTopic.WEAPON_RELEASE,
                payload={
                    "shooter": self.agent_id,
                    "target_id": tid,
                    "weapon_type": "VAPORIZER",
                    "eta": 0.2
                },
                current_time=self.sim_time
            )

    def fire_freezing(self, pos):
        self.freezing_gun.fire()


def test_anti_overkill_datalink_suppresses_redundant_fire():
    """Wingman 2 suppresses fire when Wingman 1 announces weapon release over datalink."""
    bus = MessageManager()
    w1 = MockDatalinkWingman("WINGMAN_1", 100, 100, bus, enable_anti_overkill=True)
    w2 = MockDatalinkWingman("WINGMAN_2", 110, 100, bus, enable_anti_overkill=True)

    threat = MockKamikaze("KAMIKAZE_1", 120, 100)
    w1.kamikazes = [threat]
    w1.kamikaze_to_attack = threat
    w1.distance_closest_kamikaze = 20.0

    w2.kamikazes = [threat]
    w2.kamikaze_to_attack = threat
    w2.distance_closest_kamikaze = 20.0

    # 1. W1 fires at threat
    w1.fire_vaporizer(threat.location)
    assert w1.shots_fired == 1
    assert threat.agent_id in w1.engaged_threats

    # 2. W2 processes datalink messages
    w2.process_tactical_messages(current_time=0.01)
    assert w2.is_threat_engaged(threat) is True

    # 3. W2 executes attack node - must NOT fire due to Anti-Overkill fire discipline!
    node = AttackThreatNode()
    node.time_cooldown_vaporizer = COOLDOWN_VAPORIZER + 0.1
    node.execute(w2)

    assert w2.shots_fired == 0, "Wingman 2 must hold fire because target is already engaged over datalink!"


def test_anti_overkill_opportunistic_retargeting():
    """If primary threat is already engaged, wingman opportunistically fires at second unengaged threat."""
    bus = MessageManager()
    w1 = MockDatalinkWingman("WINGMAN_1", 100, 100, bus, enable_anti_overkill=True)
    w2 = MockDatalinkWingman("WINGMAN_2", 105, 100, bus, enable_anti_overkill=True)

    threat1 = MockKamikaze("KAMIKAZE_1", 120, 100)
    threat2 = MockKamikaze("KAMIKAZE_2", 130, 100)

    w1.kamikazes = [threat1, threat2]
    w1.kamikaze_to_attack = threat1

    w2.kamikazes = [threat1, threat2]
    w2.kamikaze_to_attack = threat1  # Points to threat 1 initially
    w2.distance_closest_kamikaze = 20.0

    # W1 fires at threat1
    w1.fire_vaporizer(threat1.location)

    # W2 receives datalink broadcast
    w2.process_tactical_messages(current_time=0.01)

    # W2 executes attack node: sees threat 1 is engaged, opportunistically switches to threat 2!
    node = AttackThreatNode()
    node.time_cooldown_vaporizer = COOLDOWN_VAPORIZER + 0.1
    node.execute(w2)

    assert w2.shots_fired == 1, "Wingman 2 should opportunistically fire at the second free threat!"
    assert w2.kamikaze_to_attack == threat2


def test_anti_overkill_shoot_look_shoot_timeout_expiry():
    """If threat is still alive after ETA expiry, second-chance fire is permitted."""
    bus = MessageManager()
    w = MockDatalinkWingman("WINGMAN_1", 100, 100, bus, enable_anti_overkill=True)
    threat = MockKamikaze("KAMIKAZE_1", 120, 100)

    # Mark as engaged with expiry at t=0.5s
    w.engaged_threats["KAMIKAZE_1"] = 0.5

    # At t=0.2s: still engaged
    assert w.is_threat_engaged(threat, current_time=0.2) is True

    # At t=0.6s: timeout expired!
    assert w.is_threat_engaged(threat, current_time=0.6) is False
