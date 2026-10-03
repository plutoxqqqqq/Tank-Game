"""Minigame lifecycle and meteors."""
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




class MinigameMixin:

    def open_minigames(self):
        self.set_state("minigames")
        self.build_minigame_buttons()

    def build_minigame_buttons(self):
        """Lay the minigame rows out so they always fit above the result banner and Back button."""
        cx = WIDTH // 2
        w = min(760, WIDTH - 80)
        n = max(1, len(MINIGAMES))
        gap = 5
        self.mg_list_top = 164
        bottom = HEIGHT - 92
        self.mg_row_h = max(34, min(52, (bottom - self.mg_list_top - gap * (n - 1)) // n))
        self.mg_gap = gap
        self.mg_result_rect = pygame.Rect(cx - w // 2, 108, w, 46)
        self.mg_play_buttons = []
        for i, mg in enumerate(MINIGAMES):
            rect = pygame.Rect(cx - w // 2, self.mg_list_top + i * (self.mg_row_h + gap), w, self.mg_row_h)
            self.mg_play_buttons.append((rect, mg))
        self.mg_back_btn = Button(pygame.Rect(40, HEIGHT - 80, 220, 52), "Back", lambda: self.set_state("menu"))

    def start_minigame(self, mg_id: str):
        mg = MINIGAMES_BY_ID.get(mg_id)
        if mg is None:
            return
        self.start_run()
        self.minigame = mg
        self.minigame_result = None
        self.minigame_time = 0.0
        self.minigame_progress = 0.0
        self.meteors = []
        self.hazards = []
        self.meteor_cd = 0.7
        self.dash_only = False
        self.enemies.clear()
        self.wave_mutator = None

        if mg.id == "blitz":
            self.spawn_interval = BLITZ_SPAWN_INTERVAL
        elif mg.id == "rapid":
            # Every wave lasts three seconds, so the whole run is a blur of new waves.
            self.wave_time = RAPID_WAVE_TIME
            self.wave_timer = RAPID_WAVE_TIME
        elif mg.id == "dash_only":
            self.dash_only = True
        elif mg.id == "glass":
            self.player.max_hp = 1
            self.player.hp = 1
            # Every shot hits for a flat 99 regardless of weapon, upgrades, or multipliers.
            self.player.flat_damage = 99
        elif mg.id == "impossible":
            for _ in range(3):
                self.spawn_boss(clear_field=False, hp_mul=0.5)
        elif mg.id == "nightmare":
            # Lock the run at wave 50 so every boss spawns with maximum stage scaling, and freeze the
            # wave/spawn clocks so normal enemies can never appear - bosses replace every spawn.
            self.wave = 50
            self.wave_time = 1.0e9
            self.wave_timer = 1.0e9
            self.spawn_interval = 1.0e9
            self.spawn_timer = 1.0e9
            self.in_boss_fight = False
            self.boss_grace_timer = 0.0

        self.set_wave_banner(mg.name.upper(), 2.2)
        # Minigame setup legitimately locks in HP/wave/flat-damage etc. - rebaseline the referee.
        self.anticheat.reset()

    def update_minigame(self, dt):
        mg = self.minigame
        if mg is None:
            return
        self.minigame_time += dt
        if mg.duration > 0.0:
            self.minigame_progress = clamp(self.minigame_time / mg.duration, 0.0, 1.0)

        if mg.id == "meteor":
            self._update_meteors(dt)
        elif mg.id == "impossible":
            # Three bosses, always. Refill as soon as one goes down.
            if self.boss_grace_timer <= 0.0:
                alive_bosses = [e for e in self.enemies if isinstance(e, Boss) and e.alive()]
                if len(alive_bosses) < 3:
                    self.spawn_boss(clear_field=False, hp_mul=0.5)
        elif mg.id == "nightmare":
            # Every spawn is a maxed wave-50 boss, and they ramp up in number over time. Held at
            # wave 50 so scaling never drifts, with the normal spawner kept frozen.
            self.wave = 50
            self._ac_wave = True
            self.wave_timer = 1.0e9
            self.spawn_timer = 1.0e9
            target = 1 + int(self.minigame_time // 15.0)
            alive_bosses = sum(1 for e in self.enemies if isinstance(e, Boss) and e.alive())
            if alive_bosses < target and self.boss_grace_timer <= 0.0:
                self.spawn_boss(clear_field=False, retinue=False, banner=False)

        if mg.duration > 0.0 and self.minigame_time >= mg.duration:
            self.finish_minigame(cleared=True)

    def _update_meteors(self, dt):
        mg = self.minigame
        self.meteor_cd -= dt
        if self.meteor_cd <= 0.0:
            self.meteor_cd = lerp(1.15, 0.42, self.minigame_progress)
            incoming = sum(1 for m in self.meteors if not m.landed)
            if incoming < METEOR_MAX_ACTIVE:
                ang = random.uniform(0, math.tau)
                dist = random.uniform(120.0, 440.0)
                pos = self.player.pos + Vector2(math.cos(ang), math.sin(ang)) * dist
                pos.x = clamp(pos.x, 60, ARENA_W - 60)
                pos.y = clamp(pos.y, 60, ARENA_H - 60)
                tele = lerp(METEOR_TELEGRAPH_START, METEOR_TELEGRAPH_END, self.minigame_progress)
                self.meteors.append(Meteor(pos, tele))
        for m in self.meteors:
            m.update(dt, self)
        self.meteors = [m for m in self.meteors if not m.done]

    def finish_minigame(self, cleared: bool):
        """Pay out on a minigame and drop the player back on the minigame list."""
        mg = self.minigame
        if mg is None:
            return
        if mg.duration > 0.0:
            progress = clamp(self.minigame_time / mg.duration, 0.0, 1.0)
        else:
            progress = self.minigame_progress
        frac = progress if cleared else progress * 0.6
        coins = int(round(mg.reward * (0.35 + 0.65 * frac)))
        if cleared:
            coins = int(round(coins * 1.15))
        coins = max(1, coins)
        self.anticheat.note_save()
        self.save.coins += coins
        if cleared:
            self.save.minigame_clears[mg.id] = self.save.minigame_clears.get(mg.id, 0) + 1
        self.save.minigame_best[mg.id] = max(float(self.save.minigame_best.get(mg.id, 0.0)), float(progress))
        self.save.save()
        self.minigame_result = {
            "id": mg.id, "name": mg.name, "coins": coins, "cleared": cleared,
            "time": self.minigame_time, "progress": progress,
        }
        self.audio_play("levelup")
        self.minigame = None
        self.meteors = []
        self.hazards = []
        self.dash_only = False
        self.minigame_time = 0.0
        self.set_state("minigames")
        self.build_minigame_buttons()

    # ---------------- Difficulty / caps ----------------
