import math
import pygame as pg
from constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT, WORLD_WIDTH, WORLD_HEIGHT,
    SAMPLE_TIME, DISTANCE_LEADER
)

vec2 = pg.math.Vector2

class GUIManager:
    """
    Tactical HUD and Agent Inspector Manager for Simulation_Wingman.
    Provides glassmorphism telemetry panels, an interactive minimap radar,
    and clickable agent inspection with real-time AI and kinematics tracking.
    """
    def __init__(self):
        self.visible = True
        self.selected_agent = None
        self.selected_type = ""
        self.selected_index = -1
        self.pulse_phase = 0.0

        # UI Layout Coordinates
        self.minimap_width = 240
        self.minimap_height = int(240 * (WORLD_HEIGHT / WORLD_WIDTH))  # exact 1900:900 ratio ~ 114
        self.inspector_width = 300
        self.inspector_height = 250
        self.screen_width = 1600
        self.screen_height = 900
        self.update_layout(self.screen_width, self.screen_height)

        # Fonts (cached)
        pg.font.init()
        self.font_title = pg.font.SysFont("Helvetica, Arial, sans-serif", 18, bold=True)
        self.font_bold = pg.font.SysFont("Helvetica, Arial, sans-serif", 14, bold=True)
        self.font_main = pg.font.SysFont("Helvetica, Arial, sans-serif", 13)
        self.font_small = pg.font.SysFont("Helvetica, Arial, sans-serif", 11)
        self.font_mono = pg.font.SysFont("Courier, monospace", 12, bold=True)

        # Reusable translucent surfaces
        self._surf_card = None
        self._surf_minimap = None

    def update_layout(self, screen_w, screen_h):
        """Updates responsive layout bounds to match the current screen/window dimensions."""
        self.screen_width = screen_w
        self.screen_height = screen_h
        self.minimap_rect = pg.Rect(
            screen_w - self.minimap_width - 20,
            screen_h - self.minimap_height - 25,
            self.minimap_width,
            self.minimap_height
        )
        self.inspector_rect = pg.Rect(
            screen_w - self.inspector_width - 20,
            20,
            self.inspector_width,
            self.inspector_height
        )
        self.inspector_close_rect = pg.Rect(
            self.inspector_rect.right - 26,
            self.inspector_rect.top + 8,
            18, 18
        )

    def update(self):
        """Updates animation pulses."""
        self.pulse_phase = (self.pulse_phase + 0.08) % (2 * math.pi)

        # Validate selected agent lifecycle
        if self.selected_agent is not None:
            if hasattr(self.selected_agent, 'destroyed') and self.selected_agent.destroyed is True:
                self.selected_agent = None
            elif hasattr(self.selected_agent, 'is_active') and not self.selected_agent.is_active():
                self.selected_agent = None

    def handle_event(self, event, simulation, display_manager) -> bool:
        """
        Handles mouse clicks and shortcut keys for GUI and Agent Inspector.
        Returns True if the event was consumed by the GUI.
        """
        if hasattr(display_manager, 'screen_width') and hasattr(display_manager, 'screen_height'):
            if display_manager.screen_width != self.screen_width or display_manager.screen_height != self.screen_height:
                self.update_layout(display_manager.screen_width, display_manager.screen_height)
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_h:
                self.visible = not self.visible
                return True
            if event.key == pg.K_ESCAPE:
                if self.selected_agent is not None:
                    self.selected_agent = None
                    return True
            if event.key == pg.K_SPACE:
                simulation.is_paused = not getattr(simulation, 'is_paused', False)
                return True

        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = vec2(event.pos[0], event.pos[1])

            # 1. Click on Minimap -> Jump camera
            if self.minimap_rect.collidepoint(event.pos):
                nx = (mouse_pos.x - self.minimap_rect.x) / self.minimap_width
                ny = (mouse_pos.y - self.minimap_rect.y) / self.minimap_height
                world_target = vec2(nx * WORLD_WIDTH, ny * WORLD_HEIGHT)
                display_manager.center_on(world_target)
                return True

            # 2. Click on Inspector Close Button
            if self.selected_agent is not None and self.inspector_close_rect.collidepoint(event.pos):
                self.selected_agent = None
                return True

            # 3. Click on Inspector card body (prevents clicks from leaking into game world)
            if self.selected_agent is not None and self.inspector_rect.collidepoint(event.pos):
                return True

            # 4. Agent Selection in World Coordinates
            world_pos = display_manager.screen_to_world(mouse_pos)
            select_dist = 28.0 / max(0.4, display_manager.zoom_level)

            # Check Leading Drone
            if simulation.leadingdrone is not None and hasattr(simulation.leadingdrone, 'location'):
                if world_pos.distance_to(simulation.leadingdrone.location) <= select_dist + 10:
                    self.selected_agent = simulation.leadingdrone
                    self.selected_type = "Leading Drone"
                    self.selected_index = 0
                    return True

            # Check Loyal Wingmen
            for idx, wingman in enumerate(simulation.swarm):
                if world_pos.distance_to(wingman.location) <= select_dist:
                    self.selected_agent = wingman
                    self.selected_type = "Loyal Wingman"
                    self.selected_index = idx + 1
                    return True

            # Check Kamikazes
            for idx, kamikaze in enumerate(simulation.kamikazes):
                if world_pos.distance_to(kamikaze.location) <= select_dist:
                    self.selected_agent = kamikaze
                    self.selected_type = "Kamikaze Threat"
                    self.selected_index = idx + 1
                    return True

            # Check Protected Area
            if simulation.protected_area is not None:
                if world_pos.distance_to(simulation.protected_area.coordenates) <= simulation.protected_area.radius:
                    if world_pos.distance_to(simulation.protected_area.coordenates) >= simulation.protected_area.radius - 30:
                        self.selected_agent = simulation.protected_area
                        self.selected_type = "Protected Area"
                        self.selected_index = 0
                        return True

            # If user clicked empty ground and had an agent selected, deselect if not commanding leader
            # We let left clicks fall through so user can move leader
            if self.selected_agent is not None and self.selected_type != "Leading Drone":
                self.selected_agent = None

        return False

    def draw_world_overlays(self, world_surface, simulation, display_manager):
        """Draws dynamic reticles, tactical range circles, and target lines in world coordinates."""
        if not self.visible or self.selected_agent is None:
            return

        pulse = (math.sin(self.pulse_phase) + 1.0) * 0.5
        loc = getattr(self.selected_agent, 'location', getattr(self.selected_agent, 'coordenates', None))
        if loc is None:
            return

        # 1. Pulsing Target Lock Brackets around selected agent
        reticle_r = 18 + int(pulse * 5)
        color = (255, 210, 50) if self.selected_type == "Leading Drone" else \
                (50, 230, 255) if self.selected_type == "Loyal Wingman" else \
                (255, 60, 60) if self.selected_type == "Kamikaze Threat" else (100, 255, 120)

        pg.draw.circle(world_surface, color, (int(loc.x), int(loc.y)), reticle_r, width=2)
        # Tactical corner brackets
        bracket_len = 7
        for ang in [math.pi * 0.25, math.pi * 0.75, math.pi * 1.25, math.pi * 1.75]:
            bx = loc.x + (reticle_r + 4) * math.cos(ang)
            by = loc.y + (reticle_r + 4) * math.sin(ang)
            pg.draw.circle(world_surface, color, (int(bx), int(by)), 2)

        # 2. Line to current target
        target = getattr(self.selected_agent, 'target', None)
        if target is not None and isinstance(target, pg.math.Vector2):
            pg.draw.line(world_surface, (color[0], color[1], color[2]), loc, target, 1)
            pg.draw.circle(world_surface, color, (int(target.x), int(target.y)), 4, width=1)

        # 3. Tactical Range Rings for selected unit
        if self.selected_type == "Loyal Wingman":
            chase_dist = getattr(self.selected_agent, 'distance_chase', 300)
            pg.draw.circle(world_surface, (50, 200, 255), (int(loc.x), int(loc.y)), int(chase_dist), width=1)
        elif self.selected_type == "Leading Drone":
            formation_dist = getattr(self.selected_agent, 'distance_formation', DISTANCE_LEADER)
            pg.draw.circle(world_surface, (255, 220, 80), (int(loc.x), int(loc.y)), int(formation_dist), width=1)

    def draw_screen_hud(self, screen, simulation, display_manager, time_running: float, history):
        """Renders the complete modern tactical glassmorphism HUD directly onto the screen."""
        if not self.visible:
            # When HUD is hidden, show a minimal tip in corner
            tip = self.font_small.render("Press [H] to Show HUD", True, (150, 170, 190))
            screen.blit(tip, (15, 15))
            return

        sw, sh = screen.get_size()
        if sw != self.screen_width or sh != self.screen_height:
            self.update_layout(sw, sh)

        self.update()

        # 1. Top-Left: Telemetry & Mission Card
        self._draw_mission_card(screen, simulation, display_manager, time_running, history)

        # 2. Bottom-Right: Interactive Tactical Minimap Radar
        self._draw_minimap_radar(screen, simulation, display_manager)

        # 3. Top-Right: Agent Inspector Card (if an agent is selected)
        if self.selected_agent is not None:
            self._draw_agent_inspector(screen, simulation)

        # 4. Bottom Toolbar: Shortcuts & Command Pill
        self._draw_bottom_toolbar(screen, simulation)

    def _draw_glass_panel(self, screen, rect: pg.Rect, border_color=(60, 85, 120, 200), bg_color=(15, 22, 34, 215), radius=10):
        """Draws a rounded glassmorphism panel with alpha blending."""
        surf = pg.Surface((rect.width, rect.height), pg.SRCALPHA)
        pg.draw.rect(surf, bg_color, (0, 0, rect.width, rect.height), border_radius=radius)
        pg.draw.rect(surf, border_color, (0, 0, rect.width, rect.height), width=1, border_radius=radius)
        screen.blit(surf, (rect.x, rect.y))

    def _draw_mission_card(self, screen, simulation, display_manager, time_running, history):
        card_w, card_h = 320, 220
        card_rect = pg.Rect(20, 20, card_w, card_h)
        self._draw_glass_panel(screen, card_rect, border_color=(50, 90, 140, 220), bg_color=(14, 20, 32, 225))

        # Title & Status Badge
        title = self.font_title.render("LOYAL WINGMAN MUM-T", True, (240, 245, 255))
        screen.blit(title, (35, 32))

        is_paused = getattr(simulation, 'is_paused', False)
        badge_text = "❚❚ PAUSED" if is_paused else "● RUNNING"
        badge_color = (255, 200, 60) if is_paused else (60, 230, 130)
        badge = self.font_bold.render(badge_text, True, badge_color)
        screen.blit(badge, (card_rect.right - badge.get_width() - 15, 34))

        # Separator line
        pg.draw.line(screen, (40, 60, 85), (35, 58), (card_rect.right - 15, 58), 1)

        # Protected Area Health Bar
        pa_life = simulation.protected_area.life if simulation.protected_area else 0
        pa_pct = max(0.0, min(1.0, pa_life / 100.0))
        hp_label = self.font_small.render(f"BASE INTEGRITY: {pa_life:.0f}%", True, (190, 210, 230))
        screen.blit(hp_label, (35, 68))

        bar_x, bar_y, bar_w, bar_h = 35, 84, card_w - 50, 9
        pg.draw.rect(screen, (30, 40, 55), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
        hp_color = (70, 225, 120) if pa_pct > 0.5 else (255, 200, 50) if pa_pct > 0.2 else (255, 65, 65)
        if pa_pct > 0:
            pg.draw.rect(screen, hp_color, (bar_x, bar_y, int(bar_w * pa_pct), bar_h), border_radius=4)

        # Simulation Telemetry Grid
        y = 104
        speed = f"{simulation.accelerated_factor}x" if not is_paused else "0x"
        m, s = divmod(int(time_running), 60)
        ms = int((time_running - int(time_running)) * 10)
        time_str = f"{m:02d}:{s:02d}.{ms}"

        rows = [
            ("Sim Speed:", speed, (230, 240, 255), "Sim Time:", time_str, (230, 240, 255)),
            ("Escorts Alive:", f"{simulation.get_number_running_simultations()}/{simulation.num_loyalwingman}", (60, 215, 245),
             "Kamikazes:", f"{len(simulation.kamikazes)} Act | {simulation.get_kamikazes_destroyed()} Dead", (255, 120, 100)),
            ("Iteration:", f"#{history.iterations + 1}", (200, 210, 230),
             "Zoom:", f"{display_manager.zoom_level:.2f}x", (180, 220, 255))
        ]

        for lbl1, val1, c1, lbl2, val2, c2 in rows:
            # Col 1
            t_lbl1 = self.font_small.render(lbl1, True, (135, 160, 185))
            t_val1 = self.font_bold.render(val1, True, c1)
            screen.blit(t_lbl1, (35, y))
            screen.blit(t_val1, (115, y - 1))

            # Col 2
            t_lbl2 = self.font_small.render(lbl2, True, (135, 160, 185))
            t_val2 = self.font_bold.render(val2, True, c2)
            screen.blit(t_lbl2, (185, y))
            screen.blit(t_val2, (255, y - 1))
            y += 20

        # Leader Status Subtext
        y += 4
        leader_alive = simulation.leadingdrone is not None and getattr(simulation.leadingdrone, 'destroyed', False) is not True
        lead_str = "Leader: ACTIVE" if leader_alive else "Leader: DESTROYED"
        lead_col = (70, 225, 120) if leader_alive else (255, 70, 70)
        t_lead = self.font_bold.render(lead_str, True, lead_col)
        screen.blit(t_lead, (35, y))

    def _draw_minimap_radar(self, screen, simulation, display_manager):
        card_rect = pg.Rect(
            self.minimap_rect.x - 6,
            self.minimap_rect.y - 20,
            self.minimap_width + 12,
            self.minimap_height + 26
        )
        self._draw_glass_panel(screen, card_rect, border_color=(45, 80, 120, 200), bg_color=(12, 18, 28, 225))

        lbl = self.font_small.render("TACTICAL RADAR (Click to Jump)", True, (140, 175, 205))
        screen.blit(lbl, (self.minimap_rect.x, self.minimap_rect.y - 17))

        # Radar Viewport Area
        pg.draw.rect(screen, (8, 12, 20), self.minimap_rect)
        pg.draw.rect(screen, (35, 55, 80), self.minimap_rect, width=1)

        # Scale Factors
        sx = self.minimap_width / WORLD_WIDTH
        sy = self.minimap_height / WORLD_HEIGHT

        # Delimitation combat boundary
        bound_x = self.minimap_rect.x + int((WORLD_WIDTH / 3) * sx)
        pg.draw.line(screen, (30, 75, 45), (bound_x, self.minimap_rect.y), (bound_x, self.minimap_rect.bottom), 1)

        # Protected Area
        if simulation.protected_area:
            pa_pos = simulation.protected_area.coordenates
            mx = self.minimap_rect.x + int(pa_pos.x * sx)
            my = self.minimap_rect.y + int(pa_pos.y * sy)
            mr = max(2, int(simulation.protected_area.radius * sx))
            pg.draw.circle(screen, (80, 180, 100), (mx, my), mr, width=1)

        # Loyal Wingmen (Cyan)
        for wingman in simulation.swarm:
            wx = self.minimap_rect.x + int(wingman.location.x * sx)
            wy = self.minimap_rect.y + int(wingman.location.y * sy)
            pg.draw.circle(screen, (50, 210, 255), (wx, wy), 2)

        # Kamikazes (Red)
        for kamikaze in simulation.kamikazes:
            kx = self.minimap_rect.x + int(kamikaze.location.x * sx)
            ky = self.minimap_rect.y + int(kamikaze.location.y * sy)
            pg.draw.circle(screen, (255, 60, 60), (kx, ky), 2)

        # Leading Drone (Bright Green / Yellow)
        if simulation.leadingdrone:
            lx = self.minimap_rect.x + int(simulation.leadingdrone.location.x * sx)
            ly = self.minimap_rect.y + int(simulation.leadingdrone.location.y * sy)
            pg.draw.circle(screen, (255, 230, 60), (lx, ly), 3)

        # Camera Viewport Frustum Box
        zoom = display_manager.zoom_level
        offset = display_manager.offset
        cam_wx = -offset.x / zoom
        cam_wy = -offset.y / zoom
        cam_ww = display_manager.screen_width / zoom
        cam_wh = display_manager.screen_height / zoom

        f_rx = self.minimap_rect.x + int(cam_wx * sx)
        f_ry = self.minimap_rect.y + int(cam_wy * sy)
        f_rw = max(4, int(cam_ww * sx))
        f_rh = max(4, int(cam_wh * sy))

        frustum_rect = pg.Rect(f_rx, f_ry, f_rw, f_rh).clamp(self.minimap_rect)
        pg.draw.rect(screen, (255, 220, 80), frustum_rect, width=1)

    def _draw_agent_inspector(self, screen, simulation):
        agent = self.selected_agent
        card_rect = self.inspector_rect
        accent_color = (255, 210, 60) if self.selected_type == "Leading Drone" else \
                       (60, 215, 245) if self.selected_type == "Loyal Wingman" else \
                       (255, 75, 75) if self.selected_type == "Kamikaze Threat" else (100, 235, 130)

        self._draw_glass_panel(screen, card_rect, border_color=(accent_color[0], accent_color[1], accent_color[2], 210), bg_color=(14, 20, 32, 235))

        # Card Title
        agent_title = f"{self.selected_type} #{self.selected_index}" if self.selected_index > 0 else self.selected_type
        t_title = self.font_title.render(agent_title, True, accent_color)
        screen.blit(t_title, (card_rect.x + 16, card_rect.y + 12))

        # Close Button [X]
        pg.draw.rect(screen, (40, 50, 70), self.inspector_close_rect, border_radius=4)
        t_x = self.font_bold.render("×", True, (200, 220, 240))
        screen.blit(t_x, (self.inspector_close_rect.x + 4, self.inspector_close_rect.y - 2))

        pg.draw.line(screen, (35, 55, 80), (card_rect.x + 15, card_rect.y + 38), (card_rect.right - 15, card_rect.y + 38), 1)

        # AI State
        y = card_rect.y + 46
        state_name = "N/A"
        if hasattr(agent, 'behavior') and agent.behavior is not None:
            if hasattr(agent.behavior, 'get_current_state'):
                state_name = agent.behavior.get_current_state()
            elif hasattr(agent.behavior, 'node_name'):
                state_name = agent.behavior.node_name

        lbl_ai = self.font_small.render("AI TACTICAL BRAIN:", True, (135, 160, 185))
        screen.blit(lbl_ai, (card_rect.x + 16, y))
        val_ai = self.font_bold.render(f"● {state_name}", True, (240, 245, 255))
        screen.blit(val_ai, (card_rect.x + 130, y))

        # Kinematics
        loc = getattr(agent, 'location', getattr(agent, 'coordenates', vec2(0, 0)))
        vel = getattr(agent, 'velocity', vec2(0, 0))
        speed = vel.length() if hasattr(vel, 'length') else 0.0

        y += 24
        lbl_pos = self.font_small.render("Position (X, Y):", True, (135, 160, 185))
        screen.blit(lbl_pos, (card_rect.x + 16, y))
        val_pos = self.font_mono.render(f"{loc.x:0.1f}, {loc.y:0.1f}", True, (220, 235, 250))
        screen.blit(val_pos, (card_rect.x + 130, y))

        y += 20
        lbl_spd = self.font_small.render("Linear Speed:", True, (135, 160, 185))
        screen.blit(lbl_spd, (card_rect.x + 16, y))
        val_spd = self.font_mono.render(f"{speed:0.2f} px/f", True, (220, 235, 250))
        screen.blit(val_spd, (card_rect.x + 130, y))

        # Target Distance
        if simulation.leadingdrone is not None and hasattr(simulation.leadingdrone, 'location'):
            dist_lead = loc.distance_to(simulation.leadingdrone.location)
            y += 20
            lbl_lead = self.font_small.render("Dist to Leader:", True, (135, 160, 185))
            screen.blit(lbl_lead, (card_rect.x + 16, y))
            val_lead = self.font_mono.render(f"{dist_lead:0.1f} px", True, (220, 235, 250))
            screen.blit(val_lead, (card_rect.x + 130, y))

        # Weapons Inventory (if Loyal Wingman)
        if self.selected_type == "Loyal Wingman":
            y += 26
            pg.draw.line(screen, (35, 55, 80), (card_rect.x + 15, y - 4), (card_rect.right - 15, y - 4), 1)

            vap_ammo = agent.vaporizer_gun.get_ammo_available() if hasattr(agent, 'vaporizer_gun') else 0
            frz_ammo = agent.freezing_gun.get_ammo_available() if hasattr(agent, 'freezing_gun') else 0

            lbl_wep = self.font_small.render("WEAPONS SYSTEMS", True, (140, 175, 205))
            screen.blit(lbl_wep, (card_rect.x + 16, y))

            y += 20
            v_stat = "READY" if getattr(agent.vaporizer_gun, 'available', True) else "RELOAD"
            v_col = (70, 225, 120) if v_stat == "READY" else (255, 180, 50)
            t_v = self.font_small.render(f"• Vaporizer (100px): {vap_ammo}/10", True, (210, 225, 240))
            t_vs = self.font_bold.render(v_stat, True, v_col)
            screen.blit(t_v, (card_rect.x + 16, y))
            screen.blit(t_vs, (card_rect.right - t_vs.get_width() - 16, y))

            y += 18
            f_stat = "READY" if getattr(agent.freezing_gun, 'available', True) else "RELOAD"
            f_col = (70, 225, 120) if f_stat == "READY" else (255, 180, 50)
            t_f = self.font_small.render(f"• Freezing  (300px): {frz_ammo}/10", True, (210, 225, 240))
            t_fs = self.font_bold.render(f_stat, True, f_col)
            screen.blit(t_f, (card_rect.x + 16, y))
            screen.blit(t_fs, (card_rect.right - t_fs.get_width() - 16, y))

        elif self.selected_type == "Protected Area":
            y += 26
            pg.draw.line(screen, (35, 55, 80), (card_rect.x + 15, y - 4), (card_rect.right - 15, y - 4), 1)
            t_life = self.font_bold.render(f"Structural Integrity: {agent.life}%", True, (70, 225, 120) if agent.life > 30 else (255, 70, 70))
            screen.blit(t_life, (card_rect.x + 16, y))

    def _draw_bottom_toolbar(self, screen, simulation):
        chips = [
            ("SPACE", "Pause/Play"),
            ("L-Click", "Select/Move"),
            ("R-Click", "Spawn Kamikaze"),
            ("C", "Center Leader"),
            ("0", "Reset View"),
            ("D", "Debug/Rings"),
            ("+/-", "Speed"),
            ("P", "Plot"),
            ("H", "Hide HUD")
        ]

        bar_h = 28
        bar_w = 780
        bar_x = (self.screen_width - bar_w) // 2
        bar_y = self.screen_height - bar_h - 10

        pill_rect = pg.Rect(bar_x, bar_y, bar_w, bar_h)
        self._draw_glass_panel(screen, pill_rect, border_color=(40, 65, 95, 180), bg_color=(12, 17, 26, 210), radius=14)

        cx = bar_x + 15
        for key, desc in chips:
            # Key badge
            k_surf = self.font_mono.render(key, True, (255, 220, 80))
            d_surf = self.font_small.render(desc, True, (150, 180, 210))

            screen.blit(k_surf, (cx, bar_y + 7))
            screen.blit(d_surf, (cx + k_surf.get_width() + 3, bar_y + 8))
            cx += k_surf.get_width() + d_surf.get_width() + 14
