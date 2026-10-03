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
        # Fade toward the background: pygame.draw ignores the alpha byte on an opaque display
        # surface, so the old "(*color, a)" never actually faded.
        cr, cg, cb = self.color
        br, bg, bb = C_BG
        col = (int(br + (cr - br) * t), int(bg + (cg - bg) * t), int(bb + (cb - bb) * t))
        rr = max(1, int(self.radius * (0.7 + 0.6 * t)))
        pygame.draw.circle(surf, col, (int(self.pos.x - cam.x), int(self.pos.y - cam.y)), rr)


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

    def draw(self, surf, cam, font):
        if self.life <= 0:
            return
        t = clamp(self.life / self.life_max, 0, 1)
        a = int(255 * t)
        img = font.render(self.text, True, self.color)
        img.set_alpha(a)
        surf.blit(img, (self.pos.x - cam.x, self.pos.y - cam.y))
