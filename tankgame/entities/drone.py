"""Orbiting combat drones for the Nanite Swarm tank."""
from __future__ import annotations

import math

import pygame
from pygame.math import Vector2

from tankgame.config import *
from tankgame.entities.projectile import Projectile
from tankgame.ui.text import circle_outline
from tankgame.art.glow import add_glow


class Drone:
    """A small orbiting ally for the Nanite Swarm tank.

    Drones hold an even ring around the player (the shared orbit phase lives on the game, so a
    drone added mid-run slots into the ring instead of overlapping its neighbours) and auto-fire at
    whichever enemy the player's chosen target mode says to.
    """
    def __init__(self, index: int, total: int, origin: Vector2):
        self.index = index
        self.total = max(1, total)
        self.pos = Vector2(origin)
        self.fire_cd = random.uniform(0.0, DRONE_FIRE_CD)

    def orbit_target(self, game) -> Vector2:
        # "Swarm Unleashed" ultra: the drones leave the ring and hunt on their own.
        if game.player.drone_free_roam:
            best = None
            best_d2 = float("inf")
            for e in game.enemies:
                if (not e.alive()) or e.is_charmed():
                    continue
                d2 = (e.pos - self.pos).length_squared()
                if d2 < best_d2:
                    best_d2, best = d2, e
            if best is not None:
                d = self.pos - best.pos
                if d.length_squared() > 1e-6:
                    return best.pos + d.normalize() * (best.radius + DRONE_FREE_ROAM_KEEP)
                return Vector2(best.pos)
        ang = game.drone_phase + math.tau * self.index / self.total
        return game.player.pos + Vector2(math.cos(ang), math.sin(ang)) * DRONE_ORBIT_RADIUS

    def pick_target(self, game, rng: float):
        """Choose a victim per the player's target mode, within this drone's reach."""
        mode = game.player.drone_target_mode
        reach2 = rng * rng
        mouse = getattr(game, "mouse_world", None)
        aim = game.player.aim_dir
        best = None
        best_score = None
        for e in game.enemies:
            if (not e.alive()) or e.is_charmed():
                continue
            if (e.pos - self.pos).length_squared() > reach2:
                continue
            if mode == "mouse" and mouse is not None:
                score = -(e.pos - mouse).length_squared()     # closest to the cursor
            elif mode == "angle":
                to = e.pos - game.player.pos
                if to.length_squared() < 1e-6 or aim.length_squared() < 1e-6:
                    score = 1.0
                else:
                    # Highest cosine = smallest angle from your barrel.
                    score = aim.normalize().dot(to.normalize())
            elif mode == "health":
                score = -e.hp                                # weakest first
            elif mode == "threat":
                score = e.hp                                 # toughest first
            else:
                score = -(e.pos - self.pos).length_squared()  # closest to this drone
            if best is None or score > best_score:
                best, best_score = e, score
        return best

    def update(self, dt, game):
        roam = game.player.drone_free_roam
        self.pos = self.pos.lerp(self.orbit_target(game), 1.0 - math.exp(-dt * (6.0 if roam else 9.0)))
        self.fire_cd -= dt
        if self.fire_cd > 0.0:
            return
        # Fire-rate upgrades speed the drones up too, so the Hive Uplink card actually bites.
        self.fire_cd = DRONE_FIRE_CD / max(0.2, game.player.fire_rate_mult)
        if len(game.projectiles) >= MAX_PROJECTILES:
            return
        # Roaming drones look much further afield - they are out hunting, not guarding you.
        reach = max(game.player.get_drone_range(), 1600.0) if roam else game.player.get_drone_range()
        best = self.pick_target(game, reach)
        if best is None:
            return
        dirn = best.pos - self.pos
        dirn = dirn.normalize() if dirn.length_squared() > 1e-6 else Vector2(1, 0)
        dmg = DRONE_BULLET_DAMAGE * game.player.damage_mult * game.player.meta_damage_mul
        game.projectiles.append(Projectile(
            Vector2(self.pos), dirn * 940.0, damage=dmg, owner="player",
            color=(150, 255, 215), radius=3, lifetime=0.62,
        ))

    def draw(self, surf, cam):
        p = (int(self.pos.x - cam.x), int(self.pos.y - cam.y))
        add_glow(surf, p, (120, 255, 205), 16, 0.6)
        pygame.draw.circle(surf, (16, 40, 36), p, 7)
        pygame.draw.circle(surf, (150, 255, 215), p, 5)
        pygame.draw.circle(surf, (235, 255, 248), (p[0] - 1, p[1] - 1), 2)
