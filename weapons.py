from random import uniform
from typing import List, Optional, Any, Union, Tuple
import pygame as pg
from pygame.math import Vector2
from constants import PROB_VAPORIZER, PROB_FREEZING, SAMPLE_TIME, SIZE_DRONE

class Projectile(object):
    """
    Physical projectile entity with ballistic kinematics, finite lifetime,
    collision radius, and dynamic visual tracer trail.
    """
    def __init__(self,
                 origin: Union[Vector2, Tuple[float, float], Any],
                 target_pos: Union[Vector2, Tuple[float, float], Any],
                 speed: float,
                 max_range: float,
                 radius: float = 6.0,
                 target_entity: Optional[Any] = None,
                 shooter: Optional[Any] = None,
                 color: Tuple[int, int, int] = (255, 200, 50),
                 tracer_length: int = 6):
        self.position = Vector2(origin.x, origin.y) if hasattr(origin, 'x') else Vector2(origin[0], origin[1])
        t_pos = Vector2(target_pos.x, target_pos.y) if hasattr(target_pos, 'x') else Vector2(target_pos[0], target_pos[1])
        
        # Calculate lead pursuit if target entity has velocity
        aim_pos = t_pos
        if target_entity is not None and hasattr(target_entity, 'velocity'):
            t_flight = (t_pos - self.position).length() / max(1.0, speed)
            aim_pos = t_pos + target_entity.velocity * t_flight

        diff = aim_pos - self.position
        dist = diff.length()
        if dist > 1e-4:
            self.direction = diff.normalize()
        else:
            self.direction = Vector2(1, 0)

        self.velocity = self.direction * speed
        self.speed = speed
        self.max_range = max_range
        self.distance_traveled = 0.0
        self.radius = radius
        self.shooter = shooter
        self.target_entity = target_entity
        self.color = color
        self.tracer_length = tracer_length
        self.trail: List[Vector2] = [Vector2(self.position.x, self.position.y)]
        self.alive = True

    def update(self, dt: float):
        if not self.alive:
            return
        step = self.velocity * dt
        self.position += step
        self.distance_traveled += step.length()

        # Update tracer trail
        self.trail.append(Vector2(self.position.x, self.position.y))
        if len(self.trail) > self.tracer_length:
            self.trail.pop(0)

        # Range cutoff check
        if self.distance_traveled >= self.max_range:
            self.alive = False

    def draw(self, surface, display_manager=None):
        """
        Renders luminous projectile head and multi-segment dynamic tracer wake.
        Gracefully returns if surface is None (headless simulation mode).
        """
        if surface is None or not self.alive:
            return

        # Render gradient tracer wake
        n_trail = len(self.trail)
        if n_trail >= 2:
            for i in range(n_trail - 1):
                p1 = self.trail[i]
                p2 = self.trail[i + 1]
                factor = (i + 1) / n_trail
                segment_color = (
                    int(self.color[0] * factor),
                    int(self.color[1] * factor),
                    int(self.color[2] * factor)
                )
                width = max(1, int(3 * factor))
                pg.draw.line(surface, segment_color, p1, p2, width)

        # Render projectile head and incandescent core
        pg.draw.circle(surface, self.color, (int(self.position.x), int(self.position.y)), int(self.radius * 0.6))
        pg.draw.circle(surface, (255, 255, 255), (int(self.position.x), int(self.position.y)), max(1, int(self.radius * 0.3)))

    def on_hit(self, target: Any, swarm_manager: Any) -> bool:
        """Executed upon physical collision with a target entity."""
        raise NotImplementedError("Subclasses must implement on_hit.")


class VaporizerBolt(Projectile):
    """
    High-energy directed railgun / plasma bolt.
    Lethal kinetic projectile traveling at high velocity with fiery orange-gold tracer.
    """
    def __init__(self,
                 origin: Any,
                 target_pos: Any,
                 target_entity: Optional[Any] = None,
                 shooter: Optional[Any] = None,
                 speed: float = 850.0,
                 max_range: float = 160.0):
        super().__init__(
            origin=origin,
            target_pos=target_pos,
            speed=speed,
            max_range=max_range,
            radius=8.0,
            target_entity=target_entity,
            shooter=shooter,
            color=(255, 190, 40),
            tracer_length=5
        )

    def on_hit(self, target: Any, swarm_manager: Any, force_hit: bool = False) -> bool:
        self.alive = False
        hit_prob = uniform(0.0, 1.0)
        if force_hit or hit_prob < PROB_VAPORIZER:
            # Fatal impact: detonates enemy kamikaze
            target.destroyed = True
            target.explode = True
            return True
        return False


class FreezingBolt(Projectile):
    """
    Cryogenic non-lethal stasis pulse.
    Propagates at moderate velocity with electric ice-cyan visual tracer.
    Slows down target on impact.
    """
    def __init__(self,
                 origin: Any,
                 target_pos: Any,
                 target_entity: Optional[Any] = None,
                 shooter: Optional[Any] = None,
                 speed: float = 650.0,
                 max_range: float = 350.0):
        super().__init__(
            origin=origin,
            target_pos=target_pos,
            speed=speed,
            max_range=max_range,
            radius=7.0,
            target_entity=target_entity,
            shooter=shooter,
            color=(80, 225, 255),
            tracer_length=6
        )

    def on_hit(self, target: Any, swarm_manager: Any, force_hit: bool = False) -> bool:
        self.alive = False
        hit_prob = uniform(0.0, 1.0)
        if force_hit or hit_prob < PROB_FREEZING:
            if hasattr(target, 'slow_down'):
                target.slow_down()
            return True
        return False


class Weapon(object):
    """
    Abstract base class for drone weapon systems.
    Adheres to the Liskov Substitution Principle (LSP) with uniform interface.
    """
    def __init__(self,
                 cooldown: float,
                 num_cartridges: int,
                 rate_of_fire: float,
                 range_of_fire: float,
                 target_list: Optional[List[Any]] = None,
                 owner: Optional[Any] = None):
        self.cooldown = cooldown
        self.num_cartridges = num_cartridges
        self.max_cartridges = num_cartridges
        self.rate_of_fire = rate_of_fire
        self.range_of_fire = range_of_fire
        self.kamikazes = target_list if target_list is not None else []
        self.owner = owner
        self.available = True

    def fire(self, target: Optional[Union[int, Any]] = None, origin: Optional[Any] = None) -> Optional[Projectile]:
        """
        Attempts to discharge the weapon against a target entity or index.
        Spawns and returns a kinematic Projectile instance on success.
        """
        raise NotImplementedError("Weapon subclasses must implement fire(target).")

    def _resolve_target(self, target: Optional[Union[int, Any]] = None, origin: Optional[Any] = None):
        """Resolves origin vector, target position vector, and target entity object."""
        # 1. Resolve origin
        if origin is not None:
            pos_origin = Vector2(origin.x, origin.y) if hasattr(origin, 'x') else Vector2(origin[0], origin[1])
        elif self.owner is not None and hasattr(self.owner, 'location'):
            pos_origin = Vector2(self.owner.location.x, self.owner.location.y)
        else:
            pos_origin = Vector2(0, 0)

        # 2. Resolve target entity and target position
        target_entity = None
        target_pos = None

        if isinstance(target, int):
            if 0 <= target < len(self.kamikazes):
                target_entity = self.kamikazes[target]
                target_pos = Vector2(target_entity.location.x, target_entity.location.y)
        elif target is not None and hasattr(target, 'location'):
            target_entity = target
            target_pos = Vector2(target.location.x, target.location.y)
        elif target is not None and (isinstance(target, Vector2) or isinstance(target, tuple) or isinstance(target, list)):
            target_pos = Vector2(target[0], target[1])
            for k in self.kamikazes:
                if (k.location - target_pos).length() < 1e-2:
                    target_entity = k
                    break
        elif self.kamikazes:
            target_entity = self.kamikazes[0]
            target_pos = Vector2(target_entity.location.x, target_entity.location.y)
        else:
            target_pos = pos_origin + Vector2(self.range_of_fire, 0)

        return pos_origin, target_pos, target_entity

    def receive_list_kamikazes(self, list_kamikazes: List[Any]):
        """Updates internal reference to the current threat pool."""
        self.kamikazes = list_kamikazes

    def reload(self):
        """Replenishes weapon ammo or resets cooldown cycle."""
        self.available = True

    def rearm(self, amount: Optional[int] = None):
        """Replenishes weapon cartridges back to full capacity or specified amount."""
        if amount is not None:
            self.num_cartridges = amount
        else:
            self.num_cartridges = getattr(self, 'max_cartridges', 10)
        self.available = True

    def get_ammo_available(self) -> int:
        """Returns the current ammunition count."""
        return self.num_cartridges


class Vaporizer(Weapon):
    """
    High-energy lethal directed-energy railgun / plasma weapon.
    Fires physical VaporizerBolt projectiles with ballistic kinematics.
    """
    def __init__(self, cooldown: float, num_cartridges: int, rate_of_fire: float,
                 range_of_fire: float, target_list: Optional[List[Any]] = None,
                 owner: Optional[Any] = None):
        super().__init__(cooldown, num_cartridges, rate_of_fire, range_of_fire, target_list, owner)

    def fire(self, target: Optional[Union[int, Any]] = None, origin: Optional[Any] = None) -> Optional[VaporizerBolt]:
        if self.num_cartridges <= 0:
            return None

        pos_origin, target_pos, target_entity = self._resolve_target(target, origin)
        self.num_cartridges -= 1

        bolt = VaporizerBolt(
            origin=pos_origin,
            target_pos=target_pos,
            target_entity=target_entity,
            shooter=self.owner,
            speed=850.0,
            max_range=max(self.range_of_fire, 160.0)
        )
        return bolt


class Freezing(Weapon):
    """
    Cryogenic non-lethal stasis pulse weapon.
    Fires physical FreezingBolt projectiles with cryogenic stasis effects.
    """
    def __init__(self, cooldown: float, num_cartridges: int, rate_of_fire: float,
                 range_of_fire: float, target_list: Optional[List[Any]] = None,
                 owner: Optional[Any] = None):
        super().__init__(cooldown, num_cartridges, rate_of_fire, range_of_fire, target_list, owner)

    def fire(self, target: Optional[Union[int, Any]] = None, origin: Optional[Any] = None) -> Optional[FreezingBolt]:
        if self.num_cartridges <= 0:
            return None

        pos_origin, target_pos, target_entity = self._resolve_target(target, origin)
        self.num_cartridges -= 1

        bolt = FreezingBolt(
            origin=pos_origin,
            target_pos=target_pos,
            target_entity=target_entity,
            shooter=self.owner,
            speed=650.0,
            max_range=max(self.range_of_fire, 350.0)
        )
        return bolt
