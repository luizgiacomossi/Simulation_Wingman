import pygame
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, WORLD_WIDTH, WORLD_HEIGHT, LIGHT_BLUE

class DisplayManager(object):
    """
    Manages display rendering, surfaces, zoom and pan camera mechanics.
    Automatically detects laptop screen resolution and supports dynamic resizing.
    """
    def __init__(self, screen_width=None, screen_height=None,
                 world_width=WORLD_WIDTH, world_height=WORLD_HEIGHT):
        pygame.init()
        if not pygame.display.get_init():
            pygame.display.init()

        self.font15 = pygame.font.SysFont(None, 15)
        self.font20 = pygame.font.SysFont(None, 20)
        self.font24 = pygame.font.SysFont(None, 24)

        self.world_width = world_width
        self.world_height = world_height

        # Automatically match laptop screen resolution
        if screen_width is None or screen_height is None:
            info = pygame.display.Info()
            if info.current_w > 0 and info.current_h > 0:
                self.screen_width = max(800, info.current_w - 70)
                self.screen_height = max(550, info.current_h - 100)
            else:
                self.screen_width = SCREEN_WIDTH
                self.screen_height = SCREEN_HEIGHT
        else:
            self.screen_width = screen_width
            self.screen_height = screen_height

        self.size = (self.screen_width, self.screen_height)
        self.clock = pygame.time.Clock()
        self.screen = pygame.display.set_mode(self.size, pygame.RESIZABLE | pygame.SRCALPHA)
        pygame.display.set_caption("Loyal Wingman MUM-T Air Defense Simulator")

        # World surface on which the entire simulation is drawn before viewport scaling
        self.world_surface = pygame.Surface((self.world_width, self.world_height), depth=24)

        # Responsive zoom to comfortably fit world inside the laptop window
        fit_zoom = min(self.screen_width / self.world_width, self.screen_height / self.world_height)
        self.zoom_level = min(1.0, fit_zoom)
        self.offset = pygame.math.Vector2(
            (self.screen_width - self.world_width * self.zoom_level) / 2,
            (self.screen_height - self.world_height * self.zoom_level) / 2
        )
        self.min_zoom = fit_zoom * 0.4
        self.max_zoom = 4.0

        # Panning state
        self.is_panning = False
        self.pan_start = pygame.math.Vector2(0, 0)

        # Text rendering surface cache
        self._text_cache = {}

        # Background texture
        self.background_image = None
        try:
            bg = pygame.image.load("models/texture/camouflage.png").convert()
            self.background_image = pygame.transform.scale(bg, (self.world_width, self.world_height))
        except Exception as e:
            print(f"Notice: Camouflage texture not loaded ({e}), using default background.")

    def handle_event(self, event):
        """
        Processes camera interaction events (mouse wheel zoom, middle click pan).
        """
        # Window Resize
        if event.type == pygame.VIDEORESIZE:
            self.resize_display(event.w, event.h)
            return

        # Mouse Wheel Zoom
        if event.type == pygame.MOUSEWHEEL:
            old_zoom = self.zoom_level
            if event.y > 0:
                self.zoom_level *= 1.1
            else:
                self.zoom_level /= 1.1
            self.zoom_level = max(self.min_zoom, min(self.max_zoom, self.zoom_level))

            mouse_x, mouse_y = pygame.mouse.get_pos()
            world_x = (mouse_x - self.offset.x) / old_zoom
            world_y = (mouse_y - self.offset.y) / old_zoom

            self.offset.x = mouse_x - world_x * self.zoom_level
            self.offset.y = mouse_y - world_y * self.zoom_level
            self.clamp_offset()

        # Middle Mouse Button Pan
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
            self.is_panning = True
            self.pan_start = pygame.math.Vector2(pygame.mouse.get_pos())
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 2:
            self.is_panning = False
        elif event.type == pygame.MOUSEMOTION and self.is_panning:
            current_mouse = pygame.math.Vector2(pygame.mouse.get_pos())
            delta = current_mouse - self.pan_start
            self.offset += delta
            self.pan_start = current_mouse
            self.clamp_offset()

    def clamp_offset(self):
        curr_w = self.world_width * self.zoom_level
        curr_h = self.world_height * self.zoom_level

        if curr_w >= self.screen_width:
            self.offset.x = max(self.screen_width - curr_w, min(0, self.offset.x))
        else:
            self.offset.x = (self.screen_width - curr_w) / 2

        if curr_h >= self.screen_height:
            self.offset.y = max(self.screen_height - curr_h, min(0, self.offset.y))
        else:
            self.offset.y = (self.screen_height - curr_h) / 2

    def center_on(self, world_pos):
        """Centers the camera on a specific world position."""
        self.offset.x = self.screen_width / 2 - world_pos.x * self.zoom_level
        self.offset.y = self.screen_height / 2 - world_pos.y * self.zoom_level
        self.clamp_offset()

    def resize_display(self, new_w, new_h):
        """Dynamically resizes screen and recalculates bounds when window is resized."""
        self.screen_width = max(640, new_w)
        self.screen_height = max(480, new_h)
        self.size = (self.screen_width, self.screen_height)
        self.screen = pygame.display.set_mode(self.size, pygame.RESIZABLE | pygame.SRCALPHA)
        fit_zoom = min(self.screen_width / self.world_width, self.screen_height / self.world_height)
        self.min_zoom = fit_zoom * 0.4
        self.clamp_offset()

    def reset_view(self):
        """Resets camera to fit the laptop screen comfortably."""
        fit_zoom = min(self.screen_width / self.world_width, self.screen_height / self.world_height)
        self.zoom_level = min(1.0, fit_zoom)
        self.offset = pygame.math.Vector2(
            (self.screen_width - self.world_width * self.zoom_level) / 2,
            (self.screen_height - self.world_height * self.zoom_level) / 2
        )
        self.clamp_offset()

    def screen_to_world(self, screen_pos):
        return (screen_pos - self.offset) / self.zoom_level

    def world_to_screen(self, world_pos):
        return world_pos * self.zoom_level + self.offset

    def clear_world(self):
        if self.background_image is not None:
            self.world_surface.blit(self.background_image, (0, 0))
        else:
            self.world_surface.fill((40, 44, 52))

    def get_rendered_text(self, font, text: str, color):
        """Caches rendered font surfaces to avoid re-rasterizing static strings every frame."""
        key = (id(font), text, color)
        surf = self._text_cache.get(key)
        if surf is None:
            surf = font.render(text, True, color)
            self._text_cache[key] = surf
        return surf

    def render_to_screen(self):
        """
        Transfers the world surface to the visible display screen using viewport clipping.
        """
        zoom = self.zoom_level
        offset = self.offset

        # Fast path: 1.0x unshifted zoom avoids expensive transform.scale on 1.7M pixels
        if abs(zoom - 1.0) < 0.001 and abs(offset.x) < 0.001 and abs(offset.y) < 0.001 and self.screen_width == self.world_width and self.screen_height == self.world_height:
            self.screen.blit(self.world_surface, (0, 0))
            return

        self.screen.fill((25, 25, 28))

        if zoom > 1.0:
            wx = -offset.x / zoom
            wy = -offset.y / zoom
            ww = self.screen_width / zoom
            wh = self.screen_height / zoom

            wx = max(0, wx)
            wy = max(0, wy)
            ww = min(ww, self.world_width - wx)
            wh = min(wh, self.world_height - wy)

            if ww > 0 and wh > 0:
                try:
                    subsurf = self.world_surface.subsurface(pygame.Rect(wx, wy, ww, wh))
                    scaled_surf = pygame.transform.scale(subsurf, (int(ww * zoom), int(wh * zoom)))
                    self.screen.blit(scaled_surf, (0, 0))
                except Exception:
                    pass
        else:
            scaled_surface = pygame.transform.scale(
                self.world_surface,
                (int(self.world_width * zoom), int(self.world_height * zoom))
            )
            self.screen.blit(scaled_surface, offset)

    def WriteLegendOnCanvas(self, simulation, accelerated_factor, time_running, history):
        """Draws HUD telemetry and Tactical Inspector directly onto the unscaled screen."""
        if hasattr(simulation, 'gui_manager') and simulation.gui_manager is not None:
            simulation.gui_manager.draw_screen_hud(self.screen, simulation, self, time_running, history)
        else:
            img = self.get_rendered_text(self.font24, 'Loyal Wingman Simulation', LIGHT_BLUE)
            self.screen.blit(img, (20, 20))
