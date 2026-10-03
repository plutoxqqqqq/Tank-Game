"""Weapon mastery level requirements."""
from __future__ import annotations

from typing import Tuple

from tankgame.config import *

MAX_MASTERY_LEVEL = 5


def mastery_requirements(level: int) -> Tuple[int, int]:
    kills_needed = int(30 * (level ** 2))
    games_needed = int(5 + (level - 1) * 7)
    return kills_needed, games_needed
