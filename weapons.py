from random import uniform
from typing import List, Optional, Any, Union
from constants import PROB_VAPORIZER, PROB_FREEZING

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
                 target_list: Optional[List[Any]] = None):
        self.cooldown = cooldown
        self.num_cartridges = num_cartridges
        self.rate_of_fire = rate_of_fire
        self.range_of_fire = range_of_fire
        self.kamikazes = target_list if target_list is not None else []
        self.available = True

    def fire(self, target: Optional[Union[int, Any]] = None) -> bool:
        """
        Attempts to discharge the weapon against a target entity or index.
        Must be implemented by derived weapon classes.
        """
        raise NotImplementedError("Weapon subclasses must implement fire(target).")

    def receive_list_kamikazes(self, list_kamikazes: List[Any]):
        """Updates internal reference to the current threat pool."""
        self.kamikazes = list_kamikazes

    def reload(self):
        """Replenishes weapon ammo or resets cooldown cycle."""
        self.available = True

    def get_ammo_available(self) -> int:
        """Returns the current ammunition count."""
        return self.num_cartridges


class Vaporizer(Weapon):
    """
    High-energy lethal directed-energy weapon.
    Destroys target upon successful engagement within 100px.
    """
    def __init__(self, cooldown: float, num_cartridges: int, rate_of_fire: float,
                 range_of_fire: float, target_list: Optional[List[Any]] = None):
        super().__init__(cooldown, num_cartridges, rate_of_fire, range_of_fire, target_list)

    def fire(self, target: Optional[Union[int, Any]] = None) -> bool:
        if self.num_cartridges <= 0 or not self.kamikazes:
            return False

        try:
            target_idx = -1
            if isinstance(target, int):
                target_idx = target
            elif target is not None and target in self.kamikazes:
                target_idx = self.kamikazes.index(target)
            elif target is None:
                target_idx = 0

            if 0 <= target_idx < len(self.kamikazes):
                hit_prob = uniform(0.0, 1.0)
                if hit_prob < PROB_VAPORIZER:
                    self.kamikazes.pop(target_idx)
                    self.num_cartridges -= 1
                    return True
                else:
                    self.num_cartridges -= 1
                    return False
        except (IndexError, ValueError):
            return False

        return False


class Freezing(Weapon):
    """
    Cryogenic non-lethal incapacitation weapon.
    Dramatically slows down the target UAV upon hit within 300px.
    """
    def __init__(self, cooldown: float, num_cartridges: int, rate_of_fire: float,
                 range_of_fire: float, target_list: Optional[List[Any]] = None):
        super().__init__(cooldown, num_cartridges, rate_of_fire, range_of_fire, target_list)

    def fire(self, target: Optional[Union[int, Any]] = None) -> bool:
        if self.num_cartridges <= 0 or not self.kamikazes:
            return False

        try:
            target_idx = -1
            if isinstance(target, int):
                target_idx = target
            elif target is not None and target in self.kamikazes:
                target_idx = self.kamikazes.index(target)
            elif target is None:
                target_idx = 0

            if 0 <= target_idx < len(self.kamikazes):
                hit_prob = uniform(0.0, 1.0)
                if hit_prob < PROB_FREEZING:
                    target_drone = self.kamikazes[target_idx]
                    if hasattr(target_drone, 'slow_down'):
                        target_drone.slow_down()
                    self.num_cartridges -= 1
                    return True
                else:
                    self.num_cartridges -= 1
                    return False
        except (IndexError, ValueError):
            return False

        return False
