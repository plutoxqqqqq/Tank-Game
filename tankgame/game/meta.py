"""Coins, shop, cosmetics, bundles, challenges and mastery."""
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




class MetaMixin:

    def _shop_items_for_tab(self) -> List[ShopItemDef]:
        if self.shop_tab == "meta":
            return [it for it in SHOP_ITEMS if it.kind == "meta"]
        if self.shop_tab == "weapons":
            return [it for it in SHOP_ITEMS if it.kind == "weapon"]
        if self.shop_tab == "maps":
            return [it for it in SHOP_ITEMS if it.kind == "map"]
        return []

    def _shop_rows_per_page(self, box: pygame.Rect, row_h: int = 72, gap: int = 12) -> int:
        step = row_h + gap
        usable = max(1, box.h - 24)
        return max(1, usable // step)

    # ---------------- Shop logic ----------------

    def open_shop(self):
        self.shop_tab = "meta"
        self.shop_page = 0
        if self.save.ensure_cosmetics(COSMETICS):
            self.save.save()
        self.set_state("shop")

    def open_settings(self):
        self.set_state("settings")

    def open_leaderboard(self):
        self.set_state("leaderboard")

    def open_challenges(self):
        self.challenges_view = "daily"
        self.set_state("challenges")

    # ---------------- Cosmetics ----------------

    def get_cosmetic(self, cosmetic_id: str) -> Optional[CosmeticDef]:
        return COSMETICS_BY_ID.get(cosmetic_id)

    def get_equipped_cosmetic(self, category: str) -> CosmeticDef:
        cosmetic_id = self.save.cosmetics_equipped.get(category)
        cosmetic = self.get_cosmetic(cosmetic_id) if cosmetic_id else None
        if cosmetic:
            return cosmetic
        fallback_id = DEFAULT_COSMETICS[category]
        return COSMETICS_BY_ID[fallback_id]

    def get_outline_color(self) -> Tuple[int, int, int]:
        return self.get_equipped_cosmetic("outline").color

    def get_bullet_color(self) -> Tuple[int, int, int]:
        return self.get_equipped_cosmetic("bullet").color

    def get_trail_cosmetic(self) -> CosmeticDef:
        return self.get_equipped_cosmetic("trail")

    def get_explosion_color(self) -> Tuple[int, int, int]:
        return self.get_equipped_cosmetic("explosion").color

    def buy_cosmetic(self, cosmetic: CosmeticDef):
        if cosmetic.bundle_only:
            return
        if self.save.cosmetics_unlocked.get(cosmetic.id, False):
            return
        if self.save.coins < cosmetic.cost:
            return
        self.anticheat.note_save()
        self.save.coins -= cosmetic.cost
        self.save.cosmetics_unlocked[cosmetic.id] = True
        self.save.cosmetics_equipped[cosmetic.category] = cosmetic.id
        self.save.save()
        self.audio_play("buy")

    def equip_cosmetic(self, cosmetic: CosmeticDef):
        if not self.save.cosmetics_unlocked.get(cosmetic.id, False):
            return
        self.save.cosmetics_equipped[cosmetic.category] = cosmetic.id
        self.save.save()
        self.audio_play("buy")

    def unequip_cosmetic(self, category: str):
        default_id = DEFAULT_COSMETICS.get(category)
        if not default_id:
            return
        self.anticheat.note_save()
        self.save.cosmetics_equipped[category] = default_id
        self.save.cosmetics_unlocked[default_id] = True
        self.save.save()
        self.audio_play("buy")

    # ---------------- Bundles ----------------

    def resolve_bundle_items(self, bundle: BundleDef) -> Tuple[List[str], List[str], List[str]]:
        available_weapons = [
            wid for wid in WEAPONS.keys() if not self.save.weapon_unlocks.get(wid, False)
        ]
        resolved_weapons: List[str] = []
        remaining_pool = [wid for wid in available_weapons if wid not in bundle.weapons]
        for wid in bundle.weapons:
            if not self.save.weapon_unlocks.get(wid, False):
                if wid not in resolved_weapons:
                    resolved_weapons.append(wid)
                if wid in remaining_pool:
                    remaining_pool.remove(wid)
                continue
            replacement = remaining_pool.pop(0) if remaining_pool else None
            if replacement:
                resolved_weapons.append(replacement)
        return resolved_weapons, list(bundle.meta), list(bundle.cosmetics)

    def cosmetic_bundle_value(self, cosmetic: CosmeticDef) -> int:
        if cosmetic.cost > 0:
            return cosmetic.cost
        if cosmetic.bundle_only:
            return BUNDLE_ONLY_COSMETIC_VALUE
        return 0

    def bundle_base_value(self, bundle: BundleDef) -> int:
        total = 0
        weapons, meta, cosmetics = self.resolve_bundle_items(bundle)
        for wid in weapons:
            item = SHOP_ITEMS_BY_WEAPON.get(wid)
            if item:
                total += item.base_cost
        for mid in meta:
            item = SHOP_ITEMS_BY_ID.get(mid)
            if item:
                total += item.base_cost
        for cid in cosmetics:
            cosmetic = COSMETICS_BY_ID.get(cid)
            if cosmetic:
                total += self.cosmetic_bundle_value(cosmetic)
        return total

    def bundle_owned_value(self, bundle: BundleDef) -> int:
        owned = 0
        weapons, meta, cosmetics = self.resolve_bundle_items(bundle)
        for wid in weapons:
            if self.save.weapon_unlocks.get(wid, False):
                item = SHOP_ITEMS_BY_WEAPON.get(wid)
                if item:
                    owned += item.base_cost
        for mid in meta:
            if int(self.save.shop_levels.get(mid, 0)) > 0:
                item = SHOP_ITEMS_BY_ID.get(mid)
                if item:
                    owned += item.base_cost
        for cid in cosmetics:
            if self.save.cosmetics_unlocked.get(cid, False):
                cosmetic = COSMETICS_BY_ID.get(cid)
                if cosmetic:
                    owned += self.cosmetic_bundle_value(cosmetic)
        return owned

    def bundle_price(self, bundle: BundleDef) -> int:
        base_value = self.bundle_base_value(bundle)
        owned_value = self.bundle_owned_value(bundle)
        remaining = max(0, base_value - owned_value)
        return int(remaining * (1.0 - bundle.discount))

    def bundle_is_owned(self, bundle: BundleDef) -> bool:
        if self.save.bundles_purchased.get(bundle.id, False):
            return True
        base_value = self.bundle_base_value(bundle)
        if base_value <= 0:
            return True
        return self.bundle_owned_value(bundle) >= base_value

    def buy_bundle(self, bundle: BundleDef):
        if self.bundle_is_owned(bundle):
            return
        cost = self.bundle_price(bundle)
        if cost <= 0 or self.save.coins < cost:
            return
        self.anticheat.note_save()
        self.save.coins -= cost
        weapons, meta, cosmetics = self.resolve_bundle_items(bundle)
        for wid in weapons:
            self.save.weapon_unlocks[wid] = True
        for mid in meta:
            item = SHOP_ITEMS_BY_ID.get(mid)
            if not item:
                continue
            current = int(self.save.shop_levels.get(mid, 0))
            self.save.shop_levels[mid] = min(item.max_level, current + 1)
        for cid in cosmetics:
            self.save.cosmetics_unlocked[cid] = True
        self.save.bundles_purchased[bundle.id] = True
        self.save.save()
        self.audio_play("buy")

    # ---------------- Challenges ----------------

    def _daily_key(self) -> str:
        return time.strftime("%Y-%j", time.localtime())

    def _weekly_key(self) -> str:
        return time.strftime("%Y-%V", time.localtime())

    def refresh_challenges(self):
        daily_key = self._daily_key()
        weekly_key = self._weekly_key()
        changed = False
        if self.save.daily_challenges.get("key") != daily_key:
            self.save.daily_challenges = {
                "key": daily_key,
                "generated_at": int(time.time()),
                "items": self._generate_daily_challenges(daily_key),
            }
            changed = True
        if self.save.weekly_challenges.get("key") != weekly_key:
            self.save.weekly_challenges = {
                "key": weekly_key,
                "generated_at": int(time.time()),
                "items": self._generate_weekly_challenges(weekly_key),
            }
            changed = True
        if changed:
            self.save.save()

    def _generate_daily_challenges(self, key: str) -> List[Dict[str, object]]:
        rng = random.Random(key)
        weapon_ids = list(WEAPONS.keys())
        # Only offer a weapon-focus goal for a tank the player can actually use right now.
        unlocked_ids = [wid for wid in weapon_ids if self.save.weapon_unlocks.get(wid, False)]
        candidates = [
            {"id": "daily_kills", "name": "Clear the Field", "desc": "Defeat 60 enemies.", "target": 60, "reward": 20, "metric": "kills"},
            {"id": "daily_waves", "name": "Hold the Line", "desc": "Survive 9 waves.", "target": 9, "reward": 10, "metric": "waves"},
            {"id": "daily_run", "name": "Warm-Up Run", "desc": "Complete 2 runs.", "target": 2, "reward": 5, "metric": "runs"},
        ]
        weapon_pick = rng.choice(unlocked_ids or ["pistol"])
        weapon_name = WEAPONS[weapon_pick].name
        candidates.append({
            "id": f"daily_weapon_{weapon_pick}",
            "name": f"Weapon Focus: {weapon_name}",
            "desc": f"Defeat 38 enemies using {weapon_name}.",
            "target": 38,
            "reward": 25,
            "metric": "weapon_kills",
            "weapon_id": weapon_pick,
        })
        count = rng.randint(1, 3)
        picks = rng.sample(candidates, count)
        return [
            {
                **c,
                "progress": 0,
                "claimed": False,
            }
            for c in picks
        ]

    def _generate_weekly_challenges(self, key: str) -> List[Dict[str, object]]:
        rng = random.Random(key)
        candidates = [
            {"id": "weekly_boss", "name": "Boss Hunter", "desc": "Defeat 5 bosses.", "target": 5, "reward": 110, "metric": "boss_kills"},
            {"id": "weekly_damage", "name": "Heavy Damage", "desc": "Deal 13500 total damage.", "target": 13500, "reward": 100, "metric": "damage"},
            {"id": "weekly_wave", "name": "Deep Run", "desc": "Reach wave 30.", "target": 30, "reward": 120, "metric": "high_wave"},
            {"id": "weekly_runs", "name": "Weekend Warrior", "desc": "Complete 12 runs.", "target": 12, "reward": 70, "metric": "runs"},
        ]
        count = rng.randint(1, 2)
        picks = rng.sample(candidates, count)
        return [
            {
                **c,
                "progress": 0,
                "claimed": False,
            }
            for c in picks
        ]

    def update_challenges(self, metric: str, amount: int, weapon_id: Optional[str] = None, absolute: bool = False):
        changed = False
        for bucket in (self.save.daily_challenges.get("items", []), self.save.weekly_challenges.get("items", [])):
            for item in bucket:
                if item.get("metric") != metric:
                    continue
                if metric == "weapon_kills" and item.get("weapon_id") != weapon_id:
                    continue
                if absolute:
                    item["progress"] = max(int(item.get("progress", 0)), int(amount))
                else:
                    item["progress"] = int(item.get("progress", 0)) + int(amount)
                if not item.get("claimed") and item["progress"] >= int(item.get("target", 0)):
                    item["claimed"] = True
                    reward = int(item.get("reward", 0))
                    self.anticheat.note_save()
                    self.save.coins += reward
                    self.add_float_text(self.player.pos + Vector2(0, -34), f"+{reward} COINS", C_COIN, life=1.0)
                changed = True
        if changed:
            self.progress_dirty = True

    def time_until_reset(self, kind: str) -> str:
        now = time.time()
        if kind == "daily":
            tomorrow = time.localtime(now + 86400)
            reset = time.mktime((tomorrow.tm_year, tomorrow.tm_mon, tomorrow.tm_mday, 0, 0, 0, 0, 0, -1))
        else:
            now_local = time.localtime(now)
            days_ahead = (7 - now_local.tm_wday) % 7
            if days_ahead == 0:
                days_ahead = 7
            next_week = time.localtime(now + days_ahead * 86400)
            reset = time.mktime((next_week.tm_year, next_week.tm_mon, next_week.tm_mday, 0, 0, 0, 0, 0, -1))
        remaining = max(0, int(reset - now))
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        return f"{hours}h {minutes}m"

    # ---------------- Mastery ----------------

    def update_mastery(self, weapon_id: str, hits: int = 0, kills: int = 0, wins: int = 0):
        if weapon_id not in WEAPONS:
            return
        stats, changed = self.save.ensure_mastery_entry(weapon_id)
        if changed:
            self.save.save()
        stats["hits"] = int(stats.get("hits", 0)) + hits
        stats["total_kills"] = int(stats.get("total_kills", 0)) + kills
        stats["total_wins"] = int(stats.get("total_wins", 0)) + wins

        if stats.get("level", 0) < MAX_MASTERY_LEVEL:
            stats["level_kills"] = int(stats.get("level_kills", 0)) + kills
            stats["level_wins"] = int(stats.get("level_wins", 0)) + wins

        leveled = False
        level = int(stats.get("level", 0))
        if level < MAX_MASTERY_LEVEL:
            req_kills, req_wins = mastery_requirements(level + 1)
            stats["req_kills"] = req_kills
            stats["req_wins"] = req_wins
            if stats["level_kills"] >= req_kills and stats["level_wins"] >= req_wins:
                stats["level"] = level + 1
                stats["level_kills"] = 0
                stats["level_wins"] = 0
                leveled = True
                if stats["level"] < MAX_MASTERY_LEVEL:
                    next_req_kills, next_req_wins = mastery_requirements(stats["level"] + 1)
                    stats["req_kills"] = next_req_kills
                    stats["req_wins"] = next_req_wins
        if leveled:
            self.add_float_text(self.player.pos + Vector2(0, -50), f"{WEAPONS[weapon_id].name} Mastery +1", C_ACCENT, life=1.2)
        self.progress_dirty = True

    def change_shop_page(self, delta: int):
        self.shop_page = max(0, self.shop_page + delta)

    def shop_cost(self, item: ShopItemDef) -> int:
        lvl = int(self.save.shop_levels.get(item.id, 0))
        if item.kind in ("weapon", "map"):
            return item.base_cost
        cost = item.base_cost * (item.cost_mult ** lvl)
        return int(round(cost))

    def is_maxed(self, item: ShopItemDef) -> bool:
        if item.kind == "weapon":
            wid = item.weapon_id
            return bool(self.save.weapon_unlocks.get(wid, False))
        if item.kind == "map":
            return bool(self.save.map_unlocks.get(item.weapon_id, False))
        lvl = int(self.save.shop_levels.get(item.id, 0))
        return lvl >= item.max_level

    def can_buy(self, item: ShopItemDef) -> bool:
        if self.is_maxed(item):
            return False
        return self.save.coins >= self.shop_cost(item)

    def buy_item(self, item: ShopItemDef):
        if not self.can_buy(item):
            return
        cost = self.shop_cost(item)
        self.anticheat.note_save()
        self.save.coins -= cost

        if item.kind == "weapon":
            wid = item.weapon_id
            # Ensure key exists even if weapon list changed
            if wid not in self.save.weapon_unlocks:
                self.save.weapon_unlocks[wid] = False
            self.save.weapon_unlocks[wid] = True
            # Buying a tank equips it - otherwise the purchase looks like it did nothing.
            self.save.selected_weapon = wid
        elif item.kind == "map":
            self.save.map_unlocks[item.weapon_id] = True
        else:
            self.save.shop_levels[item.id] = int(self.save.shop_levels.get(item.id, 0)) + 1

        # Re-sync after purchases in case an update added weapons
        self.save.ensure_weapons(list(WEAPONS.keys()))
        self.save.save()
        self.audio_play("buy")

    def toggle_setting(self, key: str):
        self.save.settings[key] = not bool(self.save.settings.get(key, True))
        self.save.save()
        if key == "audio":
            self.audio_enabled = bool(self.save.settings.get("audio", True))
        self.audio_play("buy")

    def reset_settings(self):
        self.save.settings["audio"] = True
        self.save.settings["shake"] = True
        self.save.settings["damage_numbers"] = True
        self.audio_enabled = AUDIO_ENABLED_DEFAULT and bool(self.save.settings.get("audio", True))
        self.save.save()
        self.audio_play("buy")

    def reset_cosmetics(self):
        self.anticheat.note_save()
        self.save.cosmetics_equipped = dict(DEFAULT_COSMETICS)
        for cid in DEFAULT_COSMETICS.values():
            self.save.cosmetics_unlocked[cid] = True
        self.save.save()
        self.audio_play("buy")

    # ---------------- Weapons screen ----------------

    def open_weapons_screen(self):
        # Ensure weapons list is always synced before showing (future updates safety)
        if self.save.ensure_weapons(list(WEAPONS.keys())):
            self.save.save()
        if self.save.ensure_mastery(list(WEAPONS.keys())):
            self.save.save()
        self.weapon_page = 0
        self.weapon_notice_text = ""
        self.weapon_notice_timer = 0.0
        self.weapons_view = "weapons"
        self.mastery_error_logged = False
        self.set_state("weapons")

    def change_weapon_page(self, delta: int):
        self.weapon_page = max(0, self.weapon_page + delta)

    # ---------------- Meta application ----------------

    def award_coins_if_needed(self):
        if self.coins_awarded_this_gameover:
            return
        waves_cleared = max(0, self.wave - 1)
        coins_earned = (self.player.score // COINS_SCORE_DIV) + (waves_cleared * COINS_PER_WAVE) + int(self.run_bonus_coins)
        coins_earned = max(0, int(coins_earned))
        self.last_run_coins_earned = coins_earned
        self.anticheat.note_save()
        self.save.coins += coins_earned
        self.save.save()
        self.coins_awarded_this_gameover = True

    def record_leaderboard_if_needed(self):
        if self.leaderboard_recorded:
            return
        self.new_best = self.player.score > self.best_score_at_start
        self.save.add_leaderboard_entry(
            score=self.player.score,
            time_s=int(self.survival_time),
            wave=self.wave,
            level=self.player.level,
        )
        self.update_challenges("runs", 1)
        self.save.save()
        self.leaderboard_recorded = True

    # ---------------- Events ----------------
