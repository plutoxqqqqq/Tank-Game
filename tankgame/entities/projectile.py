"""A single flying round (player, enemy or ally) and how it renders."""
from __future__ import annotations

import math
from typing import Optional

import pygame
from pygame.math import Vector2

from tankgame.config import *
from tankgame.util import *
from tankgame.ui.text import circle_outline
from tankgame.art.glow import add_glow


class Projectile:
    def __init__(
        self,
        pos: Vector2,
        vel: Vector2,
        damage: float,
        owner: str,
        color,
        radius=4,
        lifetime=1.0,
        pierce=0,
        splash_radius=0.0,  # for rocket
        slow=0.0,
        slow_time=0.0,
        burn_dps=0.0,
        burn_time=0.0,
        bounces=0,
        mine=False,
        pull=0.0,
        pull_radius=0.0,
        split=0,
        split_mult=0.55,
        charm=0.0,
        overpen_frac=0.0,
        homing=0.0,
        homing_range=0.0,
        no_walls=False,
        beam=0.0,
        split_recursive=False,
        split_depth=0,
        bounce_enemies=False,
        ground_fire=False,
        source_enemy=None,
    ):
        self.pos = Vector2(pos)
        self.prev_pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.damage = float(damage)
        self.owner = owner
        self.color = color
        self.radius = radius
        self.life = lifetime
        self.life_max = lifetime
        self.pierce = pierce
        self.hit_set = set()      # enemy objects already hit by this round (identity based)
        self.splash_radius = splash_radius
        # status payload applied to whatever this round hits
        self.slow = slow
        self.slow_time = slow_time
        self.burn_dps = burn_dps
        self.burn_time = burn_time
        # ricochet rounds bounce instead of dying on the first wall; mines park where they land
        self.bounces = int(bounces)
        self.mine = mine
        self.settled = False
        # Gravity Well / Prism / Railgun / Hypnosis payloads
        self.pull = float(pull)
        self.pull_radius = float(pull_radius)
        self.split = int(split)
        self.split_mult = float(split_mult)
        self.split_done = False
        self.charm = float(charm)
        self.overpen_frac = float(overpen_frac)
        self.hit_count = 0
        # Homing tank / wall-piercing railgun / laser rendering
        self.homing = float(homing)
        self.homing_range = float(homing_range)
        self.no_walls = bool(no_walls)
        self.beam = float(beam)
        # Ultra payloads: Prism recursion, Ricochet-vs-enemies, Flamethrower scorch, Siphon blame.
        self.split_recursive = bool(split_recursive)
        self.split_depth = int(split_depth)
        self.bounce_enemies = bool(bounce_enemies)
        self.ground_fire = bool(ground_fire)
        self.source_enemy = source_enemy   # enemy object that fired this (for Siphon retribution)
        self.pierce_splash = False         # Cannon ultra: blast fires on every enemy pierced

    def update(self, dt):
        self.life -= dt
        self.prev_pos = Vector2(self.pos)
        self.pos += self.vel * dt

    def swept_hit(self, center: Vector2, radius: float) -> bool:
        """Swept test for this frame's movement - stops fast rounds tunnelling through targets."""
        return segment_hits_circle(self.prev_pos, self.pos, center, radius + self.radius)

    def draw(self, surf, cam):
        b = (int(self.pos.x - cam.x), int(self.pos.y - cam.y))
        r = max(1, int(self.radius))
        if self.mine:
            blink = (int(self.life * 6) % 2) == 0
            add_glow(surf, b, (255, 120, 90) if blink else (130, 70, 40), r * 3 + 4, 0.8 if blink else 0.35)
            pygame.draw.circle(surf, (26, 22, 22), b, r + 2)
            pygame.draw.circle(surf, self.color, b, r)
            pygame.draw.circle(surf, (255, 236, 200) if blink else (150, 118, 86), b, max(1, r // 2))
            return
        sp = self.vel.length()
        d = self.vel / sp if sp > 1e-6 else Vector2(1, 0)
        if self.beam > 0.0:
            # Railgun: a layered laser (dark halo, hot body, white core) with a glowing head.
            tail = self.pos - d * self.beam
            t0 = (int(tail.x - cam.x), int(tail.y - cam.y))
            pygame.draw.line(surf, (96, 18, 22), t0, b, 9)
            pygame.draw.line(surf, (255, 70, 70), t0, b, 5)
            pygame.draw.line(surf, (255, 222, 222), t0, b, 2)
            add_glow(surf, b, (255, 90, 90), 16, 0.9)
            return
        # A tapered tracer: dim tail, bright body, hot core, soft additive bloom.
        trail = min(30.0, 6.0 + sp * 0.02)
        tail = self.pos - d * trail
        mid = self.pos - d * (trail * 0.45)
        t0 = (int(tail.x - cam.x), int(tail.y - cam.y))
        m0 = (int(mid.x - cam.x), int(mid.y - cam.y))
        col = self.color
        dim = (col[0] * 2 // 5, col[1] * 2 // 5, col[2] * 2 // 5)
        hot = (min(255, col[0] + 90), min(255, col[1] + 90), min(255, col[2] + 90))
        add_glow(surf, b, col, r * 3 + 3, 0.7)
        pygame.draw.line(surf, dim, t0, m0, max(1, r - 1))
        pygame.draw.line(surf, col, m0, b, max(2, r))
        pygame.draw.circle(surf, col, b, r)
        pygame.draw.circle(surf, hot, b, max(1, r // 2))

    def settle(self):
        """Mines stop dead where they land."""
        self.vel = Vector2(0, 0)
        self.settled = True

    def alive(self):
        return self.life > 0
