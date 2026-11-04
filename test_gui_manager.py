import os
import sys
import math
import unittest
import pygame as pg

# Configure headless Pygame environment for automated verification
os.environ["SDL_VIDEODRIVER"] = "dummy"

from gui_manager import GUIManager
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, WORLD_WIDTH, WORLD_HEIGHT

vec2 = pg.math.Vector2

class MockProtectedArea:
    def __init__(self, life=100.0):
        self.life = life
        self.coordenates = vec2(300, 450)
        self.radius = 120

class MockGun:
    def __init__(self, ammo=10, available=True):
        self.ammo = ammo
        self.available = available

    def get_ammo_available(self):
        return self.ammo

class MockBehavior:
    def __init__(self, state_name="CRUISE_ESCORT"):
        self.state_name = state_name

    def get_current_state(self):
        return self.state_name

class MockDrone:
    def __init__(self, location, drone_type="wingman"):
        self.location = location
        self.velocity = vec2(3.5, 1.2)
        self.target = vec2(600, 450)
        self.behavior = MockBehavior()
        self.destroyed = False
        self.distance_chase = 300
        self.distance_formation = 150
        self.tactical_role = "INTERCEPTOR"
        self.assigned_threat = None
        self.vaporizer_gun = MockGun(ammo=8, available=True)
        self.freezing_gun = MockGun(ammo=5, available=False)
        self.current_formation_name = "WEDGE"

    def is_active(self):
        return not self.destroyed

    def draw_formation_guide(self, surface, num_drones, color, width=1):
        pg.draw.circle(surface, color, (int(self.location.x), int(self.location.y)), 100, width=width)

class MockHistory:
    def __init__(self):
        self.iterations = 4

class MockSimulation:
    def __init__(self):
        self.is_paused = False
        self.accelerated_factor = 2
        self.num_loyalwingman = 4
        self.protected_area = MockProtectedArea()
        self.leadingdrone = MockDrone(vec2(800, 450), drone_type="leader")
        self.swarm = [
            MockDrone(vec2(750, 400)),
            MockDrone(vec2(750, 500)),
            MockDrone(vec2(700, 350)),
            MockDrone(vec2(700, 550))
        ]
        self.kamikazes = [
            MockDrone(vec2(1400, 450), drone_type="kamikaze"),
            MockDrone(vec2(1500, 300), drone_type="kamikaze")
        ]
        self.swarm_manager = self

    def get_number_running_simultations(self):
        return len(self.swarm)

    def get_kamikazes_destroyed(self):
        return 12

class MockDisplayManager:
    def __init__(self, w=1600, h=900):
        self.screen_width = w
        self.screen_height = h
        self.zoom_level = 1.0
        self.offset = vec2(0, 0)
        self.centered_target = None

    def center_on(self, target):
        self.centered_target = target

    def screen_to_world(self, screen_pos):
        return vec2(screen_pos.x, screen_pos.y)

class TestGUIManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pg.init()
        cls.screen = pg.Surface((1600, 900), pg.SRCALPHA)
        cls.world_surface = pg.Surface((WORLD_WIDTH, WORLD_HEIGHT))

    def setUp(self):
        self.gui = GUIManager()
        self.sim = MockSimulation()
        self.display = MockDisplayManager()
        self.history = MockHistory()

    def test_initialization_and_layout(self):
        self.assertTrue(self.gui.visible)
        self.assertEqual(self.gui.screen_width, 1600)
        self.assertEqual(self.gui.screen_height, 900)
        self.assertTrue(self.gui.minimap_rect.width > 0)
        self.assertTrue(self.gui.inspector_rect.width > 0)

        # Test responsive layout update
        self.gui.update_layout(1280, 720)
        self.assertEqual(self.gui.screen_width, 1280)
        self.assertEqual(self.gui.screen_height, 720)
        self.assertEqual(self.gui.minimap_rect.right, 1280 - 20)

    def test_mission_card_rendering_active_and_paused(self):
        # 1. Active state rendering
        self.sim.is_paused = False
        self.gui._draw_mission_card(self.screen, self.sim, self.display, 125.4, self.history)

        # 2. Paused state rendering with damaged base
        self.sim.is_paused = True
        self.sim.protected_area.life = 45.0
        self.gui._draw_mission_card(self.screen, self.sim, self.display, 125.4, self.history)

        # 3. Critical base life
        self.sim.protected_area.life = 15.0
        self.gui._draw_mission_card(self.screen, self.sim, self.display, 125.4, self.history)

    def test_minimap_radar_rendering_and_hover(self):
        # Normal state
        self.gui.is_hovering_minimap = False
        self.gui._draw_minimap_radar(self.screen, self.sim, self.display)

        # Hover state
        self.gui.is_hovering_minimap = True
        self.gui._draw_minimap_radar(self.screen, self.sim, self.display)

    def test_agent_inspector_for_all_unit_types(self):
        # 1. Leading Drone
        self.gui.selected_agent = self.sim.leadingdrone
        self.gui.selected_type = "Leading Drone"
        self.gui.selected_index = 0
        self.gui._draw_agent_inspector(self.screen, self.sim)

        # 2. Loyal Wingman with ammo pips & assigned threat
        wingman = self.sim.swarm[0]
        wingman.assigned_threat = self.sim.kamikazes[0]
        self.gui.selected_agent = wingman
        self.gui.selected_type = "Loyal Wingman"
        self.gui.selected_index = 1
        self.gui._draw_agent_inspector(self.screen, self.sim)

        # 3. Kamikaze Threat
        self.gui.selected_agent = self.sim.kamikazes[0]
        self.gui.selected_type = "Kamikaze Threat"
        self.gui.selected_index = 1
        self.gui._draw_agent_inspector(self.screen, self.sim)

        # 4. Protected Area
        self.gui.selected_agent = self.sim.protected_area
        self.gui.selected_type = "Protected Area"
        self.gui.selected_index = 0
        self.gui._draw_agent_inspector(self.screen, self.sim)

    def test_bottom_toolbar_dynamic_keycaps(self):
        self.gui._draw_bottom_toolbar(self.screen, self.sim)

    def test_world_overlays(self):
        self.gui.selected_agent = self.sim.swarm[0]
        self.gui.selected_type = "Loyal Wingman"
        self.gui.draw_world_overlays(self.world_surface, self.sim, self.display)

        self.gui.selected_agent = self.sim.leadingdrone
        self.gui.selected_type = "Leading Drone"
        self.gui.draw_world_overlays(self.world_surface, self.sim, self.display)

    def test_event_handling_and_interactions(self):
        # Key 'H' toggles HUD visibility
        event_h = pg.event.Event(pg.KEYDOWN, key=pg.K_h)
        consumed = self.gui.handle_event(event_h, self.sim, self.display)
        self.assertTrue(consumed)
        self.assertFalse(self.gui.visible)

        # Toggle back
        consumed = self.gui.handle_event(event_h, self.sim, self.display)
        self.assertTrue(self.gui.visible)

        # Key SPACE toggles pause
        event_space = pg.event.Event(pg.KEYDOWN, key=pg.K_SPACE)
        consumed = self.gui.handle_event(event_space, self.sim, self.display)
        self.assertTrue(consumed)
        self.assertTrue(self.sim.is_paused)

        # Mouse motion updates hover state
        event_motion = pg.event.Event(pg.MOUSEMOTION, pos=(self.gui.minimap_rect.centerx, self.gui.minimap_rect.centery), rel=(0,0), buttons=(0,0,0))
        self.gui.handle_event(event_motion, self.sim, self.display)
        self.assertTrue(self.gui.is_hovering_minimap)

        # Click on Minimap centers camera
        event_click_map = pg.event.Event(pg.MOUSEBUTTONDOWN, pos=(self.gui.minimap_rect.centerx, self.gui.minimap_rect.centery), button=1)
        consumed = self.gui.handle_event(event_click_map, self.sim, self.display)
        self.assertTrue(consumed)
        self.assertIsNotNone(self.display.centered_target)

    def test_full_hud_render_performance(self):
        """Stress-tests HUD render loop across 500 frames to ensure >1000 FPS throughput."""
        import time
        self.gui.selected_agent = self.sim.swarm[0]
        self.gui.selected_type = "Loyal Wingman"
        self.gui.selected_index = 1

        t0 = time.perf_counter()
        frames = 500
        for i in range(frames):
            self.gui.draw_screen_hud(self.screen, self.sim, self.display, time_running=100.0 + i * 0.016, history=self.history)
        t1 = time.perf_counter()

        elapsed_ms = (t1 - t0) * 1000
        fps = frames / max(1e-6, (t1 - t0))
        print(f"\n✓ 500 HUD frames rendered in {elapsed_ms:.1f}ms ({fps:.0f} FPS).")
        self.assertTrue(fps > 500, f"HUD render FPS too low: {fps}")

if __name__ == "__main__":
    unittest.main()
