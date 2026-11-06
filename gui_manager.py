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
    Operational Tactical C2 (Command & Control) Workstation for MUM-T.
    Follows humanize-ui 'Operational Console' design principles:
    - High-density flush top & bottom status bars (zero floating bubbles or dynamic islands)
    - Strict semantic MIL-STD color palette (slate neutral canvas; color reserved for IFF & alerts)
    - Crisp rectangular MFD (Multi-Function Display) inspector and radar scope
    - Tabular monospace telemetry without verbose marketing labels or decorative glyphs
    - Legible, comfortable typography scale for tactical operational displays
    """
    def __init__(self):
        self.visible = True
        self.selected_agent = None
        self.selected_type = ""
        self.selected_index = -1
        self.pulse_phase = 0.0

        # UI Layout Coordinates (scaled for optimal readability)
        self.top_bar_height = 32
        self.bottom_bar_height = 26
        self.panel_width = 340
        self.screen_width = 1600
        self.screen_height = 900

        self.minimap_width = self.panel_width
        self.minimap_height = int(self.minimap_width * (WORLD_HEIGHT / WORLD_WIDTH))  # ~ 161px
        self.inspector_width = self.panel_width
        self.inspector_height = 340

        self.update_layout(self.screen_width, self.screen_height)

        # Hover states
        self.mouse_pos = (0, 0)
        self.is_hovering_minimap = False
        self.is_hovering_close = False
        self._current_cursor = None

        # Fonts (cached technical typography with enhanced readability)
        pg.font.init()
        # Clean technical sans for labels & headers
        self.font_header = pg.font.SysFont("Helvetica, Arial, sans-serif", 15, bold=True)
        self.font_label = pg.font.SysFont("Helvetica, Arial, sans-serif", 13, bold=True)
        self.font_meta = pg.font.SysFont("Helvetica, Arial, sans-serif", 12)
        # Tabular figures monospace for all coordinates, values, and timers
        self.font_mono = pg.font.SysFont("Courier, monospace", 13, bold=True)
        self.font_mono_small = pg.font.SysFont("Courier, monospace", 12)
        self.font_key = pg.font.SysFont("Courier, monospace", 11, bold=True)

    def update_layout(self, screen_w, screen_h):
        """Updates layout bounds to match the current screen dimensions."""
        self.screen_width = screen_w
        self.screen_height = screen_h

        # Top and Bottom flush bars
        self.top_bar_rect = pg.Rect(0, 0, screen_w, self.top_bar_height)
        self.bottom_bar_rect = pg.Rect(0, screen_h - self.bottom_bar_height, screen_w, self.bottom_bar_height)

        # Right Rail Docked Panels (crisp margin: 12px from right, below top bar)
        panel_x = screen_w - self.panel_width - 12
        self.inspector_rect = pg.Rect(panel_x, self.top_bar_height + 10, self.inspector_width, self.inspector_height)
        self.inspector_close_rect = pg.Rect(self.inspector_rect.right - 24, self.inspector_rect.top + 6, 18, 18)

        # Radar Scope docked at bottom-right above bottom bar
        radar_y = screen_h - self.bottom_bar_height - self.minimap_height - 10
        self.minimap_rect = pg.Rect(panel_x, radar_y, self.minimap_width, self.minimap_height)

    def update(self):
        """Updates phase tracking and validates selected agent lifecycle."""
        self.pulse_phase = (self.pulse_phase + 0.08) % (2 * math.pi)

        # Validate selected agent lifecycle
        if self.selected_agent is not None:
            if hasattr(self.selected_agent, 'destroyed') and self.selected_agent.destroyed is True:
                self.selected_agent = None
            elif hasattr(self.selected_agent, 'is_active') and not self.selected_agent.is_active():
                self.selected_agent = None

    def handle_event(self, event, simulation, display_manager) -> bool:
        """
        Handles mouse clicks, hover detection, and shortcut keys for tactical console.
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
            if event.key == pg.K_l:
                if hasattr(simulation, 'llm_commander') and simulation.llm_commander is not None:
                    simulation.llm_commander.toggle()
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

            # 0. Click on Top Status Bar or Bottom Bar -> Toggle AI or prevent world click leak
            if self.top_bar_rect.collidepoint(event.pos) or self.bottom_bar_rect.collidepoint(event.pos):
                if hasattr(simulation, 'llm_commander') and simulation.llm_commander is not None:
                    simulation.llm_commander.toggle()
                return True

            # 1. Click on Radar Scope -> Center camera
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

            # 3. Click on Inspector card body (prevents click from leaking to game world)
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

            # Deselect if clicking empty terrain
            if self.selected_agent is not None and self.selected_type != "Leading Drone":
                self.selected_agent = None

        return False

    def _update_cursor(self):
        """Contextually updates the system mouse cursor without crashing in headless mode."""
        desired_cursor = pg.SYSTEM_CURSOR_CROSSHAIR if self.is_hovering_minimap else pg.SYSTEM_CURSOR_HAND if self.is_hovering_close else pg.SYSTEM_CURSOR_ARROW
        if desired_cursor != self._current_cursor:
            self._current_cursor = desired_cursor
            try:
                pg.mouse.set_cursor(desired_cursor)
            except Exception:
                pass

    def draw_world_overlays(self, world_surface, simulation, display_manager):
        """Draws crisp technical reticles and targeting vectors in world coordinates."""
        if not self.visible:
            return

        # 1. Tactical AI Commander Evasion Overlay (Perpendicular Notching Vector & Threat Vector)
        commander = getattr(simulation, 'llm_commander', None)
        if commander and commander.enabled and commander.last_decision:
            action = commander.last_decision.get("leader_action", "")
            leader = getattr(simulation.swarm_manager, 'leadingdrone', None)
            if leader and action == "EVADE_RETREAT" and hasattr(leader, 'target') and leader.target:
                lx, ly = int(leader.location.x), int(leader.location.y)
                tx, ty = int(leader.target.x), int(leader.target.y)
                # Cyan notching dodge vector
                pg.draw.line(world_surface, (56, 189, 248), (lx, ly), (tx, ty), 2)
                pg.draw.circle(world_surface, (56, 189, 248), (tx, ty), 5)
                # Tag label
                t_dodge = self.font_mono.render("DODGE 90° [NOTCHING]", True, (56, 189, 248))
                world_surface.blit(t_dodge, (tx + 8, ty - 8))
            elif leader and action == "SHIELD_BASE_CORRIDOR" and hasattr(leader, 'target') and leader.target:
                lx, ly = int(leader.location.x), int(leader.location.y)
                tx, ty = int(leader.target.x), int(leader.target.y)
                # Amber shield intercept vector
                pg.draw.line(world_surface, (251, 191, 36), (lx, ly), (tx, ty), 2)
                pg.draw.circle(world_surface, (251, 191, 36), (tx, ty), 6, width=2)
                t_shield = self.font_mono.render("SHIELD BASE CORRIDOR", True, (251, 191, 36))
                world_surface.blit(t_shield, (tx + 8, ty - 8))

        # 2. Sacrificial Ramming Intercept Vectors (Winchester body-block)
        for drone in getattr(simulation.swarm_manager, 'swarm', []):
            if getattr(drone, 'is_sacrificing', False) and getattr(drone, 'sacrificial_target', None):
                target = drone.sacrificial_target
                if not getattr(target, 'destroyed', False) and not getattr(target, 'explode', False):
                    dx, dy = int(drone.location.x), int(drone.location.y)
                    kx, ky = int(target.location.x), int(target.location.y)
                    pg.draw.line(world_surface, (239, 68, 68), (dx, dy), (kx, ky), 2)
                    pg.draw.circle(world_surface, (239, 68, 68), (kx, ky), 7, width=2)
                    t_sac = self.font_mono_small.render("SACRIFICE [RAMMING]", True, (239, 68, 68))
                    world_surface.blit(t_sac, (dx - 20, dy - 18))

        # 3. Selected Agent Overlays
        if self.selected_agent is None:
            return

        loc = getattr(self.selected_agent, 'location', getattr(self.selected_agent, 'coordenates', None))
        if loc is None:
            return

        # Color coding: IFF standard
        color = (251, 191, 36) if self.selected_type == "Leading Drone" else \
                (56, 189, 248) if self.selected_type == "Loyal Wingman" else \
                (248, 113, 113) if self.selected_type == "Kamikaze Threat" else (74, 222, 128)

        # Technical 4-corner targeting box
        r = 18
        bx, by = int(loc.x), int(loc.y)
        d = 6
        pg.draw.lines(world_surface, color, False, [(bx - r, by - r + d), (bx - r, by - r), (bx - r + d, by - r)], 1)
        pg.draw.lines(world_surface, color, False, [(bx + r - d, by - r), (bx + r, by - r), (bx + r, by - r + d)], 1)
        pg.draw.lines(world_surface, color, False, [(bx - r, by + r - d), (bx - r, by + r), (bx - r + d, by + r)], 1)
        pg.draw.lines(world_surface, color, False, [(bx + r - d, by + r), (bx + r, by + r), (bx + r, by + r - d)], 1)

        # Subtle center dot
        pg.draw.circle(world_surface, color, (bx, by), 2)

        # Target vector
        target = getattr(self.selected_agent, 'target', None)
        if target is not None and isinstance(target, pg.math.Vector2):
            pg.draw.line(world_surface, (color[0], color[1], color[2]), loc, target, 1)
            tx, ty = int(target.x), int(target.y)
            # Small crosshair at target endpoint
            pg.draw.line(world_surface, color, (tx - 4, ty), (tx + 4, ty), 1)
            pg.draw.line(world_surface, color, (tx, ty - 4), (tx, ty + 4), 1)

        # Range perimeters
        if self.selected_type == "Loyal Wingman":
            chase_dist = getattr(self.selected_agent, 'distance_chase', 300)
            pg.draw.circle(world_surface, (56, 189, 248), (bx, by), int(chase_dist), width=1)
        elif self.selected_type == "Leading Drone":
            if hasattr(self.selected_agent, 'draw_formation_guide'):
                num_sw = len(getattr(simulation.swarm_manager, 'swarm', []))
                self.selected_agent.draw_formation_guide(world_surface, num_drones=num_sw, color=(251, 191, 36), width=1)
            else:
                formation_dist = getattr(self.selected_agent, 'distance_formation', DISTANCE_LEADER)
                pg.draw.circle(world_surface, (251, 191, 36), (bx, by), int(formation_dist), width=1)

    def draw_screen_hud(self, screen, simulation, display_manager, time_running: float, history):
        """Renders the complete operational command console."""
        if not self.visible:
            tip = self.font_mono_small.render("[H] HUD TOGGLE", True, (100, 116, 139))
            screen.blit(tip, (12, 10))
            return

        sw, sh = screen.get_size()
        if sw != self.screen_width or sh != self.screen_height:
            self.update_layout(sw, sh)

        self.update()

        # 1. Flush Top Status Bar
        self._draw_top_status_bar(screen, simulation, display_manager, time_running, history)

        # 2. Flush Bottom Command Bar
        self._draw_bottom_toolbar(screen, simulation)

        # 3. Docked Radar Scope (Bottom-Right)
        self._draw_minimap_radar(screen, simulation, display_manager)

        # 4. Docked Telemetry Inspector (Top-Right, if selected)
        if self.selected_agent is not None:
            self._draw_agent_inspector(screen, simulation)

        # 5. Dedicated AI Tactical Commander HUD Card (Top-Left)
        if hasattr(simulation, 'llm_commander') and simulation.llm_commander is not None:
            self._draw_ai_commander_card(screen, simulation)

    # Backward compatibility alias for tests
    def _draw_mission_card(self, screen, simulation, display_manager, time_running, history):
        self._draw_top_status_bar(screen, simulation, display_manager, time_running, history)

    def _draw_top_status_bar(self, screen, simulation, display_manager, time_running, history):
        """
        High-density, single-line flush operational status strip anchored to the top of the viewport.
        Strictly zero marketing fluff: displays actual telemetry data in tabular format.
        """
        # Solid matte background and bottom separator line
        pg.draw.rect(screen, (10, 14, 22), self.top_bar_rect)
        pg.draw.line(screen, (30, 41, 59), (0, self.top_bar_height - 1), (self.screen_width, self.top_bar_height - 1), 1)

        x = 16
        y_text = 7

        # 1. Status Indicator
        is_paused = getattr(simulation, 'is_paused', False)
        st_text = "PAUSED" if is_paused else "RUNNING"
        st_col = (251, 191, 36) if is_paused else (74, 222, 128)
        t_st_lbl = self.font_label.render("SIM:", True, (100, 116, 139))
        t_st_val = self.font_mono.render(st_text, True, st_col)
        screen.blit(t_st_lbl, (x, y_text + 1))
        x += t_st_lbl.get_width() + 5
        screen.blit(t_st_val, (x, y_text))
        x += t_st_val.get_width() + 18

        # Pipe separator
        pg.draw.line(screen, (30, 41, 59), (x - 9, 6), (x - 9, self.top_bar_height - 7), 1)

        # 2. Rate & Sim Time
        speed = f"{simulation.accelerated_factor:.1f}x" if not is_paused else "0.0x"
        m, s = divmod(int(time_running), 60)
        ms = int((time_running - int(time_running)) * 10)
        time_str = f"T+{m:02d}:{s:02d}.{ms}"

        t_time_lbl = self.font_label.render("TIME:", True, (100, 116, 139))
        t_time_val = self.font_mono.render(f"{time_str} ({speed})", True, (241, 245, 249))
        screen.blit(t_time_lbl, (x, y_text + 1))
        x += t_time_lbl.get_width() + 5
        screen.blit(t_time_val, (x, y_text))
        x += t_time_val.get_width() + 18

        pg.draw.line(screen, (30, 41, 59), (x - 9, 6), (x - 9, self.top_bar_height - 7), 1)

        # 3. Base Integrity (inline compact segmented bar)
        pa_life = simulation.protected_area.life if simulation.protected_area else 0
        pa_pct = max(0.0, min(1.0, pa_life / 100.0))
        hp_col = (74, 222, 128) if pa_pct > 0.5 else (251, 191, 36) if pa_pct > 0.2 else (248, 113, 113)

        t_base_lbl = self.font_label.render("BASE:", True, (100, 116, 139))
        screen.blit(t_base_lbl, (x, y_text + 1))
        x += t_base_lbl.get_width() + 6

        bar_w = 70
        bar_h = 10
        bar_y = y_text + 4
        pg.draw.rect(screen, (15, 23, 42), (x, bar_y, bar_w, bar_h))
        pg.draw.rect(screen, (51, 65, 85), (x, bar_y, bar_w, bar_h), 1)
        fill_w = int(bar_w * pa_pct)
        if fill_w > 0:
            pg.draw.rect(screen, hp_col, (x + 1, bar_y + 1, fill_w - 2, bar_h - 2))
        x += bar_w + 6

        t_hp_pct = self.font_mono.render(f"{pa_life:3.0f}%", True, hp_col)
        screen.blit(t_hp_pct, (x, y_text))
        x += t_hp_pct.get_width() + 18

        pg.draw.line(screen, (30, 41, 59), (x - 9, 6), (x - 9, self.top_bar_height - 7), 1)

        # 4. Swarm Escorts & Hostiles
        alive_escorts = simulation.get_number_running_simultations()
        total_escorts = simulation.num_loyalwingman
        t_esc_lbl = self.font_label.render("ESCORTS:", True, (100, 116, 139))
        t_esc_val = self.font_mono.render(f"{alive_escorts}/{total_escorts}", True, (56, 189, 248))
        screen.blit(t_esc_lbl, (x, y_text + 1))
        x += t_esc_lbl.get_width() + 5
        screen.blit(t_esc_val, (x, y_text))
        x += t_esc_val.get_width() + 18

        pg.draw.line(screen, (30, 41, 59), (x - 9, 6), (x - 9, self.top_bar_height - 7), 1)

        # 5. Threats
        act_threats = len(simulation.kamikazes)
        kia_threats = simulation.get_kamikazes_destroyed()
        t_th_lbl = self.font_label.render("THREATS:", True, (100, 116, 139))
        t_th_val = self.font_mono.render(f"{act_threats} ACT | {kia_threats} KIA", True, (248, 113, 113) if act_threats > 0 else (148, 163, 184))
        screen.blit(t_th_lbl, (x, y_text + 1))
        x += t_th_lbl.get_width() + 5
        screen.blit(t_th_val, (x, y_text))
        x += t_th_val.get_width() + 18

        pg.draw.line(screen, (30, 41, 59), (x - 9, 6), (x - 9, self.top_bar_height - 7), 1)

        # 6. Leader & Formation
        leader_alive = simulation.leadingdrone is not None and getattr(simulation.leadingdrone, 'destroyed', False) is not True
        form_name = getattr(simulation.leadingdrone, 'current_formation_name', 'CIRCLE') if simulation.leadingdrone else 'NONE'
        t_lead_lbl = self.font_label.render("LEADER:", True, (100, 116, 139))
        t_lead_val = self.font_mono.render(f"{'ACTIVE' if leader_alive else 'MIA'} [{form_name}]", True, (74, 222, 128) if leader_alive else (248, 113, 113))
        screen.blit(t_lead_lbl, (x, y_text + 1))
        x += t_lead_lbl.get_width() + 5
        screen.blit(t_lead_val, (x, y_text))
        x += t_lead_val.get_width() + 18

        # 6.5 LLM Autonomous Commander Status
        if hasattr(simulation, 'llm_commander') and simulation.llm_commander is not None:
            llm_stat = simulation.llm_commander.get_hud_status()
            llm_on = llm_stat.get("enabled", False)
            llm_flight = llm_stat.get("in_flight", False)
            engine_name = llm_stat.get("engine", "laya").upper()
            llm_text = "EVAL..." if llm_flight else (f"{engine_name}: ON" if llm_on else f"{engine_name}: OFF")
            llm_col = (250, 204, 21) if llm_flight else ((56, 189, 248) if llm_on else (100, 116, 139))

            pg.draw.line(screen, (30, 41, 59), (x - 9, 6), (x - 9, self.top_bar_height - 7), 1)
            t_llm_lbl = self.font_label.render("COMMAND:", True, (100, 116, 139))
            t_llm_val = self.font_mono.render(llm_text, True, llm_col)
            screen.blit(t_llm_lbl, (x, y_text + 1))
            x += t_llm_lbl.get_width() + 5
            screen.blit(t_llm_val, (x, y_text))
            x += t_llm_val.get_width() + 18

        # 7. Iteration / Episode (Far Right)
        iter_str = f"EPISODE #{history.iterations + 1}  |  ZOOM {display_manager.zoom_level:.2f}x"
        t_iter = self.font_mono_small.render(iter_str, True, (100, 116, 139))
        screen.blit(t_iter, (self.screen_width - t_iter.get_width() - 16, y_text + 1))

    def _draw_bottom_toolbar(self, screen, simulation):
        """
        High-density flush bottom command line anchored to the window bottom.
        Replaces floating dynamic islands with an integrated, single-line professional CAD/C2 status bar.
        """
        pg.draw.rect(screen, (10, 14, 22), self.bottom_bar_rect)
        pg.draw.line(screen, (30, 41, 59), (0, self.bottom_bar_rect.top), (self.screen_width, self.bottom_bar_rect.top), 1)

        shortcuts = [
            ("SPACE", "Pause/Resume"),
            ("1-4", "Formation"),
            ("L", "Toggle AI"),
            ("M", "Switch Engine"),
            ("L-Click", "Select/Move"),
            ("R-Click", "Spawn Threat"),
            ("C", "Center View"),
            ("0", "Reset"),
            ("D", "Perimeters"),
            ("+/-", "Speed"),
            ("P", "Export Plot"),
            ("H", "Toggle HUD")
        ]

        cx = 16
        y_text = self.bottom_bar_rect.top + 5

        for key, label in shortcuts:
            k_surf = self.font_key.render(f"[{key}]", True, (241, 245, 249))
            l_surf = self.font_meta.render(label, True, (100, 116, 139))
            screen.blit(k_surf, (cx, y_text))
            cx += k_surf.get_width() + 4
            screen.blit(l_surf, (cx, y_text))
            cx += l_surf.get_width() + 16

            # Subtle dot separator
            if key != shortcuts[-1][0]:
                pg.draw.circle(screen, (51, 65, 85), (cx - 8, y_text + 7), 1)

    def _draw_minimap_radar(self, screen, simulation, display_manager):
        """
        Renders a crisp, rectangular radar scope docked on the right rail.
        Gridlines represent tactical coordinate sectors without gratuitous sci-fi styling.
        """
        rx, ry, rw, rh = self.minimap_rect.x, self.minimap_rect.y, self.minimap_rect.width, self.minimap_rect.height

        # Header bar
        header_h = 24
        pg.draw.rect(screen, (15, 23, 42), (rx, ry - header_h, rw, header_h))
        pg.draw.rect(screen, (30, 41, 59), (rx, ry - header_h, rw, header_h), 1)
        t_header = self.font_label.render("TACTICAL RADAR SCOPE", True, (148, 163, 184))
        screen.blit(t_header, (rx + 10, ry - header_h + 4))

        # Radar Scope Body
        scope_bg = (8, 12, 18)
        border_col = (56, 189, 248) if self.is_hovering_minimap else (30, 41, 59)
        pg.draw.rect(screen, scope_bg, self.minimap_rect)
        pg.draw.rect(screen, border_col, self.minimap_rect, 1)

        sx = rw / WORLD_WIDTH
        sy = rh / WORLD_HEIGHT

        # 4x2 Technical Coordinate Grid
        for gx in [0.25, 0.5, 0.75]:
            px = rx + int(rw * gx)
            pg.draw.line(screen, (18, 26, 38), (px, ry), (px, ry + rh), 1)
        for gy in [0.333, 0.666]:
            py = ry + int(rh * gy)
            pg.draw.line(screen, (18, 26, 38), (rx, py), (rx + rw, py), 1)

        # Combat Delimitation Line (Defense Perimeter at 1/3 world)
        bound_x = rx + int((WORLD_WIDTH / 3) * sx)
        pg.draw.line(screen, (22, 60, 36), (bound_x, ry), (bound_x, ry + rh), 1)

        # Protected Area (Base)
        if simulation.protected_area:
            pa_pos = simulation.protected_area.coordenates
            mx = rx + int(pa_pos.x * sx)
            my = ry + int(pa_pos.y * sy)
            mr = max(2, int(simulation.protected_area.radius * sx))
            pg.draw.circle(screen, (74, 222, 128), (mx, my), mr, width=1)

        # Swarm Wingmen (Sky Blue)
        for wingman in simulation.swarm:
            wx = rx + int(wingman.location.x * sx)
            wy = ry + int(wingman.location.y * sy)
            pg.draw.circle(screen, (56, 189, 248), (wx, wy), 2)

        # Kamikazes (Red)
        for kamikaze in simulation.kamikazes:
            kx = rx + int(kamikaze.location.x * sx)
            ky = ry + int(kamikaze.location.y * sy)
            pg.draw.circle(screen, (248, 113, 113), (kx, ky), 2)

        # Leading Drone (Amber)
        if simulation.leadingdrone:
            lx = rx + int(simulation.leadingdrone.location.x * sx)
            ly = ry + int(simulation.leadingdrone.location.y * sy)
            pg.draw.circle(screen, (251, 191, 36), (lx, ly), 3)

        # Camera Viewport Frustum Box
        zoom = display_manager.zoom_level
        offset = display_manager.offset
        cam_wx = -offset.x / zoom
        cam_wy = -offset.y / zoom
        cam_ww = display_manager.screen_width / zoom
        cam_wh = display_manager.screen_height / zoom

        f_rx = rx + int(cam_wx * sx)
        f_ry = ry + int(cam_wy * sy)
        f_rw = max(4, int(cam_ww * sx))
        f_rh = max(4, int(cam_wh * sy))

        frustum_rect = pg.Rect(f_rx, f_ry, f_rw, f_rh).clamp(self.minimap_rect)
        pg.draw.rect(screen, (148, 163, 184), frustum_rect, width=1)

    def _draw_agent_inspector(self, screen, simulation):
        """
        Renders a crisp rectangular MFD (Multi-Function Display) agent inspector on the right rail.
        High density, strict key-value typography, zero cartoon markers.
        """
        agent = self.selected_agent
        card_rect = self.inspector_rect
        rx, ry, rw, rh = card_rect.x, card_rect.y, card_rect.width, card_rect.height

        accent_color = (251, 191, 36) if self.selected_type == "Leading Drone" else \
                       (56, 189, 248) if self.selected_type == "Loyal Wingman" else \
                       (248, 113, 113) if self.selected_type == "Kamikaze Threat" else (74, 222, 128)

        # Panel frame
        pg.draw.rect(screen, (10, 14, 22), card_rect)
        pg.draw.rect(screen, (30, 41, 59), card_rect, 1)

        # Top Title Header
        header_h = 28
        pg.draw.rect(screen, (15, 23, 42), (rx, ry, rw, header_h))
        pg.draw.line(screen, (30, 41, 59), (rx, ry + header_h), (rx + rw, ry + header_h), 1)

        # Identification Tag
        iff_tag = "COMMAND" if self.selected_type == "Leading Drone" else \
                  f"LW-{self.selected_index:02d}" if self.selected_type == "Loyal Wingman" else \
                  f"THREAT-{self.selected_index:02d}" if self.selected_type == "Kamikaze Threat" else "DEFENSE ASSET"

        t_title = self.font_header.render(f"TELEMETRY // {iff_tag}", True, accent_color)
        screen.blit(t_title, (rx + 10, ry + 6))

        # Close button [×]
        close_bg = (50, 20, 20) if self.is_hovering_close else (20, 28, 42)
        pg.draw.rect(screen, close_bg, self.inspector_close_rect)
        pg.draw.rect(screen, (51, 65, 85), self.inspector_close_rect, 1)
        t_x = self.font_mono.render("x", True, (241, 245, 249))
        screen.blit(t_x, (self.inspector_close_rect.x + 5, self.inspector_close_rect.y + 1))

        # Kinematics & Brain Data
        y = ry + header_h + 10

        # AI Behavior State
        state_name = "CRUISE_ESCORT"
        if hasattr(agent, 'behavior') and agent.behavior is not None:
            if hasattr(agent.behavior, 'get_current_state'):
                state_name = agent.behavior.get_current_state()
            elif hasattr(agent.behavior, 'node_name'):
                state_name = agent.behavior.node_name

        loc = getattr(agent, 'location', getattr(agent, 'coordenates', vec2(0, 0)))
        vel = getattr(agent, 'velocity', vec2(0, 0))
        speed = vel.length() if hasattr(vel, 'length') else 0.0

        state_color = (239, 68, 68) if state_name == "SacrificialRamming" else (241, 245, 249)
        rows = [
            ("IFF STATUS:", self.selected_type.upper(), accent_color),
            ("BRAIN STATE:", state_name, state_color),
            ("POSITION:", f"X:{loc.x:05.1f}  Y:{loc.y:05.1f}", (241, 245, 249)),
            ("VELOCITY:", f"{speed:04.2f} px/f", (241, 245, 249)),
        ]

        if simulation.leadingdrone is not None and hasattr(simulation.leadingdrone, 'location'):
            dist_lead = loc.distance_to(simulation.leadingdrone.location)
            rows.append(("RNG TO LEADER:", f"{dist_lead:05.1f} px", (241, 245, 249)))

        if self.selected_type == "Leading Drone":
            form_name = getattr(agent, 'current_formation_name', 'CIRCLE')
            rows.append(("FORMATION:", f"{form_name}", (56, 189, 248)))

        elif self.selected_type == "Loyal Wingman":
            role = getattr(agent, 'tactical_role', 'INTERCEPTOR')
            rows.append(("TAC ROLE:", f"{role}", (56, 189, 248) if role == "INTERCEPTOR" else (251, 191, 36)))

            assigned = getattr(agent, 'assigned_threat', None)
            if assigned is not None and hasattr(assigned, 'location'):
                tgt_dist = loc.distance_to(assigned.location)
                rows.append(("TARGET LOCK:", f"DIST {tgt_dist:05.1f} px", (248, 113, 113)))
            else:
                rows.append(("TARGET LOCK:", "STANDBY / FORMATION", (100, 116, 139)))

        val_x = rx + 125
        for lbl, val, val_col in rows:
            t_lbl = self.font_label.render(lbl, True, (100, 116, 139))
            t_val = self.font_mono.render(val, True, val_col)
            screen.blit(t_lbl, (rx + 10, y))
            screen.blit(t_val, (val_x, y))
            y += 21

        # Weapons Inventory for Wingman
        if self.selected_type == "Loyal Wingman":
            y += 6
            pg.draw.line(screen, (30, 41, 59), (rx + 10, y), (rx + rw - 10, y), 1)
            y += 10

            t_wep_head = self.font_label.render("PAYLOAD INVENTORY & AMMO", True, (148, 163, 184))
            screen.blit(t_wep_head, (rx + 10, y))
            y += 20

            # Vaporizer
            vap_ammo = agent.vaporizer_gun.get_ammo_available() if hasattr(agent, 'vaporizer_gun') else 0
            v_avail = getattr(agent.vaporizer_gun, 'available', True) if hasattr(agent, 'vaporizer_gun') else False
            self._draw_compact_weapon_row(screen, rx + 10, y, rw - 20, "VAPORIZER [100px]", vap_ammo, 10, (56, 189, 248), v_avail)
            y += 28

            # Freezing
            frz_ammo = agent.freezing_gun.get_ammo_available() if hasattr(agent, 'freezing_gun') else 0
            f_avail = getattr(agent.freezing_gun, 'available', True) if hasattr(agent, 'freezing_gun') else False
            self._draw_compact_weapon_row(screen, rx + 10, y, rw - 20, "FREEZING  [300px]", frz_ammo, 10, (74, 222, 128), f_avail)

        elif self.selected_type == "Protected Area":
            y += 6
            pg.draw.line(screen, (30, 41, 59), (rx + 10, y), (rx + rw - 10, y), 1)
            y += 10
            t_life = self.font_mono.render(f"INTEGRITY: {agent.life:.1f}%", True, (74, 222, 128) if agent.life > 30 else (248, 113, 113))
            screen.blit(t_life, (rx + 10, y))

    def _draw_compact_weapon_row(self, screen, x, y, max_w, name, ammo, max_ammo, pip_color, is_ready):
        """Draws a clean tabular weapon row with discrete tactical ammo pips."""
        t_name = self.font_mono_small.render(name, True, (203, 213, 225))
        screen.blit(t_name, (x, y))

        stat_str = "RDY" if is_ready else "RLD"
        stat_col = (74, 222, 128) if is_ready else (251, 191, 36)
        t_stat = self.font_mono_small.render(stat_str, True, stat_col)
        screen.blit(t_stat, (x + max_w - t_stat.get_width(), y))

        # Ammo pips
        pip_w, pip_h = 10, 6
        pip_gap = 3
        pip_y = y + 14

        for i in range(max_ammo):
            px = x + i * (pip_w + pip_gap)
            if i < ammo:
                pg.draw.rect(screen, pip_color, (px, pip_y, pip_w, pip_h))
            else:
                pg.draw.rect(screen, (20, 28, 42), (px, pip_y, pip_w, pip_h))
                pg.draw.rect(screen, (51, 65, 85), (px, pip_y, pip_w, pip_h), 1)

        t_cnt = self.font_mono_small.render(f"{ammo:02d}/{max_ammo:02d}", True, (148, 163, 184))
        screen.blit(t_cnt, (x + max_ammo * (pip_w + pip_gap) + 14, pip_y - 2))

    def _draw_ai_commander_card(self, screen, simulation):
        """
        Renders a dedicated tactical HUD card for the AI Commander (Qwen 3.5 SLM).
        Displays real-time tactical decisions: formation doctrine, role distribution,
        priority target locks, leader action, inference latency, and operational rationale.
        """
        commander = simulation.llm_commander
        if commander is None:
            return

        summary = commander.get_status_summary()

        # Layout parameters (top-left, docked below top status bar)
        card_x = 16
        card_y = self.top_bar_height + 10
        card_w = 400
        card_h = 175 if summary["enabled"] else 68
        card_rect = pg.Rect(card_x, card_y, card_w, card_h)

        # Background panel & border
        pg.draw.rect(screen, (10, 14, 22), card_rect)
        pg.draw.rect(screen, (30, 41, 59), card_rect, 1)

        # Header bar
        header_h = 26
        pg.draw.rect(screen, (15, 23, 42), (card_x, card_y, card_w, header_h))
        pg.draw.line(screen, (30, 41, 59), (card_x, card_y + header_h), (card_x + card_w, card_y + header_h), 1)

        # Header title
        engine_label = summary.get("engine_label", "LAYA [MPS]" if summary.get("engine") == "laya" else "QWEN 3.5 [LM]")
        t_header = self.font_header.render(f"AI COMMANDER // {engine_label}", True, (251, 191, 36) if summary["enabled"] else (148, 163, 184))
        screen.blit(t_header, (card_x + 10, card_y + 5))

        # Status Pill (Right side of header)
        if not summary["enabled"]:
            pill_text = "OFFLINE [L]"
            pill_bg = (30, 41, 59)
            pill_border = (51, 65, 85)
            pill_fg = (148, 163, 184)
        elif summary["is_thinking"]:
            # Pulsing amber indicator
            alpha_pulse = int(180 + 75 * math.sin(self.pulse_phase * 2.5))
            pill_text = "EVALUATING..."
            pill_bg = (66, 32, 6)
            pill_border = (251, 191, 36)
            pill_fg = (251, 191, 36)
        else:
            pill_text = "ACTIVE"
            pill_bg = (8, 47, 73)
            pill_border = (56, 189, 248)
            pill_fg = (56, 189, 248)

        t_pill = self.font_key.render(pill_text, True, pill_fg)
        pw = t_pill.get_width() + 12
        ph = 18
        px = card_x + card_w - pw - 8
        py = card_y + 4
        pg.draw.rect(screen, pill_bg, (px, py, pw, ph), border_radius=3)
        pg.draw.rect(screen, pill_border, (px, py, pw, ph), width=1, border_radius=3)
        screen.blit(t_pill, (px + 6, py + 2))

        # Card body content
        if not summary["enabled"]:
            msg = self.font_meta.render(f"Offline. Press [L] to activate, [M] to toggle engine ({engine_label}).", True, (100, 116, 139))
            screen.blit(msg, (card_x + 12, card_y + header_h + 10))
            return

        # Rows when active
        y = card_y + header_h + 8
        val_x = card_x + 120

        form_val = summary["last_formation"]
        n_inter = summary["num_interceptors"]
        n_escort = summary["num_close_escorts"]
        roles_val = f"{n_inter} INT / {n_escort} ESC" if (n_inter + n_escort) > 0 else "BALANCED / AUTO"
        target_val = summary["last_target"]
        action_val = summary["last_action"]
        if summary["last_latency"] > 0:
            if summary.get("engine") == "laya":
                lat_val = f"{summary['last_latency']*1000:.0f}ms"
            else:
                lat_val = f"{summary['last_latency']:.2f}s"
        else:
            lat_val = "BENCHMARKING"
        cycle_val = f"#{summary['total_decisions']} ({lat_val})"

        rows = [
            ("FORMATION:", form_val, (56, 189, 248)),
            ("ROLE SPLIT:", roles_val, (74, 222, 128)),
            ("PRIORITY TGT:", target_val, (248, 113, 113) if target_val != "N/A" else (148, 163, 184)),
            ("LEAD ACTION:", action_val, (251, 191, 36)),
            ("CYCLE / LAT:", cycle_val, (148, 163, 184)),
        ]

        for lbl, val, col in rows:
            t_lbl = self.font_label.render(lbl, True, (100, 116, 139))
            t_val = self.font_mono.render(val, True, col)
            screen.blit(t_lbl, (card_x + 10, y))
            screen.blit(t_val, (val_x, y))
            y += 18

        # Divider line
        y += 2
        pg.draw.line(screen, (30, 41, 59), (card_x + 10, y), (card_x + card_w - 10, y), 1)
        y += 5

        # Tactical Rationale quote (trimmed/wrapped cleanly)
        rationale_raw = summary["rationale"] or "Establishing air supremacy perimeter..."
        # Wrap rationale text to fit card width
        words = rationale_raw.split()
        lines = []
        curr_line = ""
        for word in words:
            test_line = f"{curr_line} {word}".strip()
            if self.font_meta.size(test_line)[0] < (card_w - 24):
                curr_line = test_line
            else:
                if curr_line:
                    lines.append(curr_line)
                curr_line = word
            if len(lines) >= 2:
                break
        if curr_line and len(lines) < 2:
            lines.append(curr_line)

        # Truncate second line if still more words exist
        if len(lines) == 2 and words.index(lines[-1].split()[-1]) < len(words) - 1:
            lines[-1] = lines[-1][:45].rstrip() + "..."

        for r_line in lines:
            t_rat = self.font_meta.render(f"\"{r_line}\"" if r_line == lines[0] else f" {r_line}\"", True, (203, 213, 225))
            screen.blit(t_rat, (card_x + 12, y))
            y += 15

