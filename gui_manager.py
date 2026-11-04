import math
import os
import pygame as pg
from constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT, WORLD_WIDTH, WORLD_HEIGHT,
    SAMPLE_TIME, DISTANCE_LEADER
)

vec2 = pg.math.Vector2

class GUIManager:
    """
    High-Fidelity Aerospace Tactical C2 HUD & Agent Inspector Manager.
    Designed according to human-centered design principles (humanize-ui):
    - Multi-layer glassmorphism cockpit panels with specular lighting
    - Segmented military avionics health bars and tactical ammo pip displays
    - Interactive radar scope with grid reticles and dynamic cursor affordance
    - Monospace telemetry alignment to eliminate optical jitter
    - Adaptive, centered keycap toolbar
    """
    def __init__(self):
        self.visible = True
        self.selected_agent = None
        self.selected_type = ""
        self.selected_index = -1
        self.pulse_phase = 0.0

        # UI Layout Coordinates
        self.minimap_width = 240
        self.minimap_height = int(240 * (WORLD_HEIGHT / WORLD_WIDTH))  # 1900:900 ratio ~ 114
        self.inspector_width = 310
        self.inspector_height = 310
        self.screen_width = 1600
        self.screen_height = 900
        self.update_layout(self.screen_width, self.screen_height)

        # Hover states
        self.mouse_pos = (0, 0)
        self.is_hovering_minimap = False
        self.is_hovering_close = False
        self._current_cursor = None

        # Fonts (cached)
        pg.font.init()
        self.font_title = pg.font.SysFont("Helvetica, Arial, sans-serif", 16, bold=True)
        self.font_bold = pg.font.SysFont("Helvetica, Arial, sans-serif", 13, bold=True)
        self.font_main = pg.font.SysFont("Helvetica, Arial, sans-serif", 12)
        self.font_small = pg.font.SysFont("Helvetica, Arial, sans-serif", 11)
        self.font_mono = pg.font.SysFont("Courier, monospace", 12, bold=True)
        self.font_key = pg.font.SysFont("Courier, monospace", 11, bold=True)

    def update_layout(self, screen_w, screen_h):
        """Updates responsive layout bounds to match the current screen/window dimensions."""
        self.screen_width = screen_w
        self.screen_height = screen_h
        self.minimap_height = max(80, int(self.minimap_width * (screen_h / screen_w)))
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
        """Updates animation pulses and validates agent lifecycle."""
        self.pulse_phase = (self.pulse_phase + 0.08) % (2 * math.pi)

        # Validate selected agent lifecycle
        if self.selected_agent is not None:
            if hasattr(self.selected_agent, 'destroyed') and self.selected_agent.destroyed is True:
                self.selected_agent = None
            elif hasattr(self.selected_agent, 'is_active') and not self.selected_agent.is_active():
                self.selected_agent = None

    def handle_event(self, event, simulation, display_manager) -> bool:
        """
        Handles mouse clicks, hover detection, and shortcut keys for GUI and Agent Inspector.
        Returns True if the event was consumed by the GUI.
        """
        if hasattr(display_manager, 'screen_width') and hasattr(display_manager, 'screen_height'):
            if display_manager.screen_width != self.screen_width or display_manager.screen_height != self.screen_height:
                self.update_layout(display_manager.screen_width, display_manager.screen_height)

        # Mouse motion for hover affordance
        if event.type == pg.MOUSEMOTION:
            self.mouse_pos = event.pos
            self.is_hovering_minimap = self.minimap_rect.collidepoint(event.pos)
            self.is_hovering_close = self.inspector_close_rect.collidepoint(event.pos) if self.selected_agent else False
            self._update_cursor()

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
            if self.selected_agent is not None and self.selected_type != "Leading Drone":
                self.selected_agent = None

        return False

    def _update_cursor(self):
        """Contextually updates the system mouse cursor without crashing in headless tests."""
        desired_cursor = pg.SYSTEM_CURSOR_CROSSHAIR if self.is_hovering_minimap else pg.SYSTEM_CURSOR_HAND if self.is_hovering_close else pg.SYSTEM_CURSOR_ARROW
        if desired_cursor != self._current_cursor:
            self._current_cursor = desired_cursor
            try:
                pg.mouse.set_cursor(desired_cursor)
            except Exception:
                pass

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
        for ang in [math.pi * 0.25, math.pi * 0.75, math.pi * 1.25, math.pi * 1.75]:
            bx = loc.x + (reticle_r + 4) * math.cos(ang)
            by = loc.y + (reticle_r + 4) * math.sin(ang)
            pg.draw.circle(world_surface, color, (int(bx), int(by)), 2)

        # 2. Line to current target
        target = getattr(self.selected_agent, 'target', None)
        if target is not None and isinstance(target, pg.math.Vector2):
            pg.draw.line(world_surface, color, loc, target, 1)
            pg.draw.circle(world_surface, color, (int(target.x), int(target.y)), 4, width=1)

        # 3. Tactical Range Rings for selected unit
        if self.selected_type == "Loyal Wingman":
            chase_dist = getattr(self.selected_agent, 'distance_chase', 300)
            pg.draw.circle(world_surface, (50, 200, 255), (int(loc.x), int(loc.y)), int(chase_dist), width=1)
        elif self.selected_type == "Leading Drone":
            # Highlight active formation geometry in tactical gold for selected leader
            if hasattr(self.selected_agent, 'draw_formation_guide'):
                num_sw = len(getattr(simulation.swarm_manager, 'swarm', []))
                self.selected_agent.draw_formation_guide(world_surface, num_drones=num_sw, color=(255, 220, 80), width=1)
            else:
                formation_dist = getattr(self.selected_agent, 'distance_formation', DISTANCE_LEADER)
                pg.draw.circle(world_surface, (255, 220, 80), (int(loc.x), int(loc.y)), int(formation_dist), width=1)

    def draw_screen_hud(self, screen, simulation, display_manager, time_running: float, history):
        """Renders the complete modern tactical glassmorphism HUD directly onto the screen."""
        if not self.visible:
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

    def _draw_glass_panel(self, screen, rect: pg.Rect, border_color=(50, 85, 130, 200),
                          bg_color=(12, 18, 30, 225), radius=10, with_specular=True):
        """
        Draws an aerospace-grade rounded glassmorphism panel.
        Includes an optical specular top highlight to simulate physical cockpit MFD acrylic glass.
        """
        surf = pg.Surface((rect.width, rect.height), pg.SRCALPHA)
        # Background fill
        pg.draw.rect(surf, bg_color, (0, 0, rect.width, rect.height), border_radius=radius)
        # Outer border
        pg.draw.rect(surf, border_color, (0, 0, rect.width, rect.height), width=1, border_radius=radius)

        # Specular top highlight (subtle light reflection along top 1px)
        if with_specular and rect.width > 20 and rect.height > 10:
            pg.draw.line(surf, (200, 225, 255, 45), (radius, 1), (rect.width - radius, 1), 1)

        screen.blit(surf, (rect.x, rect.y))

    def _draw_mission_card(self, screen, simulation, display_manager, time_running, history):
        """Draws the primary mission telemetry and base integrity panel."""
        card_w, card_h = 320, 225
        card_rect = pg.Rect(20, 20, card_w, card_h)
        self._draw_glass_panel(screen, card_rect, border_color=(45, 80, 125, 215), bg_color=(11, 17, 28, 230))

        # Title
        title = self.font_title.render("LOYAL WINGMAN MUM-T", True, (240, 245, 255))
        screen.blit(title, (35, 32))

        # Tactical Status Badge Pill
        is_paused = getattr(simulation, 'is_paused', False)
        badge_text = "❚❚ PAUSED" if is_paused else "● ACTIVE"
        badge_bg = (48, 38, 14, 210) if is_paused else (14, 45, 28, 210)
        badge_border = (220, 170, 45, 220) if is_paused else (50, 205, 110, 220)
        badge_col = (255, 210, 65) if is_paused else (70, 240, 130)

        t_badge = self.font_bold.render(badge_text, True, badge_col)
        bw = t_badge.get_width() + 14
        bh = 20
        bx = card_rect.right - bw - 15
        by = 31

        badge_surf = pg.Surface((bw, bh), pg.SRCALPHA)
        pg.draw.rect(badge_surf, badge_bg, (0, 0, bw, bh), border_radius=10)
        pg.draw.rect(badge_surf, badge_border, (0, 0, bw, bh), width=1, border_radius=10)
        screen.blit(badge_surf, (bx, by))
        screen.blit(t_badge, (bx + 7, by + 2))

        # Divider
        pg.draw.line(screen, (32, 50, 72), (35, 57), (card_rect.right - 15, 57), 1)

        # Base Structural Integrity (Segmented Avionics Bar)
        pa_life = simulation.protected_area.life if simulation.protected_area else 0
        pa_pct = max(0.0, min(1.0, pa_life / 100.0))
        hp_label = self.font_small.render("PROTECTED BASE INTEGRITY", True, (135, 160, 185))
        hp_val = self.font_mono.render(f"{pa_life:.0f}%", True,
                                       (70, 235, 130) if pa_pct > 0.5 else (255, 200, 50) if pa_pct > 0.2 else (255, 65, 65))
        screen.blit(hp_label, (35, 66))
        screen.blit(hp_val, (card_rect.right - hp_val.get_width() - 15, 65))

        bar_x, bar_y, bar_w, bar_h = 35, 82, card_w - 50, 8
        # Inset Track
        pg.draw.rect(screen, (20, 28, 42), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        pg.draw.rect(screen, (40, 55, 80), (bar_x, bar_y, bar_w, bar_h), width=1, border_radius=3)

        hp_color = (65, 220, 115) if pa_pct > 0.5 else (255, 195, 45) if pa_pct > 0.2 else (255, 60, 60)
        fill_w = int(bar_w * pa_pct)
        if fill_w > 0:
            pg.draw.rect(screen, hp_color, (bar_x, bar_y, fill_w, bar_h), border_radius=3)

        # Tactical Segment Dividers (25%, 50%, 75%)
        for div in [0.25, 0.5, 0.75]:
            dx = bar_x + int(bar_w * div)
            pg.draw.line(screen, (12, 18, 30), (dx, bar_y), (dx, bar_y + bar_h - 1), 1)

        # Telemetry Grid
        y = 100
        speed = f"{simulation.accelerated_factor}x" if not is_paused else "0x"
        m, s = divmod(int(time_running), 60)
        ms = int((time_running - int(time_running)) * 10)
        time_str = f"{m:02d}:{s:02d}.{ms}"

        rows = [
            ("Sim Speed:", speed, (230, 240, 255), "Sim Time:", time_str, (230, 240, 255)),
            ("Escorts Alive:", f"{simulation.get_number_running_simultations()}/{simulation.num_loyalwingman}", (60, 215, 245),
             "Kamikazes:", f"{len(simulation.kamikazes)} Act | {simulation.get_kamikazes_destroyed()} Kill", (255, 110, 95)),
            ("Episode:", f"#{history.iterations + 1}", (200, 210, 230),
             "Zoom Level:", f"{display_manager.zoom_level:.2f}x", (180, 220, 255))
        ]

        for lbl1, val1, c1, lbl2, val2, c2 in rows:
            t_lbl1 = self.font_small.render(lbl1, True, (125, 150, 175))
            t_val1 = self.font_bold.render(val1, True, c1)
            screen.blit(t_lbl1, (35, y))
            screen.blit(t_val1, (115, y - 1))

            t_lbl2 = self.font_small.render(lbl2, True, (125, 150, 175))
            t_val2 = self.font_bold.render(val2, True, c2)
            screen.blit(t_lbl2, (185, y))
            screen.blit(t_val2, (255, y - 1))
            y += 20

        # Leader Escort Status
        y += 4
        leader_alive = simulation.leadingdrone is not None and getattr(simulation.leadingdrone, 'destroyed', False) is not True
        formation_name = getattr(simulation.leadingdrone, 'current_formation_name', 'CIRCLE') if simulation.leadingdrone else 'N/A'
        lead_str = f"LEADER: {'AIRBORNE' if leader_alive else 'MIA'}  |  FORMATION: [{formation_name}]"
        lead_col = (70, 225, 120) if leader_alive else (255, 70, 70)
        t_lead = self.font_bold.render(lead_str, True, lead_col)
        screen.blit(t_lead, (35, y))

    def _draw_minimap_radar(self, screen, simulation, display_manager):
        """Draws the tactical radar display with coordinate grid reticles and camera frustum."""
        card_rect = pg.Rect(
            self.minimap_rect.x - 6,
            self.minimap_rect.y - 20,
            self.minimap_width + 12,
            self.minimap_height + 26
        )
        border_col = (60, 110, 170, 230) if self.is_hovering_minimap else (40, 75, 115, 200)
        self._draw_glass_panel(screen, card_rect, border_color=border_col, bg_color=(10, 16, 26, 230))

        lbl = self.font_small.render("TACTICAL RADAR (Click to Jump)", True, (150, 185, 215))
        screen.blit(lbl, (self.minimap_rect.x, self.minimap_rect.y - 17))

        # Radar Viewport Area
        pg.draw.rect(screen, (7, 11, 18), self.minimap_rect)
        pg.draw.rect(screen, (32, 50, 75), self.minimap_rect, width=1)

        # Scale Factors
        sx = self.minimap_width / WORLD_WIDTH
        sy = self.minimap_height / WORLD_HEIGHT

        # Radar Reticle Grid (Center crosshair ticks)
        cx = self.minimap_rect.x + self.minimap_width // 2
        cy = self.minimap_rect.y + self.minimap_height // 2
        pg.draw.line(screen, (18, 30, 48), (self.minimap_rect.x, cy), (self.minimap_rect.right, cy), 1)
        pg.draw.line(screen, (18, 30, 48), (cx, self.minimap_rect.y), (cx, self.minimap_rect.bottom), 1)

        # Delimitation Combat Boundary
        bound_x = self.minimap_rect.x + int((WORLD_WIDTH / 3) * sx)
        pg.draw.line(screen, (25, 65, 40), (bound_x, self.minimap_rect.y), (bound_x, self.minimap_rect.bottom), 1)

        # Protected Area
        if simulation.protected_area:
            pa_pos = simulation.protected_area.coordenates
            mx = self.minimap_rect.x + int(pa_pos.x * sx)
            my = self.minimap_rect.y + int(pa_pos.y * sy)
            mr = max(2, int(simulation.protected_area.radius * sx))
            pg.draw.circle(screen, (75, 175, 95), (mx, my), mr, width=1)

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

        # Leading Drone (Tactical Gold)
        if simulation.leadingdrone:
            lx = self.minimap_rect.x + int(simulation.leadingdrone.location.x * sx)
            ly = self.minimap_rect.y + int(simulation.leadingdrone.location.y * sy)
            pg.draw.circle(screen, (255, 225, 60), (lx, ly), 3)

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
        pg.draw.rect(screen, (255, 215, 70), frustum_rect, width=1)

        # Radar Scope Corner Brackets
        cr = 6
        rx, ry, rw, rh = self.minimap_rect.x, self.minimap_rect.y, self.minimap_rect.width, self.minimap_rect.height
        pg.draw.lines(screen, (60, 95, 140), False, [(rx, ry + cr), (rx, ry), (rx + cr, ry)], 1)
        pg.draw.lines(screen, (60, 95, 140), False, [(rx + rw - cr, ry), (rx + rw, ry), (rx + rw, ry + cr)], 1)
        pg.draw.lines(screen, (60, 95, 140), False, [(rx, ry + rh - cr), (rx, ry + rh), (rx + cr, ry + rh)], 1)
        pg.draw.lines(screen, (60, 95, 140), False, [(rx + rw - cr, ry + rh), (rx + rw, ry + rh), (rx + rw, ry + rh - cr)], 1)

    def _draw_agent_inspector(self, screen, simulation):
        """Draws the selected agent telemetry card with ammo pips, AI brain state, and kinematics."""
        agent = self.selected_agent
        card_rect = self.inspector_rect
        accent_color = (255, 210, 60) if self.selected_type == "Leading Drone" else \
                       (60, 215, 245) if self.selected_type == "Loyal Wingman" else \
                       (255, 75, 75) if self.selected_type == "Kamikaze Threat" else (100, 235, 130)

        self._draw_glass_panel(screen, card_rect,
                               border_color=(accent_color[0], accent_color[1], accent_color[2], 210),
                               bg_color=(12, 18, 30, 235))

        # Title
        agent_title = f"{self.selected_type} #{self.selected_index}" if self.selected_index > 0 else self.selected_type
        t_title = self.font_title.render(agent_title, True, accent_color)
        screen.blit(t_title, (card_rect.x + 16, card_rect.y + 12))

        # Close Button [X] with hover state
        close_bg = (80, 35, 35) if self.is_hovering_close else (30, 42, 60)
        close_border = (200, 70, 70) if self.is_hovering_close else (50, 70, 95)
        pg.draw.rect(screen, close_bg, self.inspector_close_rect, border_radius=4)
        pg.draw.rect(screen, close_border, self.inspector_close_rect, width=1, border_radius=4)
        t_x = self.font_bold.render("×", True, (255, 200, 200) if self.is_hovering_close else (190, 210, 230))
        screen.blit(t_x, (self.inspector_close_rect.x + 4, self.inspector_close_rect.y - 2))

        pg.draw.line(screen, (32, 50, 75), (card_rect.x + 15, card_rect.y + 38), (card_rect.right - 15, card_rect.y + 38), 1)

        # AI Tactical Brain State
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
        screen.blit(val_ai, (card_rect.x + 135, y))

        # Kinematics
        loc = getattr(agent, 'location', getattr(agent, 'coordenates', vec2(0, 0)))
        vel = getattr(agent, 'velocity', vec2(0, 0))
        speed = vel.length() if hasattr(vel, 'length') else 0.0

        y += 24
        lbl_pos = self.font_small.render("Position (X, Y):", True, (135, 160, 185))
        screen.blit(lbl_pos, (card_rect.x + 16, y))
        val_pos = self.font_mono.render(f"{loc.x:0.1f}, {loc.y:0.1f}", True, (220, 235, 250))
        screen.blit(val_pos, (card_rect.x + 135, y))

        y += 20
        lbl_spd = self.font_small.render("Linear Speed:", True, (135, 160, 185))
        screen.blit(lbl_spd, (card_rect.x + 16, y))
        val_spd = self.font_mono.render(f"{speed:0.2f} px/f", True, (220, 235, 250))
        screen.blit(val_spd, (card_rect.x + 135, y))

        # Distance to Leader
        if simulation.leadingdrone is not None and hasattr(simulation.leadingdrone, 'location'):
            dist_lead = loc.distance_to(simulation.leadingdrone.location)
            y += 20
            lbl_lead = self.font_small.render("Dist to Leader:", True, (135, 160, 185))
            screen.blit(lbl_lead, (card_rect.x + 16, y))
            val_lead = self.font_mono.render(f"{dist_lead:0.1f} px", True, (220, 235, 250))
            screen.blit(val_lead, (card_rect.x + 135, y))

        # Formation Details (if Leading Drone)
        if self.selected_type == "Leading Drone":
            y += 22
            lbl_form = self.font_small.render("Formation Geometry:", True, (135, 160, 185))
            screen.blit(lbl_form, (card_rect.x + 16, y))
            form_name = getattr(agent, 'current_formation_name', 'CIRCLE')
            val_form = self.font_bold.render(f"[ {form_name} ]", True, (60, 225, 245))
            screen.blit(val_form, (card_rect.x + 135, y))

        # Weapons Inventory & Pips (if Loyal Wingman)
        elif self.selected_type == "Loyal Wingman":
            role = getattr(agent, 'tactical_role', 'INTERCEPTOR')
            y += 20
            lbl_role = self.font_small.render("Tactical Role:", True, (135, 160, 185))
            screen.blit(lbl_role, (card_rect.x + 16, y))
            role_col = (60, 220, 245) if role == "INTERCEPTOR" else (255, 210, 60)
            val_role = self.font_bold.render(f"{role}", True, role_col)
            screen.blit(val_role, (card_rect.x + 135, y))

            # Target Lock Tracking
            assigned = getattr(agent, 'assigned_threat', None)
            if assigned is not None and hasattr(assigned, 'location'):
                y += 20
                lbl_tgt = self.font_small.render("Locked Threat:", True, (135, 160, 185))
                screen.blit(lbl_tgt, (card_rect.x + 16, y))
                tgt_dist = loc.distance_to(assigned.location)
                val_tgt = self.font_mono.render(f"{tgt_dist:0.1f} px", True, (255, 110, 110))
                screen.blit(val_tgt, (card_rect.x + 135, y))

            # Weapons Systems & Pips
            y += 24
            pg.draw.line(screen, (32, 50, 75), (card_rect.x + 15, y - 4), (card_rect.right - 15, y - 4), 1)

            lbl_wep = self.font_small.render("WEAPONS SYSTEMS & AMMO PIPS", True, (140, 175, 205))
            screen.blit(lbl_wep, (card_rect.x + 16, y))

            # 1. Vaporizer Gun
            y += 20
            vap_ammo = agent.vaporizer_gun.get_ammo_available() if hasattr(agent, 'vaporizer_gun') else 0
            v_avail = getattr(agent.vaporizer_gun, 'available', True) if hasattr(agent, 'vaporizer_gun') else False
            self._draw_weapon_pip_row(screen, card_rect.x + 16, y, "Vaporizer (100px)", vap_ammo, 10,
                                     pip_color=(60, 220, 245), is_ready=v_avail)

            # 2. Freezing Gun
            y += 24
            frz_ammo = agent.freezing_gun.get_ammo_available() if hasattr(agent, 'freezing_gun') else 0
            f_avail = getattr(agent.freezing_gun, 'available', True) if hasattr(agent, 'freezing_gun') else False
            self._draw_weapon_pip_row(screen, card_rect.x + 16, y, "Freezing  (300px)", frz_ammo, 10,
                                     pip_color=(100, 240, 150), is_ready=f_avail)

        elif self.selected_type == "Protected Area":
            y += 26
            pg.draw.line(screen, (32, 50, 75), (card_rect.x + 15, y - 4), (card_rect.right - 15, y - 4), 1)
            t_life = self.font_bold.render(f"Structural Integrity: {agent.life}%", True,
                                           (70, 225, 120) if agent.life > 30 else (255, 70, 70))
            screen.blit(t_life, (card_rect.x + 16, y))

    def _draw_weapon_pip_row(self, screen, x, y, name, ammo, max_ammo, pip_color, is_ready):
        """Draws a tactical weapon row with name, ammunition count, and discrete military pip blocks."""
        t_name = self.font_small.render(name, True, (210, 225, 240))
        screen.blit(t_name, (x, y))

        # Status badge (READY vs RELOADING)
        stat_text = "READY" if is_ready else "RELOAD"
        stat_col = (70, 225, 120) if is_ready else (255, 180, 50)
        t_stat = self.font_bold.render(stat_text, True, stat_col)
        screen.blit(t_stat, (x + 215, y))

        # Discrete Ammo Pips (10 blocks)
        pip_w, pip_h = 7, 7
        pip_gap = 3
        pip_start_x = x
        pip_y = y + 14

        for i in range(max_ammo):
            px = pip_start_x + i * (pip_w + pip_gap)
            if i < ammo:
                pg.draw.rect(screen, pip_color, (px, pip_y, pip_w, pip_h), border_radius=1)
            else:
                pg.draw.rect(screen, (30, 42, 58), (px, pip_y, pip_w, pip_h), border_radius=1)
                pg.draw.rect(screen, (50, 68, 92), (px, pip_y, pip_w, pip_h), width=1, border_radius=1)

        # Numeric count text
        t_num = self.font_mono.render(f"{ammo}/{max_ammo}", True, (160, 185, 210))
        screen.blit(t_num, (pip_start_x + max_ammo * (pip_w + pip_gap) + 12, pip_y - 2))

    def _draw_bottom_toolbar(self, screen, simulation):
        """Draws the centered shortcut keycap toolbar with tactical avionics styling."""
        chips = [
            ("SPACE", "Pause"),
            ("1-4", "Formations"),
            ("L-Click", "Select/Move"),
            ("R-Click", "Kamikaze"),
            ("C", "Center"),
            ("0", "Reset"),
            ("D", "Rings"),
            ("+/-", "Speed"),
            ("P", "Plot"),
            ("H", "HUD")
        ]

        bar_h = 28
        padding_h = 16
        gap = 12

        # Measure dynamic width for perfect centering
        measured_items = []
        total_content_w = 0
        for key, desc in chips:
            k_surf = self.font_key.render(key, True, (255, 220, 80))
            d_surf = self.font_small.render(desc, True, (160, 185, 210))
            cap_w = k_surf.get_width() + 8
            item_w = cap_w + 4 + d_surf.get_width()
            measured_items.append((k_surf, d_surf, cap_w))
            total_content_w += item_w

        total_w = total_content_w + (len(chips) - 1) * gap + padding_h * 2
        bar_x = (self.screen_width - total_w) // 2
        bar_y = self.screen_height - bar_h - 10

        pill_rect = pg.Rect(bar_x, bar_y, total_w, bar_h)
        self._draw_glass_panel(screen, pill_rect, border_color=(45, 75, 110, 190),
                               bg_color=(10, 16, 26, 220), radius=14)

        cx = bar_x + padding_h
        for k_surf, d_surf, cap_w in measured_items:
            # Keycap container
            cap_rect = pg.Rect(cx, bar_y + 4, cap_w, 20)
            pg.draw.rect(screen, (22, 32, 48), cap_rect, border_radius=3)
            pg.draw.rect(screen, (55, 80, 115), cap_rect, width=1, border_radius=3)
            screen.blit(k_surf, (cx + 4, bar_y + 6))

            # Description
            screen.blit(d_surf, (cx + cap_w + 4, bar_y + 7))
            cx += cap_w + 4 + d_surf.get_width() + gap
