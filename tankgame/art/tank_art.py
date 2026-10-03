"""Top-down tank rendering: hull, treads and a per-weapon barrel silhouette."""
from __future__ import annotations

import math
from typing import Tuple

import pygame
from pygame.math import Vector2

from tankgame.config import *
from tankgame.util import *


def _rot_rect(center: Vector2, f: Vector2, length: float, width: float):
    """Corners of a rectangle whose long axis follows `f`. Used to build the tank silhouette."""
    right = Vector2(-f.y, f.x)
    hl, hw = length * 0.5, width * 0.5
    return [center + f * hl + right * hw, center + f * hl - right * hw,
            center - f * hl - right * hw, center - f * hl + right * hw]


def draw_tank(surf, pos: Vector2, aim: Vector2, body_col, trim_col, outline_col, barrel_id: str):
    """Clean top-down tank with a barrel shaped for its weapon.

    Every tank now has its own muzzle silhouette, so you can tell a Railgun from a Minigun at a
    glance instead of every gun being the same grey triangle.
    """
    f = Vector2(aim)
    if f.length_squared() < 1e-6:
        f = Vector2(1, 0)
    f = f.normalize()
    right = Vector2(-f.y, f.x)
    edge = (11, 13, 18)
    tread = (36, 42, 55)
    muzzle = (150, 160, 178)

    # Treads either side of the hull.
    for side in (1, -1):
        pts = _rot_rect(pos + right * (12.5 * side), f, 36.0, 9.0)
        pygame.draw.polygon(surf, tread, pts)
        pygame.draw.polygon(surf, edge, pts, 1)

    # Hull.
    hull = _rot_rect(pos, f, 29.0, 25.0)
    pygame.draw.polygon(surf, body_col, hull)
    pygame.draw.polygon(surf, edge, hull, 2)

    # Turret ring in the player's cosmetic outline colour.
    pygame.draw.circle(surf, trim_col, (int(pos.x), int(pos.y)), 10)
    pygame.draw.circle(surf, edge, (int(pos.x), int(pos.y)), 10, 2)

    def rrect(off_along, length, width, col, outline=True):
        c = pos + f * off_along
        pts = _rot_rect(c, f, length, width)
        pygame.draw.polygon(surf, col, pts)
        if outline:
            pygame.draw.polygon(surf, edge, pts, 1)
        return c

    bid = barrel_id
    if bid == "minigun":
        for o in (-5.0, 0.0, 5.0):
            pts = _rot_rect(pos + f * 21.0 + right * o, f, 20.0, 4.0)
            pygame.draw.polygon(surf, muzzle, pts)
            pygame.draw.polygon(surf, edge, pts, 1)
    elif bid == "railgun":
        for o in (-4.5, 4.5):
            pts = _rot_rect(pos + f * 25.0 + right * o, f, 26.0, 3.5)
            pygame.draw.polygon(surf, muzzle, pts)
            pygame.draw.polygon(surf, edge, pts, 1)
        rrect(14.0, 10.0, 12.0, trim_col)
    elif bid == "sniper":
        rrect(26.0, 32.0, 3.5, muzzle)
        rrect(12.0, 12.0, 8.0, trim_col)
    elif bid == "cannon" or bid == "tank":
        rrect(22.0, 26.0, 11.0, muzzle)
        rrect(36.0, 6.0, 15.0, muzzle)   # muzzle brake
    elif bid == "shotgun":
        rrect(20.0, 22.0, 9.0, muzzle)
        rrect(33.0, 5.0, 14.0, muzzle)   # flared choke
    elif bid == "rocket":
        rrect(21.0, 24.0, 10.0, muzzle)
        pygame.draw.circle(surf, (255, 140, 90), (int((pos + f * 34).x), int((pos + f * 34).y)), 4)
    elif bid == "flamethrower":
        rrect(18.0, 18.0, 9.0, muzzle)
        tip = pos + f * 30
        pygame.draw.circle(surf, (255, 150, 70), (int(tip.x), int(tip.y)), 6)
        pygame.draw.circle(surf, (255, 200, 110), (int(tip.x), int(tip.y)), 3)
    elif bid == "windscreen_wiper":
        rrect(16.0, 16.0, 8.0, muzzle)
        # A wide flat wiper blade, perpendicular to the aim.
        pts = _rot_rect(pos + f * 30.0, f, 6.0, 40.0)
        pygame.draw.polygon(surf, trim_col, pts)
        pygame.draw.polygon(surf, edge, pts, 1)
    elif bid == "electricity" or bid == "tesla":
        rrect(19.0, 18.0, 8.0, muzzle)
        for o in (-6.0, 6.0):
            tip = pos + f * 30 + right * o
            pygame.draw.circle(surf, (190, 230, 255), (int(tip.x), int(tip.y)), 3)
    elif bid == "gravity_well":
        c = pos + f * 24
        pygame.draw.circle(surf, (120, 130, 200), (int(c.x), int(c.y)), 11, 2)
        pygame.draw.circle(surf, trim_col, (int(c.x), int(c.y)), 5)
    elif bid == "prism":
        c = pos + f * 24
        pts = [c + f * 11, c + right * 9 - f * 6, c - right * 9 - f * 6]
        pygame.draw.polygon(surf, (200, 235, 255), pts)
        pygame.draw.polygon(surf, edge, pts, 1)
    elif bid == "nanite_swarm":
        for i, o in enumerate((-8.0, 0.0, 8.0)):
            c = pos + f * (24 + i % 2 * 6) + right * o
            pygame.draw.circle(surf, (150, 255, 215), (int(c.x), int(c.y)), 3)
    elif bid == "hypnosis":
        c = pos + f * 23
        pygame.draw.circle(surf, trim_col, (int(c.x), int(c.y)), 9, 2)
        pygame.draw.circle(surf, (255, 190, 240), (int(c.x), int(c.y)), 3)
    elif bid == "mine_layer":
        rrect(18.0, 16.0, 11.0, muzzle)
        c = pos - f * 16
        pygame.draw.circle(surf, (255, 120, 110), (int(c.x), int(c.y)), 4)
        pygame.draw.circle(surf, edge, (int(c.x), int(c.y)), 4, 1)
    elif bid == "siphon":
        rrect(20.0, 22.0, 7.0, muzzle)
        c = pos + f * 32
        pygame.draw.circle(surf, (150, 255, 190), (int(c.x), int(c.y)), 3)
    elif bid == "ricochet":
        rrect(20.0, 20.0, 7.0, muzzle)
        c = pos + f * 30
        pygame.draw.polygon(surf, trim_col, [c + f * 5, c - f * 5 + right * 6, c - f * 5 - right * 6])
    elif bid == "homing":
        # Seeker launcher: a stubby tube with a dish ring that reads as "it tracks you".
        rrect(19.0, 19.0, 8.0, muzzle)
        c = pos + f * 30
        pygame.draw.circle(surf, trim_col, (int(c.x), int(c.y)), 6, 2)
        pygame.draw.circle(surf, (255, 200, 130), (int(c.x), int(c.y)), 2)
    else:   # pistol and anything new without its own silhouette
        rrect(20.0, 20.0, 6.0, muzzle)
