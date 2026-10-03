"""Per-wave twists (mutators) + lookup."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from tankgame.config import *


@dataclass
class MutatorDef:
    """A per-wave twist. Announced in the banner and pinned to the HUD for the whole wave.

    Every field defaults to 1.0, so a mutator only states what it actually changes.
    """
    id: str
    name: str
    desc: str
    color: Tuple[int, int, int]
    hp_mul: float = 1.0
    speed_mul: float = 1.0
    rate_mul: float = 1.0      # multiplies the spawn interval: below 1.0 = more enemies
    elite_mul: float = 1.0
    coin_bonus: int = 2        # banked coins if you survive the wave


MUTATORS = [
    MutatorDef("swarm", "SWARM", "Many more, much frailer enemies", C_SPRINTER,
               hp_mul=0.78, rate_mul=0.62, coin_bonus=3),
    MutatorDef("hardened", "HARDENED", "Tankier enemies for a bigger payout", C_TANK,
               hp_mul=1.45, coin_bonus=4),
    MutatorDef("overdrive", "OVERDRIVE", "Everything moves 18% faster", C_DASHER,
               speed_mul=1.18, coin_bonus=4),
    MutatorDef("elite_hunt", "ELITE HUNT", "Elite variants are far more common", C_BOSS,
               elite_mul=3.0, coin_bonus=5),
]

MUTATORS_BY_ID = {m.id: m for m in MUTATORS}
