"""Dropped pickups: XP orbs, health and temporary power-ups."""
from __future__ import annotations

import math

import pygame
from pygame.math import Vector2

from tankgame.config import *
from tankgame.ui.text import circle_outline, get_font
from tankgame.art.glow import add_glow


POWERUP_COLORS = {
    "damage_boost": (255, 120, 220),
    "rapid_fire": (120, 255, 240),
    "speed_boost": (140, 255, 160),
    "shield": (200, 200, 255),
    "drone_range": (170, 255, 215),
}
POWERUP_LETTERS = {"damage_boost": "D", "rapid_fire": "R", "speed_boost": "S", "shield": "O",
                   "drone_range": "N"}


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
        p = (int(self.pos.x - cam.x), int(self.pos.y - cam.y))
        pulse = 1.0 + 0.10 * math.sin(t_seconds * 5.0 + (self.pos.x + self.pos.y) * 0.01)

        if self.kind == "xp":
            r = int(XP_ORB_RADIUS * pulse)
            add_glow(surf, p, C_XP, r * 2 + 6, 0.55)
            pygame.draw.circle(surf, (40, 140, 92), p, r)
            pygame.draw.circle(surf, C_XP, p, max(1, r - 2))
            pygame.draw.circle(surf, (225, 255, 236), (p[0] - r // 3, p[1] - r // 3), max(1, r // 3))
        elif self.kind == "health":
            r = int(HEALTH_PACK_RADIUS * pulse)
            add_glow(surf, p, C_HEALTH, r * 2 + 6, 0.55)
            pygame.draw.circle(surf, (170, 46, 70), p, r)
            pygame.draw.circle(surf, C_HEALTH, p, max(1, r - 2))
            pygame.draw.rect(surf, (255, 242, 246), pygame.Rect(p[0] - 2, p[1] - 6, 4, 12), border_radius=1)
            pygame.draw.rect(surf, (255, 242, 246), pygame.Rect(p[0] - 6, p[1] - 2, 12, 4), border_radius=1)
        else:
            col = POWERUP_COLORS.get(self.power_type, (255, 255, 255))
            r = int(POWERUP_RADIUS * pulse)
            add_glow(surf, p, col, r * 3, 0.7)
            # A glassy rounded badge with the power-up's letter.
            pygame.draw.circle(surf, (18, 22, 30), p, r + 3)
            pygame.draw.circle(surf, col, p, r + 3, 2)
            pygame.draw.circle(surf, col, p, r - 2)
            pygame.draw.circle(surf, tuple(min(255, c + 60) for c in col), (p[0] - r // 3, p[1] - r // 3), max(2, r // 3))
            letter = POWERUP_LETTERS.get(self.power_type, "?")
            font = get_font(17)
            font.set_bold(True)
            glyph = font.render(letter, True, (14, 18, 24))
            font.set_bold(False)
            surf.blit(glyph, glyph.get_rect(center=p))
