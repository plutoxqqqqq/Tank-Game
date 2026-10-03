"""Small numeric + geometry helpers used everywhere."""
from __future__ import annotations

import math
from typing import Optional

import pygame
from pygame.math import Vector2

from tankgame.config import *


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)

def clamp_to_screen_edge(pt: Vector2, margin: int = 10) -> Vector2:
    return Vector2(clamp(pt.x, margin, WIDTH - margin), clamp(pt.y, margin, HEIGHT - margin))


def dist_point_to_segment(p: Vector2, a: Vector2, b: Vector2) -> float:
    """Shortest distance from point p to segment a->b (swept bullet collision)."""
    ab = b - a
    ab_len2 = ab.length_squared()
    if ab_len2 < 1e-9:
        return (p - a).length()
    t = clamp((p - a).dot(ab) / ab_len2, 0.0, 1.0)
    return (p - (a + ab * t)).length()


def segment_hits_circle(a: Vector2, b: Vector2, center: Vector2, radius: float) -> bool:
    return dist_point_to_segment(center, a, b) <= radius


def safe_int(value, default: int = 0) -> int:
    """Lenient int() for values coming out of the save file."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def fmt_amount(value) -> str:
    """Damage numbers: keep them short (flamethrower hits are fractional)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(v - round(v)) < 0.05:
        return str(int(round(v)))
    return f"{v:.1f}"
