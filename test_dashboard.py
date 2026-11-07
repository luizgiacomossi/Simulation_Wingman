import pytest
import time
import multiprocessing as mp
from queue import Empty
import pygame as pg
from dashboard import DashboardBridge
from swarm_manager import SwarmManager

vec2 = pg.math.Vector2


class MockSimulation:
    def __init__(self):
        self.swarm_manager = SwarmManager(window=None)
        self.swarm_manager.create_swarm(num_loyal=4, num_kamikazes=4)
        self.accelerated_factor = 1


def test_dashboard_bridge_telemetry_packet_formatting():
    """Validates that DashboardBridge serializes telemetry accurately."""
    bridge = DashboardBridge(enabled=False)
    bridge.telemetry_queue = mp.Queue()
    bridge.command_queue = mp.Queue()
    bridge.enabled = True

    sim = MockSimulation()
    bridge.emit_event("TEST_EVENT_LOG")
    bridge._push_telemetry(sim, current_time=12.5)

    packet = bridge.telemetry_queue.get(timeout=2.0)
    assert packet["sim_time"] == 12.5
    assert packet["base_hp"] == 100.0
    assert packet["active_threats"] == 4
    assert packet["leader_alive"] is True
    assert "TEST_EVENT_LOG" in packet["events"]


def test_dashboard_bridge_command_dispatch():
    """Validates that commands from the dashboard actuate the simulation correctly."""
    bridge = DashboardBridge(enabled=False)
    bridge.telemetry_queue = mp.Queue()
    bridge.command_queue = mp.Queue()
    bridge.enabled = True

    sim = MockSimulation()

    # 1. Test SET_FORMATION command
    bridge.command_queue.put({"action": "SET_FORMATION", "payload": {"formation": "WEDGE"}})
    time.sleep(0.05)  # Allow IPC feeder thread to flush
    bridge.update(sim, current_time=1.0)
    assert sim.swarm_manager.leadingdrone.formation_manager.active_strategy_name == "WEDGE"

    # 2. Test SET_SLIDER for distance_chase
    bridge.command_queue.put({"action": "SET_SLIDER", "payload": {"param": "distance_chase", "value": 450.0}})
    time.sleep(0.05)  # Allow IPC feeder thread to flush
    bridge.update(sim, current_time=2.0)
    assert sim.swarm_manager.distance_chase == 450.0
    assert sim.swarm_manager.swarm[0].distance_chase == 450.0

    # 3. Test OPERATOR_COMMAND natural language
    bridge.command_queue.put({"action": "OPERATOR_COMMAND", "payload": {"text": "deploy wall formation"}})
    time.sleep(0.05)  # Allow IPC feeder thread to flush
    bridge.update(sim, current_time=3.0)
    assert sim.swarm_manager.leadingdrone.formation_manager.active_strategy_name == "WALL"
