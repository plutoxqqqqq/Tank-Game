"""Arena layouts + lookup."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from tankgame.config import *


@dataclass
class MapDef:
    """An arena layout. Each run rolls one of the maps you own, so every run looks different.

    `pattern` picks the generator; the size fields tune it per map.
    """
    id: str
    name: str
    desc: str
    pattern: str
    count: int
    size_min: Tuple[int, int]
    size_max: Tuple[int, int]


MAPS = [
    MapDef("classic", "Classic", "Scattered cover, room to move", "scatter", 22, (80, 60), (220, 180)),
    MapDef("open_field", "Open Field", "Bare arena built for long kites", "scatter", 8, (60, 50), (150, 120)),
    MapDef("crowded", "Crowded", "Dense cover - tight sightlines", "scatter", 46, (58, 48), (150, 130)),
    MapDef("pillars", "Pillars", "A regular grid of hard cover", "pillars", 7, (86, 86), (86, 86)),
    MapDef("maze", "Maze", "Long corridors and chokepoints", "maze", 9, (60, 60), (260, 60)),
    MapDef("fortress", "Fortress", "A fortified ring around the centre", "fortress", 26, (70, 70), (170, 170)),
]

MAPS_BY_ID: Dict[str, MapDef] = {m.id: m for m in MAPS}


def map_of(map_id: str) -> MapDef:
    return MAPS_BY_ID.get(map_id, MAPS_BY_ID[MAP_DEFAULT_ID])
