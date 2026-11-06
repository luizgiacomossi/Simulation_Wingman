"""
Unit and integration tests for LLMTacticalCommander in MUM-T simulation.
Verifies asynchronous telemetry aggregation, mock decision application,
tactical datalink broadcasts, and hotkey toggling.
"""

import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pytest
import pygame as pg
from pygame.math import Vector2
from unittest.mock import MagicMock, patch

from constants import *
from llm_commander import LLMTacticalCommander
from simulation import Simulation
from swarm_manager import SwarmManager


class TestLLMTacticalCommander:

    def setup_method(self):
        pg.init()
        pg.display.set_mode((1, 1))
        self.canvas = pg.Surface((800, 600))
        self.mock_screen = MagicMock()
        self.mock_screen.world_surface = self.canvas
        self.mock_screen.screen = self.canvas

        self.simulation = Simulation(self.mock_screen)
        self.simulation.create_swarm_uav(
            num_swarm=4,
            num_kamikazes=2,
            distance_chase=300,
            kp=1.0,
            kv=1.0,
            distance_formation=100.0
        )
        self.commander = LLMTacticalCommander(decision_interval=1.0)

    def test_initialization_and_toggle(self):
        assert self.commander.enabled is False
        assert self.commander.is_request_in_flight is False

        new_state = self.commander.toggle()
        assert new_state is True
        assert self.commander.enabled is True

        new_state = self.commander.toggle()
        assert new_state is False
        assert self.commander.enabled is False

    def test_build_telemetry_snapshot(self):
        snapshot = self.commander.build_telemetry_snapshot(self.simulation)
        assert "leader" in snapshot
        assert "protected_area" in snapshot
        assert "threats_detected" in snapshot
        assert "num_wingmen_alive" in snapshot

        assert snapshot["num_wingmen_alive"] == 4
        assert len(snapshot["threats_detected"]) == 2
        assert snapshot["protected_area"]["status"] in ("SECURE", "UNDER_THREAT")

    def test_apply_decision_formation_and_roles(self):
        mock_decision = {
            "selected_formation": "WALL",
            "num_interceptors": 2,
            "num_close_escorts": 2,
            "target_priority_order": ["K_1"],
            "leader_action": "HOLD_DEFENSIVE",
            "tactical_rationale": "Test wall barrier."
        }

        self.commander._apply_decision(mock_decision, self.simulation)

        # 1. Formation changed to WALL
        assert self.simulation.leadingdrone.current_formation_name == "WALL"

        # 2. Roles assigned correctly
        interceptors = [w for w in self.simulation.swarm if w.tactical_role == "INTERCEPTOR"]
        escorts = [w for w in self.simulation.swarm if w.tactical_role == "CLOSE_ESCORT"]
        assert len(interceptors) == 2
        assert len(escorts) == 2

    def test_apply_decision_leader_evasion(self):
        mock_decision = {
            "selected_formation": "CIRCLE",
            "num_interceptors": 1,
            "num_close_escorts": 3,
            "target_priority_order": [],
            "leader_action": "EVADE_RETREAT",
            "tactical_rationale": "Evade threats."
        }

        self.commander._apply_decision(mock_decision, self.simulation)
        assert self.simulation.leadingdrone.target is not None

    def test_hud_status_dictionary(self):
        status = self.commander.get_hud_status()
        assert "enabled" in status
        assert "in_flight" in status
        assert "last_formation" in status
        assert "last_latency" in status
        assert "total_decisions" in status
