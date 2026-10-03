"""Cached additive glow sprites for in-world effects (bullets, sparks, pickups, hazards).

Everything here is blitted with ``BLEND_RGB_ADD`` onto the frame: black adds nothing, so the
sprites need no per-pixel alpha and stay cheap even with hundreds of rounds on screen. Sprites
are built once per (colour, radius, intensity) and cached.
"""
from __future__ import annotations

from typing import Dict, Tuple

import pygame

_glow_cache: Dict[tuple, pygame.Surface] = {}
_disc_cache: Dict[tuple, pygame.Surface] = {}
_GLOW_LEVELS = 8


def _scale(color, k: float) -> Tuple[int, int, int]:
    return (min(255, int(color[0] * k)), min(255, int(color[1] * k)), min(255, int(color[2] * k)))


def glow_sprite(color, radius: int, intensity: float = 1.0) -> pygame.Surface:
    """A soft radial glow (bright centre, falling to black at ``radius``)."""
    radius = max(2, int(radius))
    level = max(1, min(_GLOW_LEVELS, int(round(intensity * _GLOW_LEVELS))))
    key = (tuple(color[:3]), radius, level)
    surf = _glow_cache.get(key)
    if surf is None:
        size = radius * 2 + 2
        surf = pygame.Surface((size, size))
        surf.fill((0, 0, 0))
        k_max = level / _GLOW_LEVELS
        steps = min(radius, 14)
        for i in range(steps, 0, -1):
            t = i / steps                       # 1 at the rim, ~0 at the centre
            falloff = (1.0 - t) ** 1.8
            pygame.draw.circle(surf, _scale(color, falloff * k_max * 1.15),
                               (radius + 1, radius + 1), max(1, int(radius * t)))
        if len(_glow_cache) > 600:
            _glow_cache.clear()
        _glow_cache[key] = surf
    return surf


def add_glow(screen: pygame.Surface, pos, color, radius: int, intensity: float = 1.0):
    spr = glow_sprite(color, radius, intensity)
    r = spr.get_width() // 2
    screen.blit(spr, (int(pos[0]) - r, int(pos[1]) - r), special_flags=pygame.BLEND_RGB_ADD)


def tinted_disc(color, radius: int, alpha: int) -> pygame.Surface:
    """A translucent filled disc (real alpha), e.g. a meteor danger zone."""
    radius = max(2, int(radius))
    key = (tuple(color[:3]), radius, int(alpha))
    surf = _disc_cache.get(key)
    if surf is None:
        surf = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*color[:3], int(alpha)), (radius + 1, radius + 1), radius)
        if len(_disc_cache) > 200:
            _disc_cache.clear()
        _disc_cache[key] = surf
    return surf
