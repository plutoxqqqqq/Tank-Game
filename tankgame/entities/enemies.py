"""All enemy types, including the boss."""
from __future__ import annotations

import math
import random
from typing import Optional

import pygame
from pygame.math import Vector2

from tankgame.config import *
from tankgame.util import *
from tankgame.entities.projectile import Projectile
from tankgame.ui.text import circle_outline


def shade_body(surf, p, radius: int, col):
    """A solid unit with a ground shadow, a darker rim and a soft specular highlight."""
    pygame.draw.circle(surf, (6, 8, 12), (p[0] + 3, p[1] + 4), radius)
    rim = (max(0, col[0] - 70), max(0, col[1] - 70), max(0, col[2] - 70))
    pygame.draw.circle(surf, rim, p, radius)
    pygame.draw.circle(surf, col, p, max(1, radius - 2))
    hl = (min(255, col[0] + 70), min(255, col[1] + 70), min(255, col[2] + 70))
    pygame.draw.circle(surf, hl, (p[0] - radius // 3, p[1] - radius // 3), max(2, radius // 3))
    pygame.draw.circle(surf, (12, 14, 20), p, radius + 1, 1)


class EnemyBase:
    def __init__(self, pos: Vector2, hp: float, speed: float, radius: int, color):
        self.pos = Vector2(pos)
        self.vel = Vector2(0, 0)
        self.hp = hp
        self.hp_max = hp
        self.speed = speed
        self.radius = radius
        self.color = color
        self.damage_contact = 1
        self.score_value = 10
        self.hit_flash = 0.0
        self.last_hit_weapon_id: Optional[str] = None
        self.last_hit_by_player: bool = False
        # status effects
        self.slow_timer = 0.0
        self.slow_frac = 0.0
        self.burn_timer = 0.0
        self.burn_dps = 0.0
        self.elite = False
        # Hypnosis: while charmed the enemy is a temporary ally and ignores the player.
        self.charm_timer = 0.0
        self.charm_hit_cd = 0.0
        # Every point of HP this enemy loses is recorded here by the engine's own damage paths
        # (take_damage, burn, scorched ground). The referee checks hp == hp_max - recorded damage,
        # so an HP that drops without a recorded hit (a poke) is restored before it can pay out.
        self._ac_dmg = 0.0

    def speed_mult(self) -> float:
        return (1.0 - self.slow_frac) if self.slow_timer > 0.0 else 1.0

    def effective_speed(self) -> float:
        return self.speed * self.speed_mult()

    def apply_slow(self, frac: float, duration: float):
        if frac > 0.0 and duration > 0.0:
            self.slow_frac = max(self.slow_frac, clamp(frac, 0.0, 0.9))
            self.slow_timer = max(self.slow_timer, duration)

    def is_charmed(self) -> bool:
        return self.charm_timer > 0.0

    def apply_charm(self, duration: float):
        if duration > 0.0:
            self.charm_timer = max(self.charm_timer, duration)

    def apply_burn(self, dps: float, duration: float):
        if dps > 0.0 and duration > 0.0:
            self.burn_dps = max(self.burn_dps, dps)
            self.burn_timer = max(self.burn_timer, duration)

    def tick_status(self, dt, game):
        if self.slow_timer > 0.0:
            self.slow_timer = max(0.0, self.slow_timer - dt)
            if self.slow_timer <= 0.0:
                self.slow_frac = 0.0
        if self.burn_timer > 0.0:
            self.burn_timer = max(0.0, self.burn_timer - dt)
            self.hp -= self.burn_dps * dt
            self._ac_dmg += self.burn_dps * dt
            game.credit_burn_damage(self.burn_dps * dt)
        if self.charm_timer > 0.0:
            self.charm_timer = max(0.0, self.charm_timer - dt)
        self.charm_hit_cd = max(0.0, self.charm_hit_cd - dt)

    def update(self, dt, game):
        raise NotImplementedError

    def apply_separation(self, dt, neighbors: List["EnemyBase"]):
        push = Vector2(0, 0)
        for other in neighbors:
            if other is self:
                continue
            d = self.pos - other.pos
            dist = d.length()
            min_dist = self.radius + other.radius
            if 0.001 < dist < min_dist * ENEMY_SEPARATION_SOFT:
                push += d.normalize() * (min_dist - dist) * ENEMY_SEPARATION_FORCE
        if push.length_squared() > 0:
            self.vel += push * dt * 8.0

    def take_damage(self, dmg: int, knock_dir: Vector2, knockback: float, weapon_id: Optional[str] = None, from_player: bool = False):
        self.hp -= dmg
        self._ac_dmg += dmg
        self.vel += knock_dir * (knockback / max(1.0, self.radius))
        self.hit_flash = 0.12
        if from_player:
            self.last_hit_by_player = True
            self.last_hit_weapon_id = weapon_id

    def alive(self):
        return self.hp > 0

    def draw(self, surf, cam):
        p = (int(self.pos.x - cam.x), int(self.pos.y - cam.y))
        col = (255, 255, 255) if self.hit_flash > 0 else self.color
        shade_body(surf, p, self.radius, col)

        if self.elite:
            circle_outline(surf, (255, 215, 120), p, self.radius + 6, 2)
        if self.slow_timer > 0.0:
            circle_outline(surf, (140, 220, 255), p, self.radius + 4, 2)
        if self.burn_timer > 0.0:
            flick = 2 + int(2 + 2 * math.sin(self.burn_timer * 30.0))
            pygame.draw.circle(surf, (255, 150, 60), p, max(1, self.radius - flick))
        if self.charm_timer > 0.0:
            # Charmed allies glow pink so you never mistake them for threats.
            pulse = 1 + int(1 + math.sin(self.charm_timer * 12.0))
            circle_outline(surf, C_CHARM, p, self.radius + 6 + pulse, 3)

        # hp bar (small) - only once damaged, to keep the field readable
        if self.hp < self.hp_max:
            w = self.radius * 2
            h = 5
            x = p[0] - w // 2
            y = p[1] - self.radius - 12
            frac = clamp(self.hp / max(1.0, self.hp_max), 0, 1)
            pygame.draw.rect(surf, (10, 12, 16), pygame.Rect(x - 1, y - 1, w + 2, h + 2), border_radius=3)
            if frac > 0:
                pygame.draw.rect(surf, (90, 255, 210), pygame.Rect(x, y, max(2, int(w * frac)), h), border_radius=2)


class Chaser(EnemyBase):
    def __init__(self, pos, hp, speed):
        super().__init__(pos, hp, speed, radius=ENEMY_RADIUS_CHASER, color=C_CHASER)
        self.damage_contact = 1
        self.score_value = 12

    def update(self, dt, game):
        tgt = game.enemy_target(self)
        if tgt is None:
            self.vel *= math.exp(-dt * 3.0)
            self.pos += self.vel * dt
            game.resolve_circle_walls(self, damping=0.2)
            return
        d = tgt.pos - self.pos
        if d.length_squared() > 1:
            desired = d.normalize() * self.effective_speed()
            self.vel = self.vel.lerp(desired, 1 - math.exp(-dt * 6.5))
        self.pos += self.vel * dt
        game.resolve_circle_walls(self, damping=0.2)


class Pink(EnemyBase):
    """The boss's retinue: a cheap, quick swarmer spawned in bulk on boss waves.

    Boss waves drop one per wave number (wave 10 -> 10, wave 20 -> 20, ...), so the arena fills
    with pink the moment a boss arrives.
    """
    def __init__(self, pos, hp, speed):
        super().__init__(pos, hp, speed, radius=ENEMY_RADIUS_PINK, color=C_PINK)
        self.damage_contact = PINK_DAMAGE_CONTACT
        self.score_value = 8

    def update(self, dt, game):
        tgt = game.enemy_target(self)
        if tgt is None:
            self.vel *= math.exp(-dt * 3.0)
            self.pos += self.vel * dt
            game.resolve_circle_walls(self, damping=0.2)
            return
        d = tgt.pos - self.pos
        if d.length_squared() > 1:
            desired = d.normalize() * self.effective_speed()
            self.vel = self.vel.lerp(desired, 1 - math.exp(-dt * 7.5))
        self.pos += self.vel * dt
        game.resolve_circle_walls(self, damping=0.2)


class Ranged(EnemyBase):
    def __init__(self, pos, hp, speed):
        super().__init__(pos, hp, speed, radius=ENEMY_RADIUS_RANGED, color=C_RANGED)
        self.damage_contact = 1
        self.score_value = 16
        self.shoot_cd = random.uniform(0.9, 1.3)

    def update(self, dt, game):
        self.shoot_cd -= dt
        # Brainwashed shooters keep shooting - just at their former allies.
        tgt = game.enemy_target(self)
        if tgt is None:
            self.vel *= math.exp(-dt * 4.0)
            self.pos += self.vel * dt
            game.resolve_circle_walls(self, damping=0.2)
            return
        d = tgt.pos - self.pos
        dist = d.length()

        # keep distance
        if dist > 430:
            if dist > 1:
                desired = d.normalize() * self.effective_speed()
                self.vel = self.vel.lerp(desired, 1 - math.exp(-dt * 5.0))
        elif dist < 270:
            if dist > 1:
                desired = (-d).normalize() * (self.effective_speed() * 0.95)
                self.vel = self.vel.lerp(desired, 1 - math.exp(-dt * 7.0))
        else:
            self.vel *= (1.0 - min(dt * 6.5, 0.25))

        self.pos += self.vel * dt
        game.resolve_circle_walls(self, damping=0.2)

        # Re-measure after moving: the old code aimed with the distance from before the step.
        d = tgt.pos - self.pos
        dist = d.length()

        if self.shoot_cd <= 0 and dist <= RANGED_MAX_SHOOT_DIST:
            if game.is_world_pos_onscreen(self.pos, margin=RANGED_SHOOT_IF_ONSCREEN_MARGIN):
                if (not RANGED_LOS_ENABLED) or game.has_line_of_sight(self.pos, tgt.pos):
                    if dist > 1:
                        spd = RANGED_BULLET_SPEED_BASE + 60.0 * game.diff_eased
                        dmg = int(round(lerp(RANGED_DAMAGE_BASE, RANGED_DAMAGE_HARD, game.diff_eased)))
                        ally = self.is_charmed()
                        # A brainwashed shooter leads its target like a real gunner; a hostile
                        # shooter still fires at where you are, so it stays dodgeable.
                        if ally:
                            aim = game.predict_intercept(self.pos, tgt, spd)
                            dirn = aim.normalize() if aim.length_squared() > 1e-6 else d.normalize()
                        else:
                            dirn = d.normalize()
                        vel = dirn * spd
                        # Ally rounds live in the player's list and hit enemies instead of you.
                        store = game.projectiles if ally else game.enemy_projectiles
                        if len(store) < MAX_PROJECTILES:
                            b = Projectile(
                                self.pos + dirn * (self.radius + 6),
                                vel,
                                damage=dmg * (2 if ally else 1),
                                owner="ally" if ally else "enemy",
                                color=C_CHARM if ally else C_EBULLET,
                                radius=BULLET_RADIUS_ENEMY,
                                lifetime=RANGED_BULLET_LIFETIME,
                                source_enemy=self,
                            )
                            store.append(b)
                        game.audio_play("enemy_shoot")
                    self.shoot_cd = random.uniform(RANGED_COOLDOWN_MIN, RANGED_COOLDOWN_MAX)


class Tank(EnemyBase):
    def __init__(self, pos, hp, speed):
        super().__init__(pos, hp, speed, radius=ENEMY_RADIUS_TANK, color=C_TANK)
        self.damage_contact = 2
        self.score_value = 24

    def update(self, dt, game):
        tgt = game.enemy_target(self)
        if tgt is None:
            self.vel *= math.exp(-dt * 3.0)
            self.pos += self.vel * dt
            game.resolve_circle_walls(self, damping=0.15)
            return
        d = tgt.pos - self.pos
        if d.length_squared() > 1:
            desired = d.normalize() * self.effective_speed()
            self.vel = self.vel.lerp(desired, 1 - math.exp(-dt * 4.0))
        self.pos += self.vel * dt
        game.resolve_circle_walls(self, damping=0.15)


class Sprinter(EnemyBase):
    def __init__(self, pos, hp, speed):
        super().__init__(pos, hp, speed, radius=ENEMY_RADIUS_SPRINTER, color=C_SPRINTER)
        self.damage_contact = 1
        self.score_value = 10

    def update(self, dt, game):
        tgt = game.enemy_target(self)
        if tgt is None:
            self.vel *= math.exp(-dt * 3.0)
            self.pos += self.vel * dt
            game.resolve_circle_walls(self, damping=0.25)
            return
        d = tgt.pos - self.pos
        if d.length_squared() > 1:
            desired = d.normalize() * self.effective_speed()
            self.vel = self.vel.lerp(desired, 1 - math.exp(-dt * 9.0))
        self.pos += self.vel * dt
        game.resolve_circle_walls(self, damping=0.25)


class Dasher(EnemyBase):
    def __init__(self, pos, hp, speed):
        super().__init__(pos, hp, speed, radius=ENEMY_RADIUS_DASHER, color=C_DASHER)
        self.damage_contact = 2
        self.score_value = 20
        self.dash_cd = random.uniform(2.2, 3.0)
        self.dash_time = 0.0

    def update(self, dt, game):
        self.dash_cd -= dt
        self.dash_time = max(0.0, self.dash_time - dt)

        tgt = game.enemy_target(self)
        if tgt is None:
            self.vel *= math.exp(-dt * 3.0)
            self.pos += self.vel * dt
            game.resolve_circle_walls(self, damping=0.18)
            return
        d = tgt.pos - self.pos
        dist2 = d.length_squared()

        if self.dash_time > 0:
            if dist2 > 1:
                steer = d.normalize()
                self.vel = self.vel.lerp(steer * (self.effective_speed() * 2.6), 1 - math.exp(-dt * 10.0))
        else:
            if dist2 > 1:
                desired = d.normalize() * self.effective_speed()
                self.vel = self.vel.lerp(desired, 1 - math.exp(-dt * 6.0))

            if self.dash_cd <= 0 and dist2 < (620 * 620):
                self.dash_time = 0.22
                self.dash_cd = lerp(3.0, 2.0, game.diff_eased) + random.uniform(-0.15, 0.15)

        self.pos += self.vel * dt
        game.resolve_circle_walls(self, damping=0.18)

    def draw(self, surf, cam):
        super().draw(surf, cam)
        if self.dash_cd < 0.55:
            p = (int(self.pos.x - cam.x), int(self.pos.y - cam.y))
            circle_outline(surf, (230, 200, 255), p, self.radius + 10, 2)


class Boss(EnemyBase):
    """Big slow boss. Spawns every N waves. No normal spawns while alive."""
    def __init__(self, pos, hp, speed, wave_index: int):
        super().__init__(pos, hp, speed, radius=36, color=C_BOSS)
        self.damage_contact = 1
        self.score_value = 300 + wave_index * 25
        self.wave_index = wave_index
        self.shoot_cd = 1.4
        self.shoot_cd_base = 1.4
        self.volley = 3
        self.volley_spread = 12.0
        self.bullet_speed = 270.0
        self.bullet_damage = 1 + max(0, (wave_index // 10) - 1) * 2 # Boss damage
        self.bullet_life = 1.5
        self.enraged = False

    def apply_charm(self, duration: float):
        # Immune: a brainwashed boss can never be killed, so the boss fight (and the run) would
        # never end - wave progression and normal spawns both wait on it.
        return

    def take_damage(self, dmg: int, knock_dir: Vector2, knockback: float, weapon_id: Optional[str] = None, from_player: bool = False):
        # Boss has knockback resistance
        super().take_damage(dmg, knock_dir, knockback * 0.35, weapon_id=weapon_id, from_player=from_player)

    def update(self, dt, game):
        # Enrage at low HP: shoots faster
        if (not self.enraged) and self.hp < self.hp_max * 0.35:
            self.enraged = True
            self.shoot_cd_base = max(0.45, self.shoot_cd_base * 0.68)
            self.volley = int(min(12, self.volley + 2))
            self.volley_spread += 4.0

        self.shoot_cd -= dt

        # Slow pursuit (of the player, or of its former friends once brainwashed)
        tgt = game.enemy_target(self)
        if tgt is None:
            self.vel *= math.exp(-dt * 3.0)
            self.pos += self.vel * dt
            game.resolve_circle_walls(self, damping=0.12)
            return
        d = tgt.pos - self.pos
        if d.length_squared() > 1:
            desired = d.normalize() * self.effective_speed()
            self.vel = self.vel.lerp(desired, 1 - math.exp(-dt * 3.2))
        self.pos += self.vel * dt
        game.resolve_circle_walls(self, damping=0.12)

        # Shoot if on screen-ish and has LOS
        dist = d.length()
        if self.shoot_cd <= 0 and dist < 820:
            if game.is_world_pos_onscreen(self.pos, margin=120):
                if (not RANGED_LOS_ENABLED) or game.has_line_of_sight(self.pos, tgt.pos):
                    if dist > 1:
                        base_dir = d.normalize()
                        # fire a small volley spread
                        if self.volley <= 1:
                            angles = [0.0]
                        else:
                            angles = []
                            for i in range(self.volley):
                                t = i / (self.volley - 1)
                                angles.append(lerp(-self.volley_spread * 0.5, self.volley_spread * 0.5, t))

                        spd = self.bullet_speed + 90.0 * game.diff_eased + (30.0 if self.enraged else 0.0)
                        dmg = int(self.bullet_damage + 2 * game.diff_eased)

                        charmed = self.is_charmed()
                        store = game.projectiles if charmed else game.enemy_projectiles
                        b_owner = "ally" if charmed else "enemy"
                        b_color = C_CHARM if charmed else C_EBULLET
                        for ang in angles:
                            if len(store) >= MAX_PROJECTILES:
                                break
                            dirn = base_dir.rotate(ang)
                            b = Projectile(
                                self.pos + dirn * (self.radius + 8),
                                dirn * spd,
                                damage=dmg,
                                owner=b_owner,
                                color=b_color,
                                radius=5,
                                lifetime=self.bullet_life,
                                source_enemy=self,
                            )
                            store.append(b)

                        game.audio_play("enemy_shoot")
            self.shoot_cd = self.shoot_cd_base + random.uniform(-0.12, 0.18)

    def draw(self, surf, cam):
        p = (int(self.pos.x - cam.x), int(self.pos.y - cam.y))
        col = (255, 255, 255) if self.hit_flash > 0 else self.color
        shade_body(surf, p, self.radius, col)
        edge = C_BOSS_EDGE if not self.enraged else (255, 235, 150)
        circle_outline(surf, edge, p, self.radius + 5, 3)
        circle_outline(surf, (25, 25, 35), p, self.radius + 10, 2)
        if self.enraged:
            circle_outline(surf, (255, 200, 90), p, self.radius + 15, 2)

        # tiny hp bar over head
        w = self.radius * 2 + 30
        h = 7
        x = p[0] - w // 2
        y = p[1] - self.radius - 16
        frac = clamp(self.hp / max(1.0, self.hp_max), 0, 1)
        pygame.draw.rect(surf, (10, 12, 16), pygame.Rect(x - 1, y - 1, w + 2, h + 2), border_radius=4)
        if frac > 0:
            pygame.draw.rect(surf, (255, 120, 140), pygame.Rect(x, y, max(2, int(w * frac)), h), border_radius=3)
