"""The falling meteors used by the Meteor Strike minigame."""
from __future__ import annotations

import math

import pygame
from pygame.math import Vector2

from tankgame.config import *
from tankgame.util import *
from tankgame.data.minigames import METEOR_RADIUS
from tankgame.ui.text import circle_outline


class Meteor:
    """A telegraphed meteor for the Meteor Strike minigame.

    A ring shrinks for `telegraph` seconds, then the rock lands: anything inside the ring - you and
    the enemies alike - takes the hit. That telegraph is the whole fairness of the mode.
    """
    def __init__(self, pos: Vector2, telegraph: float, radius: float = METEOR_RADIUS,
                 friendly: bool = False, damage: float = 0.0):
        self.pos = Vector2(pos)
        self.radius = radius
        self.telegraph = telegraph
        self.timer = telegraph
        self.impact_timer = 0.0
        self.landed = False
        self.done = False
        # The Rocket "Meteor Barrage" ultra calls down friendly rocks: they hit enemies only and
        # never the player, so you can fire them point-blank without hurting yourself.
        self.friendly = friendly
        self.damage = float(damage)

    def update(self, dt, game):
        if not self.landed:
            self.timer -= dt
            if self.timer <= 0.0:
                self.landed = True
                self.impact_timer = 0.35
                self.impact(game)
        else:
            self.impact_timer -= dt
            if self.impact_timer <= 0.0:
                self.done = True

    def impact(self, game):
        game.shake = max(game.shake, 12.0)
        game._spawn_hit_particles(self.pos, (255, 160, 80))
        r2 = self.radius * self.radius
        if self.friendly:
            dmg = int(self.damage)
            for e in list(game.enemies):
                if (not e.alive()) or e.is_charmed():
                    continue
                d = e.pos - self.pos
                if d.length_squared() <= r2:
                    dirn = d.normalize() if d.length_squared() > 1e-6 else Vector2(1, 0)
                    e.take_damage(dmg, dirn, 300.0, weapon_id=game.player.weapon_id, from_player=True)
                    game.credit_player_damage(dmg)
                    game.add_float_text(e.pos + Vector2(0, -12), str(dmg), C_WARN, damage=True)
            return
        for e in list(game.enemies):
            if not e.alive():
                continue
            d = e.pos - self.pos
            if d.length_squared() <= r2:
                dirn = d.normalize() if d.length_squared() > 1e-6 else Vector2(1, 0)
                e.take_damage(180, dirn, 220.0, weapon_id=game.player.weapon_id, from_player=True)
        if (game.player.pos - self.pos).length_squared() <= r2:
            game.damage_player(1)

    def draw(self, surf, cam):
        p = (int(self.pos.x - cam.x), int(self.pos.y - cam.y))
        ring = (120, 220, 255) if self.friendly else (255, 150, 70)
        inner_c = (200, 245, 255) if self.friendly else (255, 220, 150)
        core = (140, 210, 255) if self.friendly else (255, 170, 90)
        hot = (240, 255, 255) if self.friendly else (255, 235, 190)
        if not self.landed:
            frac = 1.0 - clamp(self.timer / max(0.01, self.telegraph), 0.0, 1.0)
            r = int(self.radius)
            pygame.draw.circle(surf, ring, p, r, 2)
            circle_outline(surf, inner_c, p, max(3, int(r * (1.0 - frac))), 2)
            for q in range(4):
                a = q * math.pi / 2 + frac * 3.0
                inner = Vector2(math.cos(a), math.sin(a)) * r
                outer = inner * 1.22
                pygame.draw.line(surf, ring,
                                 (p[0] + inner.x, p[1] + inner.y), (p[0] + outer.x, p[1] + outer.y), 2)
        else:
            t = clamp(self.impact_timer / 0.35, 0.0, 1.0)
            r = int(self.radius * (0.7 + 0.5 * (1.0 - t)))
            pygame.draw.circle(surf, core, p, r)
            pygame.draw.circle(surf, hot, p, max(2, int(r * 0.6)))
