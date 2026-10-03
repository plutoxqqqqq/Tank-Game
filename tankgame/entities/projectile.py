"""A single flying round (player, enemy or ally) and how it renders."""
from __future__ import annotations

import math
from typing import Optional

import pygame
from pygame.math import Vector2

from tankgame.config import *
from tankgame.util import *
from tankgame.ui.text import circle_outline


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
        a = (int(self.prev_pos.x - cam.x), int(self.prev_pos.y - cam.y))
        b = (int(self.pos.x - cam.x), int(self.pos.y - cam.y))
        if self.mine:
            blink = (int(self.life * 6) % 2) == 0
            pygame.draw.circle(surf, self.color, b, self.radius)
            circle_outline(surf, (255, 120, 90) if blink else (120, 90, 60), b, self.radius + 3, 2)
            return
        if self.beam > 0.0:
            # Railgun: a long red laser instead of a dot, so you can read the line it cut.
            sp = self.vel.length()
            back = Vector2(self.vel)
            if sp > 1e-6:
                back = back / sp
            else:
                back = Vector2(1, 0)
            tail = self.pos - back * self.beam
            t0 = (int(tail.x - cam.x), int(tail.y - cam.y))
            pygame.draw.line(surf, (255, 60, 60), t0, b, 5)
            pygame.draw.line(surf, (255, 190, 190), t0, b, 2)
            pygame.draw.circle(surf, (255, 120, 120), b, self.radius + 2)
            return
        # short tracer so fast rounds still read on screen
        if a != b:
            pygame.draw.line(surf, self.color, a, b, max(1, self.radius))
        pygame.draw.circle(surf, self.color, b, self.radius)
        circle_outline(surf, self.color, b, self.radius + 3, 1)

    def settle(self):
        """Mines stop dead where they land."""
        self.vel = Vector2(0, 0)
        self.settled = True

    def alive(self):
        return self.life > 0
