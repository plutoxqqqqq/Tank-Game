"""Waves, difficulty ramp, enemy/boss spawns, mutators and pickups."""
from __future__ import annotations

import math
import random
import sys
import time
import traceback
from typing import Dict, List, Optional, Tuple

import pygame
from pygame.math import Vector2

from tankgame.config import *
from tankgame.util import *
from tankgame.ui.text import *
from tankgame.audio import *
from tankgame.save import SaveManager
from tankgame.data.weapons import WEAPONS
from tankgame.data.traits import TRAITS, trait_of, TraitDef
from tankgame.data.upgrades import UPGRADES, UPGRADES_BY_ID, UpgradeDef
from tankgame.data.shop import (SHOP_ITEMS, SHOP_ITEMS_BY_ID, SHOP_ITEMS_BY_WEAPON,
                                SHOP_ITEMS_BY_MAP, ShopItemDef, COSMETICS, COSMETICS_BY_ID,
                                DEFAULT_COSMETICS, BUNDLES, CosmeticDef, BundleDef,
                                BUNDLE_ONLY_COSMETIC_VALUE)
from tankgame.data.maps import MAPS, MAPS_BY_ID, MapDef, map_of
from tankgame.data.mutators import MUTATORS, MUTATORS_BY_ID, MutatorDef
from tankgame.data.minigames import (MINIGAMES, MINIGAMES_BY_ID, MinigameDef,
                                      METEOR_TELEGRAPH_START, METEOR_TELEGRAPH_END,
                                      METEOR_RADIUS, METEOR_MAX_ACTIVE)
from tankgame.data.mastery import MAX_MASTERY_LEVEL, mastery_requirements
from tankgame.entities.player import Player
from tankgame.entities.enemies import (EnemyBase, Chaser, Ranged, Tank, Sprinter, Dasher,
                                        Pink, Boss)
from tankgame.entities.projectile import Projectile
from tankgame.entities.pickup import Pickup
from tankgame.entities.fx import Particle, FloatingText
from tankgame.entities.drone import Drone
from tankgame.entities.meteor import Meteor
from tankgame.art.tank_art import draw_tank
from tankgame.ui.widgets import Button, TabButton




class ProgressionMixin:

    def update_difficulty(self):
        self.difficulty = clamp(self.survival_time / DIFFICULTY_RAMP_TIME, 0.0, 1.0)
        self.diff_eased = smoothstep(self.difficulty)

    def current_enemy_cap(self) -> int:
        return int(round(lerp(ENEMY_CAP_BASE, ENEMY_CAP_HARD, self.diff_eased)))

    def active_enemy_count(self) -> int:
        """Hostiles only: a hypnotised enemy has joined you and must not count against the cap,
        or a permanent-charm build would fill the arena and stall every future spawn."""
        return sum(1 for e in self.enemies if not e.is_charmed())

    # ---------------- Visibility / LOS ----------------

    def spawn_enemy(self, kind: str):
        player = self.player
        spawn = self._find_spawn_point(player.pos, ENEMY_SPAWN_DIST)

        mut = self.wave_mutator
        hp_mul = lerp(ENEMY_HP_BASE_MUL, ENEMY_HP_HARD_MUL, self.diff_eased)
        if mut is not None:
            hp_mul *= mut.hp_mul
        spd_mul = mut.speed_mul if mut is not None else 1.0

        if kind == "chaser":
            spd = lerp(CHASER_SPEED_BASE, CHASER_SPEED_HARD, self.diff_eased) * spd_mul
            e = Chaser(spawn, hp=42 * hp_mul, speed=spd)
        elif kind == "ranged":
            spd = lerp(RANGED_SPEED_BASE, RANGED_SPEED_HARD, self.diff_eased) * spd_mul
            e = Ranged(spawn, hp=58 * hp_mul, speed=spd)
        elif kind == "tank":
            spd = lerp(TANK_SPEED_BASE, TANK_SPEED_HARD, self.diff_eased) * spd_mul
            e = Tank(spawn, hp=125 * hp_mul, speed=spd)
        elif kind == "sprinter":
            spd = lerp(SPRINTER_SPEED_BASE, SPRINTER_SPEED_HARD, self.diff_eased) * spd_mul
            e = Sprinter(spawn, hp=28 * hp_mul, speed=spd)
        else:
            spd = lerp(DASHER_SPEED_BASE, DASHER_SPEED_HARD, self.diff_eased) * spd_mul
            e = Dasher(spawn, hp=72 * hp_mul, speed=spd)

        elite_chance = lerp(ELITE_CHANCE_BASE, ELITE_CHANCE_HARD, self.diff_eased)
        if mut is not None:
            elite_chance *= mut.elite_mul
        if self.wave >= ELITE_MIN_WAVE and random.random() < elite_chance:
            self.make_elite(e)

        self.enemies.append(e)

    def make_elite(self, enemy: EnemyBase) -> EnemyBase:
        """Golden variants: beefier, faster, worth far more and often carrying a power-up."""
        enemy.elite = True
        enemy.hp_max *= ELITE_HP_MUL
        enemy.hp = enemy.hp_max
        enemy.speed *= 1.08
        enemy.radius = int(enemy.radius * ELITE_RADIUS_MUL)
        enemy.score_value = int(enemy.score_value * ELITE_SCORE_MUL)
        return enemy

    def spawn_boss(self, clear_field: bool = True, hp_mul: float = 1.0,
                   retinue: bool = True, banner: bool = True):
        # Normal waves clear the field so the boss has the arena to itself. Impossible Mode asks for
        # several at once, so it opts out of the clear and scales them down to stay beatable.
        if clear_field:
            self.enemies.clear()
            self.enemy_projectiles.clear()

        dist = BOSS_SPAWN_DIST
        ang = random.uniform(0, math.tau)
        pos = self.player.pos + Vector2(math.cos(ang), math.sin(ang)) * dist
        pos.x = clamp(pos.x, 120, ARENA_W - 120)
        pos.y = clamp(pos.y, 120, ARENA_H - 120)

        tries = 24
        while tries > 0 and any(r.inflate(60, 60).collidepoint(pos.x, pos.y) for r in self.obstacles):
            ang = random.uniform(0, math.tau)
            pos = self.player.pos + Vector2(math.cos(ang), math.sin(ang)) * dist
            pos.x = clamp(pos.x, 120, ARENA_W - 120)
            pos.y = clamp(pos.y, 120, ARENA_H - 120)
            tries -= 1

        # Boss scaling tracks the player's power curve. Every stage should still be a real fight, so
        # HP grows with both stage and raw wave, and the boss's attacks get faster, wider and deadlier
        # instead of staying a fixed peashooter you can out-heal.
        stage = max(1, self.wave // BOSS_EVERY_WAVES)
        base_hp = 1400.0
        wave_mul = 1.0 + 1.15 * (stage - 1) + 0.05 * (self.wave - 1)
        diff_mul = 1.0 + 0.95 * self.diff_eased
        hp = base_hp * wave_mul * diff_mul * hp_mul

        speed = 74.0 + 24.0 * self.diff_eased + 5.0 * (stage - 1)
        boss = Boss(pos, hp=hp, speed=speed, wave_index=self.wave)
        # Offensive threat: fire faster, throw more shots, hit harder as the run matures.
        boss.shoot_cd_base = max(0.58, 1.35 - 0.07 * (stage - 1) - 0.18 * self.diff_eased)
        boss.volley = int(min(9, 2 + stage))
        boss.volley_spread = 10.0 + 2.2 * stage
        boss.bullet_speed = 275.0 + 26.0 * (stage - 1) + 70.0 * self.diff_eased
        boss.bullet_damage = 2 + 3 * (stage - 1) + int(round(2.0 * self.diff_eased))
        self.enemies.append(boss)

        # Boss retinue: one pink swarmer per wave number, ringed around the boss. Wave 10 drops 10,
        # wave 20 -> 20, and so on, so a boss wave is a crowd fight, not a duel. Nightmare mode asks
        # for bosses only, so it opts out entirely.
        retinue_count = max(0, int(self.wave)) if retinue else 0
        for i in range(retinue_count):
            ang = math.tau * i / max(1, retinue_count) + random.uniform(-0.15, 0.15)
            rad = random.uniform(80.0, 190.0)
            p = boss.pos + Vector2(math.cos(ang), math.sin(ang)) * rad
            p.x = clamp(p.x, 40, ARENA_W - 40)
            p.y = clamp(p.y, 40, ARENA_H - 40)
            pink_hp = PINK_HP_BASE * (1.0 + 0.09 * (self.wave - 1)) * hp_mul
            pink_spd = lerp(PINK_SPEED_BASE, PINK_SPEED_HARD, self.diff_eased)
            self.enemies.append(Pink(p, hp=pink_hp, speed=pink_spd))

        self.in_boss_fight = True
        self.boss_alive = True
        self.shake = max(self.shake, 10.0)
        if banner:
            self.set_wave_banner("BOSS INCOMING", 2.3)
            self.add_float_text(self.player.pos + Vector2(-10, -40), "BOSS!", C_ACCENT_2, life=1.0)

    def on_boss_killed(self, boss: Boss):
        center = Vector2(boss.pos)
        self.player._grant_score(boss.score_value)
        self.run_stats["bosses"] += 1
        self.update_challenges("boss_kills", 1)
        self.update_challenges("kills", 1)
        if boss.last_hit_by_player and boss.last_hit_weapon_id:
            self.update_mastery(boss.last_hit_weapon_id, kills=1)
            self.update_challenges("weapon_kills", 1, weapon_id=boss.last_hit_weapon_id)

        stage = max(1, self.wave // BOSS_EVERY_WAVES)
        bonus = 10 + 4 * (stage - 1)
        self.run_bonus_coins += bonus
        self.add_float_text(self.player.pos + Vector2(0, -54), f"+{bonus} COINS (BANKED)", C_COIN, life=1.0)

        xp_each = int(XP_ORB_VALUE_BASE * (3.0 + 1.0 * self.diff_eased))
        for _ in range(18):
            ang = random.uniform(0, math.tau)
            rad = random.uniform(10, 120)
            p = center + Vector2(math.cos(ang), math.sin(ang)) * rad
            p.x = clamp(p.x, 40, ARENA_W - 40)
            p.y = clamp(p.y, 40, ARENA_H - 40)
            self.pickups.append(Pickup(p, "xp", xp_each))

        for _ in range(2):
            p = center + Vector2(random.uniform(-60, 60), random.uniform(-60, 60))
            self.pickups.append(Pickup(p, "health", HEALTH_PACK_AMOUNT + 1))

        ptype = random.choice(self.powerup_pool())
        self.pickups.append(Pickup(center + Vector2(0, -20), "power", 0, ptype))

        self._spawn_hit_particles(center, self.get_explosion_color())
        self.shake = max(self.shake, 12.0)

        self.in_boss_fight = False
        self.boss_alive = False
        self.boss_grace_timer = BOSS_GRACE_AFTER_DEATH

    def drop_pickups(self, pos: Vector2):
        xp = XP_ORB_VALUE_BASE + int(self.diff_eased * 6)
        self.pickups.append(Pickup(pos, "xp", xp))

        health_chance = 0.09 + 0.07 * self.diff_eased
        if random.random() < health_chance:
            self.pickups.append(Pickup(pos + Vector2(random.uniform(-10, 10), random.uniform(-10, 10)),
                                       "health", HEALTH_PACK_AMOUNT))

    def spawn_powerup_at(self, pos: Vector2):
        if sum(1 for p in self.pickups if p.kind == "power") >= POWERUP_MAX_ON_MAP + 1:
            return
        ptype = random.choice(self.powerup_pool())
        self.pickups.append(Pickup(pos, "power", 0, ptype))

    def powerup_pool(self) -> List[str]:
        """Which power-ups can drop: the Drone Range pickup only matters once you have drones."""
        pool = ["damage_boost", "rapid_fire", "speed_boost", "shield"]
        if self.player.get_drone_count() > 0:
            pool.append("drone_range")
        return pool

    def try_spawn_powerup(self, dt):
        self.powerup_timer -= dt
        if self.powerup_timer > 0:
            return
        self.powerup_timer = random.uniform(POWERUP_SPAWN_MIN, POWERUP_SPAWN_MAX)

        powerups_on_map = sum(1 for p in self.pickups if p.kind == "power")
        if powerups_on_map >= POWERUP_MAX_ON_MAP:
            return

        attempts = 40
        while attempts > 0:
            pos = Vector2(random.uniform(80, ARENA_W - 80), random.uniform(80, ARENA_H - 80))
            if not self.valid_pickup_spawn(pos, min_player_dist=260.0):
                attempts -= 1
                continue
            ptype = random.choice(self.powerup_pool())
            self.pickups.append(Pickup(pos, "power", 0, ptype))
            break

    # ---------------- Coins on run end ----------------

    def set_wave_banner(self, text: str, duration: float = 2.0):
        self.wave_banner_text = text
        self.wave_banner_timer = duration

    def roll_mutator(self) -> Optional[MutatorDef]:
        """Pick this wave's twist. Never repeats back to back, so runs stay varied but readable."""
        if self.wave < MUTATOR_MIN_WAVE or random.random() >= MUTATOR_CHANCE:
            return None
        options = [m for m in MUTATORS if m.id != self.last_mutator_id] or MUTATORS
        mut = random.choice(options)
        self.last_mutator_id = mut.id
        return mut

    # ---------------- Pickup collect ----------------

    def _compact_xp_orbs(self):
        """Fold far-away XP orbs together once the floor gets crowded. Total XP is preserved."""
        orbs = [p for p in self.pickups if p.kind == "xp"]
        if len(orbs) <= XP_ORB_SOFT_CAP:
            return
        ppos = self.player.pos
        orbs.sort(key=lambda p: (p.pos - ppos).length_squared(), reverse=True)
        excess = len(orbs) - XP_ORB_SOFT_CAP
        far = orbs[:excess * 2]
        merged = set()
        for i in range(0, len(far) - 1, 2):
            keep, gone = far[i], far[i + 1]
            keep.value += gone.value
            merged.add(id(gone))
        if merged:
            self.pickups = [p for p in self.pickups if id(p) not in merged]

    def _handle_pickup_collect(self, p: Pickup) -> bool:
        if p.kind == "health" and self.player.hp >= self.player.max_hp:
            return False   # leave it for later instead of wasting it at full HP
        if (self.player.pos - p.pos).length_squared() <= (PLAYER_RADIUS + p.radius()) ** 2:
            if p.kind == "xp":
                self.player.gain_xp(p.value)
                self.audio_play("powerup", 0.05)
            elif p.kind == "health":
                self.player._grant_heal(min(p.value, self.player.max_hp - self.player.hp))
                self.player.hp = min(self.player.max_hp, self.player.hp + p.value)
            else:
                self.player.apply_powerup(p.power_type)
                self.run_stats["powerups"] += 1
                self.audio_play("powerup")
                self.add_float_text(self.player.pos + Vector2(0, -26),
                                    p.power_type.replace("_", " ").upper(), C_ACCENT)
            return True
        return False

    # ---------------- Combat collisions ----------------
