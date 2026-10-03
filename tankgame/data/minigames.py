"""Short challenge (minigame) definitions, their tuning and lookup."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from tankgame.config import *


@dataclass
class MinigameDef:
    """A short, self-contained challenge with its own win condition and coin payout.

    Every current minigame is a timed survival; `duration` is how many seconds to last.
    """
    id: str
    name: str
    desc: str
    difficulty: int          # 1..5, drives the payout tier
    reward: int              # coins for a full clear
    duration: float          # seconds to survive
    accent: Tuple[int, int, int]
    tip: str = ""


# Minigames are long-haul challenges: 4x the old duration and 4x the payout, so a clear is a real
# session rather than a coffee break. (3-5x was the target; everything scales by the same factor.)
MINIGAME_SCALE = 4.0

MINIGAMES = [
    MinigameDef("meteor", "Meteor Strike", "Survive a meteor rain - the warnings get shorter.",
                2, 60, 75.0, (255, 150, 70), "The ring shows where it lands. Step off it."),
    MinigameDef("blitz", "Blitz", "180 seconds of maximum spawn pressure.",
                3, 85, 45.0, (120, 220, 255), "The arena fills fast. Keep moving."),
    MinigameDef("rapid", "Rapid", "Waves flip every 3 seconds. Survive the churn.",
                4, 110, 60.0, (255, 214, 120), "Bosses can arrive in seconds - stay mobile."),
    MinigameDef("dash_only", "Dash Only", "Walking is disabled - dash is your only movement.",
                3, 95, 60.0, (200, 150, 255), "Aim where you want to go, then dash."),
    MinigameDef("glass", "Glass Gauntlet", "One hit point, flat 99 damage. Survive.",
                4, 120, 60.0, (255, 104, 168), "One mistake ends it - but every shot hits for 99."),
    MinigameDef("ultra_only", "Ultra Only", "Every level-up offers ultra cards - from ANY tank.",
                5, 190, 80.0, (255, 208, 74), "Pick an ultra, then pick another one."),
    MinigameDef("impossible", "Impossible Mode", "Three bosses at once, the whole time.",
                5, 200, 70.0, (255, 90, 95), "They never stop coming. Play keep-away."),
    MinigameDef("nightmare", "Nightmare", "Every spawn is a maxed wave-50 boss.",
                5, 150, 45.0, (255, 60, 60), "No normal enemies exist here. Keep dashing."),
]

# Apply the length/payout scale in one place so the table above stays readable.
for _mg in MINIGAMES:
    _mg.duration = round(_mg.duration * MINIGAME_SCALE, 1)
    _mg.reward = int(round(_mg.reward * MINIGAME_SCALE))

MINIGAMES_BY_ID: Dict[str, MinigameDef] = {m.id: m for m in MINIGAMES}

# Meteor Strike tuning: telegraph shrinks from generous to brutal over the run.
METEOR_TELEGRAPH_START = 3.0
METEOR_TELEGRAPH_END = 0.5
METEOR_RADIUS = 58.0
METEOR_MAX_ACTIVE = 14
