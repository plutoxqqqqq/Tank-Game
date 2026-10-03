"""Dropped pickups: XP orbs, health and temporary power-ups."""
from __future__ import annotations

import math

import pygame
from pygame.math import Vector2

from tankgame.config import *
from tankgame.ui.text import circle_outline, get_font


class Pickup:
    def __init__(self, pos: Vector2, kind: str, value: int = 0, power_type: str = ""):
        self.pos = Vector2(pos)
        self.kind = kind  # "xp" | "health" | "power"
        self.value = value
        self.power_type = power_type
        self.vel = Vector2(0, 0)

    def radius(self):
        if self.kind == "xp":
            return XP_ORB_RADIUS
        if self.kind == "health":
            return HEALTH_PACK_RADIUS
        return POWERUP_RADIUS

    def draw(self, surf, cam, t_seconds: float):
        screen_p = Vector2(self.pos.x - cam.x, self.pos.y - cam.y)
        p = (int(screen_p.x), int(screen_p.y))
        pulse = 1.0 + 0.10 * math.sin(t_seconds * 5.0 + (self.pos.x + self.pos.y) * 0.01)

        if self.kind == "xp":
            r = int(XP_ORB_RADIUS * pulse)
            pygame.draw.circle(surf, C_XP, p, r)
            circle_outline(surf, (60, 220, 140), p, r + 3, 2)
        elif self.kind == "health":
            r = int(HEALTH_PACK_RADIUS * pulse)
            pygame.draw.circle(surf, C_HEALTH, p, r)
            circle_outline(surf, (255, 160, 190), p, r + 3, 2)
            pygame.draw.rect(surf, (255, 240, 245), pygame.Rect(p[0] - 2, p[1] - 7, 4, 14))
            pygame.draw.rect(surf, (255, 240, 245), pygame.Rect(p[0] - 7, p[1] - 2, 14, 4))
        else:
            col = {
                "damage_boost": (255, 120, 220),
                "rapid_fire": (120, 255, 240),
                "speed_boost": (140, 255, 160),
                "shield": (200, 200, 255),
                "drone_range": (170, 255, 215),
            }.get(self.power_type, (255, 255, 255))
            r = int(POWERUP_RADIUS * pulse)
            pygame.draw.circle(surf, (58, 64, 88), p, r + 5, 2)
            pts = [(p[0], p[1] - r), (p[0] + r, p[1]), (p[0], p[1] + r), (p[0] - r, p[1])]
            pygame.draw.polygon(surf, col, pts)
            pygame.draw.polygon(surf, (20, 20, 30), pts, 2)
            letter = {
                "damage_boost": "D",
                "rapid_fire": "R",
                "speed_boost": "S",
                "shield": "O",
                "drone_range": "N",
            }.get(self.power_type, "?")
            glyph = get_font(16).render(letter, True, (16, 18, 26))
            surf.blit(glyph, glyph.get_rect(center=p))
