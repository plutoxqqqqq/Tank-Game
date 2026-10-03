"""Starting, restarting and banking a run, plus the level-up pool."""
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




class RunMixin:

    def apply_meta_upgrades_to_player(self):
        dmg_lvl = int(self.save.shop_levels.get("meta_damage", 0))
        mov_lvl = int(self.save.shop_levels.get("meta_move", 0))
        hp_lvl = int(self.save.shop_levels.get("meta_hp", 0))
        xp_lvl = int(self.save.shop_levels.get("meta_xp", 0))
        dash_lvl = int(self.save.shop_levels.get("meta_dash", 0))
        armor_lvl = int(self.save.shop_levels.get("meta_armor", 0))
        bsp_lvl = int(self.save.shop_levels.get("meta_bulletspeed", 0))

        self.player.meta_damage_mul = 1.0 + 0.05 * dmg_lvl
        self.player.meta_move_mul = 1.0 + 0.05 * mov_lvl
        self.player.meta_xp_mul = 1.0 + 0.05 * xp_lvl
        self.player.meta_dash_mul = max(0.55, 1.0 - 0.05 * dash_lvl)
        self.player.meta_armor_mul = max(0.70, 1.0 - 0.05 * armor_lvl)
        self.player.meta_bulletspd_mul = 1.0 + 0.05 * bsp_lvl

        if hp_lvl > 0:
            self.player.max_hp += hp_lvl
            self.player.hp += hp_lvl

        self.player.outline_color = self.get_outline_color()

    def reset_run_stats(self):
        self.run_stats = {
            "kills": 0, "bosses": 0, "damage": 0.0,
            "shots": 0, "hits": 0, "dmg_taken": 0, "powerups": 0,
        }
        self.burn_credit = 0.0

    def accuracy(self) -> float:
        shots = self.run_stats.get("shots", 0)
        if shots <= 0:
            return 0.0
        return 100.0 * self.run_stats.get("hits", 0) / shots

    # ---------------- Run reset ----------------

    def start_run(self):
        self.set_state("playing")

        # Always ensure weapon keys are synced before starting
        self.save.ensure_weapons(list(WEAPONS.keys()))
        weapon_id = self.save.selected_weapon if self.save.weapon_unlocks.get(self.save.selected_weapon, False) else "pistol"

        self.player = Player(Vector2(ARENA_W / 2, ARENA_H / 2), weapon_id=weapon_id)
        self.apply_meta_upgrades_to_player()
        self.counted_game = False

        self.projectiles.clear()
        self.enemy_projectiles.clear()
        self.enemies.clear()
        self.pickups.clear()
        self.particles.clear()
        self.float_texts.clear()

        self.current_map = self.roll_map()
        self._generate_obstacles()

        self.survival_time = 0.0
        self.reset_run_stats()
        self.wave = 1
        # wave_time is per-run so the Rapid minigame can shorten every wave to 3 seconds.
        self.wave_time = WAVE_TIME_BASE
        self.wave_timer = self.wave_time
        self.spawn_timer = 0.0
        self.drones.clear()
        self.drone_phase = 0.0
        self.spawn_interval = SPAWN_RATE_BASE
        self.wave_mutator = None
        self.last_mutator_id = ""

        self.difficulty = 0.0
        self.diff_eased = 0.0

        self.shake = 0.0
        self.powerup_timer = random.uniform(POWERUP_SPAWN_MIN, POWERUP_SPAWN_MAX)

        self.last_run_coins_earned = 0
        self.coins_awarded_this_gameover = False
        self.run_bonus_coins = 0
        self.leaderboard_recorded = False
        self.new_best = False
        self.best_score_at_start = self.save.best_score()

        self.pending_levelups = 0
        self.level_choices = []
        self.level_cards = []
        self.wave_banner_text = ""
        self.wave_banner_timer = 0.0
        self.sfx_timers.clear()
        self.progress_dirty = False
        self.progress_dirty_timer = 0.0
        self.trail_timer = 0.0
        self.set_wave_banner(f"{self.current_map.name.upper()}  \u2014  SURVIVE!", 1.8)

        self.in_boss_fight = False
        self.boss_alive = False
        self.boss_grace_timer = 0.0

        # A fresh run is never a minigame until start_minigame says so.
        self.minigame = None
        self.meteors = []
        self.hazards = []
        self.dash_only = False
        self.minigame_time = 0.0
        self.minigame_progress = 0.0

        # Once every run value is settled, rebaseline the referee against the fresh run.
        self._ac_new_run = True
        self.anticheat.reset()
        self._ac_new_run = False

    def bank_run(self):
        """Bank a run's coins + leaderboard entry. Used on death and when leaving early."""
        self.award_coins_if_needed()
        self.record_leaderboard_if_needed()

    def abandon_run(self):
        """Quitting from the pause menu used to throw away every coin the run earned."""
        if self.minigame is not None:
            # Aborting a minigame forfeits the payout - back to the list, no banking.
            self.minigame = None
            self.meteors = []
            self.dash_only = False
            self.set_state("minigames")
            self.build_minigame_buttons()
            return
        self.bank_run()
        self.set_state("menu")

    def restart_run(self):
        if self.minigame is not None:
            # Restarting a minigame restarts that minigame (and never banks its payout).
            self.start_minigame(self.minigame.id)
            return
        self.bank_run()
        self.start_run()

    def ultra_chance(self) -> float:
        """Very rare at wave 1 (1%) and nudging up 0.5% per wave, so long runs see a few."""
        return clamp(ULTRA_CHANCE_BASE + max(0, self.wave - 1) * ULTRA_CHANCE_PER_WAVE,
                     0.0, ULTRA_CHANCE_MAX)

    def roll_ultra(self, weapon_id: str) -> Optional[UpgradeDef]:
        """Offer this tank's ultra card, if it still has one left to take."""
        options = [
            u for u in UPGRADES
            if u.ultra and u.weapon_id == weapon_id
            and self.player.upgrade_counts.get(u.id, 0) == 0
        ]
        if not options or random.random() >= self.ultra_chance():
            return None
        return random.choice(options)

    def open_levelup(self):
        self.set_state("levelup")
        pid = self.player.weapon_id

        # "Ultra Only" minigame: the pool is nothing but ultra cards. Prefer ones you have not taken
        # yet; once they are exhausted, everything is fair game again so the run never runs dry.
        if self.minigame is not None and self.minigame.id == "ultra_only":
            fresh = [u for u in UPGRADES if u.ultra and self.player.upgrade_counts.get(u.id, 0) == 0]
            everything = [u for u in UPGRADES if u.ultra]
            source = fresh if len(fresh) >= 3 else everything
            self.level_choices = random.sample(source, min(3, len(source)))
        else:
            # Tank-exclusive cards only show up while driving that tank, and never offer a wasted
            # heal. Ultras are kept out of the normal pool - they arrive through the ultra roll.
            pool = [
                u for u in UPGRADES
                if (not u.ultra)
                and (not u.weapon_id or u.weapon_id == pid)
                and not (u.id == "heal" and self.player.hp >= self.player.max_hp)
            ]
            count = min(3, len(pool))
            self.level_choices = random.sample(pool, count)

            # Ultra tier: yellow, overpowered, tank-specific, and rare. It replaces the last slot so
            # the choice stays three cards, never four.
            ultra = self.roll_ultra(pid)
            if ultra is not None and self.level_choices:
                self.level_choices[-1] = ultra

        cx = WIDTH // 2
        bw, bh = 720, 90
        top = HEIGHT // 2 - 132
        self.level_cards = []
        for i, up in enumerate(self.level_choices):
            rect = pygame.Rect(cx - bw // 2, top + i * (bh + 16), bw, bh)
            self.level_cards.append((rect, up))

    def pick_upgrade(self, up: UpgradeDef):
        self.player.apply_upgrade(up.id)
        self.audio_play("levelup")
        self.pending_levelups = max(0, self.pending_levelups - 1)
        if self.pending_levelups > 0:
            self.open_levelup()
        else:
            self.set_state("playing")
