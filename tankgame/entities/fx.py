"""Transient visual effects: particles and floating damage text."""
from __future__ import annotations

import math
import random
from typing import Tuple

import pygame
from pygame.math import Vector2

from tankgame.config import *
from tankgame.util import *
from tankgame.ui.text import draw_text
from tankgame.ui.text import get_font
from tankgame.art.glow import add_glow


_TEXT_CACHE = {}


def _outlined_text(text: str, color) -> pygame.Surface:
    """Bold label with a dark outline so damage numbers stay readable over a busy fight."""
    key = (text, tuple(color[:3]))
    img = _TEXT_CACHE.get(key)
    if img is None:
        font = get_font(20)
        font.set_bold(True)
        fg = font.render(text, True, color[:3])
        edge = font.render(text, True, (8, 10, 14))
        font.set_bold(False)
        img = pygame.Surface((fg.get_width() + 2, fg.get_height() + 2), pygame.SRCALPHA)
        for ox, oy in ((0, 1), (2, 1), (1, 0), (1, 2), (0, 0), (2, 2), (0, 2), (2, 0)):
            img.blit(edge, (ox, oy))
        img.blit(fg, (1, 1))
        if len(_TEXT_CACHE) > 400:
            _TEXT_CACHE.clear()
        _TEXT_CACHE[key] = img
    return img


class Particle:
    def __init__(self, pos: Vector2, vel: Vector2, color: Tuple[int, int, int], life=PARTICLE_LIFE, radius=2):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.color = color
        self.life = life
        self.life_max = life
        self.radius = radius

    def update(self, dt):
        self.life -= dt
        self.pos += self.vel * dt
        self.vel *= (1.0 - min(dt * 4.5, 0.35))

    def draw(self, surf, cam):
        if self.life <= 0:
            return
        t = clamp(self.life / self.life_max, 0, 1)
        p = (int(self.pos.x - cam.x), int(self.pos.y - cam.y))
        rr = max(1, int(self.radius * (0.6 + 0.7 * t)))
        # A glowing spark that dims as it dies (additive, so it never darkens what is under it).
        add_glow(surf, p, self.color, rr * 3 + 1, 0.25 + 0.6 * t)
        cr, cg, cb = self.color
        br, bg, bb = C_BG
        col = (int(br + (cr - br) * t), int(bg + (cg - bg) * t), int(bb + (cb - bb) * t))
        pygame.draw.circle(surf, col, p, rr)

class FloatingText:
    def __init__(self, pos: Vector2, text: str, color=C_WARN, life=0.65):
        self.pos = Vector2(pos)
        self.text = text
        self.color = color
        self.life = life
        self.life_max = life
        self.vel = Vector2(random.uniform(-30, 30), random.uniform(-90, -55))

    def update(self, dt):
        self.life -= dt
        self.pos += self.vel * dt
        self.vel.y -= 55 * dt

    def draw(self, surf, cam, font=None):
        if self.life <= 0:
            return
        t = clamp(self.life / self.life_max, 0, 1)
        img = _outlined_text(self.text, self.color)
        img.set_alpha(int(255 * min(1.0, t * 1.6)))
        surf.blit(img, (int(self.pos.x - cam.x) - img.get_width() // 2, int(self.pos.y - cam.y)))
