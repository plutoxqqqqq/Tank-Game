"""JSON save file: settings, unlocks, mastery, challenges and the leaderboard."""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Dict, List, Optional

from tankgame.config import *
from tankgame.util import *
from tankgame.data.weapons import WEAPONS
from tankgame.data.maps import MAPS
from tankgame.data.shop import CosmeticDef, DEFAULT_COSMETICS
from tankgame.data.mastery import MAX_MASTERY_LEVEL, mastery_requirements


class SaveManager:
    def __init__(self, path: str):
        self.path = path
        self.coins: int = 0
        self.shop_levels: Dict[str, int] = {}
        self.weapon_unlocks: Dict[str, bool] = {}
        self.map_unlocks: Dict[str, bool] = {}
        self.minigame_clears: Dict[str, int] = {}
        self.minigame_best: Dict[str, float] = {}
        self.selected_weapon: str = "pistol"
        self.cosmetic_outline_alt: bool = False
        self.bundles_purchased: Dict[str, bool] = {}
        self.cosmetics_unlocked: Dict[str, bool] = {}
        self.cosmetics_equipped: Dict[str, str] = {}
        self.daily_challenges: Dict[str, object] = {}
        self.weekly_challenges: Dict[str, object] = {}
        self.weapon_mastery: Dict[str, Dict[str, int]] = {}
        self.settings: Dict[str, bool] = {"audio": True, "shake": True, "damage_numbers": True, "fullscreen": True}
        self.leaderboard: List[Dict[str, int]] = []
        self.load()

    def defaults(self):
        self.coins = 0
        self.shop_levels = {
            "meta_damage": 0,
            "meta_move": 0,
            "meta_hp": 0,
            "meta_xp": 0,
            "meta_dash": 0,
            "meta_armor": 0,
            "meta_bulletspeed": 0,
        }
        # NOTE: weapon ids are synced against WEAPONS later (future-proof)
        self.weapon_unlocks = {"pistol": True}
        self.map_unlocks = {MAP_DEFAULT_ID: True}
        self.minigame_clears = {}
        self.minigame_best = {}
        self.selected_weapon = "pistol"
        self.cosmetic_outline_alt = False
        self.bundles_purchased = {}
        self.cosmetics_unlocked = {}
        self.cosmetics_equipped = {}
        self.daily_challenges = {}
        self.weekly_challenges = {}
        self.weapon_mastery = {}
        self.settings = {"audio": True, "shake": True, "damage_numbers": True, "fullscreen": True}
        self.leaderboard = []

    def ensure_weapons(self, weapon_ids: List[str]) -> bool:
        """Future-proof: ensure save file contains keys for every weapon in WEAPONS."""
        changed = False
        if "pistol" not in self.weapon_unlocks:
            self.weapon_unlocks["pistol"] = True
            changed = True

        for wid in weapon_ids:
            if wid not in self.weapon_unlocks:
                self.weapon_unlocks[wid] = (wid == "pistol")
                changed = True

        # Retire tanks that no longer exist (the roster evolves), and re-point a stale selection.
        for wid in list(self.weapon_unlocks.keys()):
            if wid not in weapon_ids:
                del self.weapon_unlocks[wid]
                changed = True
        if self.selected_weapon not in weapon_ids:
            self.selected_weapon = "pistol"
            changed = True

        # If selected weapon isn't unlocked, fallback.
        if not self.weapon_unlocks.get(self.selected_weapon, False):
            self.selected_weapon = "pistol"
            changed = True

        return changed

    def ensure_maps(self, map_ids: List[str]) -> bool:
        """Future-proof: every MAPS entry gets a slot, and the classic map is always owned."""
        changed = False
        if MAP_DEFAULT_ID not in self.map_unlocks:
            self.map_unlocks[MAP_DEFAULT_ID] = True
            changed = True
        for mid in map_ids:
            if mid not in self.map_unlocks:
                self.map_unlocks[mid] = (mid == MAP_DEFAULT_ID)
                changed = True
        return changed

    def ensure_cosmetics(self, cosmetics: List["CosmeticDef"]) -> bool:
        changed = False
        if not self.cosmetics_equipped:
            self.cosmetics_equipped = dict(DEFAULT_COSMETICS)
            changed = True
        for category, cid in DEFAULT_COSMETICS.items():
            if category not in self.cosmetics_equipped:
                self.cosmetics_equipped[category] = cid
                changed = True

        for cosmetic in cosmetics:
            if cosmetic.id not in self.cosmetics_unlocked:
                self.cosmetics_unlocked[cosmetic.id] = bool(cosmetic.default)
                changed = True

        for category, default_id in DEFAULT_COSMETICS.items():
            equipped_id = self.cosmetics_equipped.get(category, default_id)
            if equipped_id not in self.cosmetics_unlocked:
                self.cosmetics_equipped[category] = default_id
                equipped_id = default_id
                changed = True
            if not self.cosmetics_unlocked.get(equipped_id, False):
                self.cosmetics_unlocked[equipped_id] = True
                changed = True

        if self.cosmetic_outline_alt:
            if "outline_neon" in self.cosmetics_unlocked:
                if not self.cosmetics_unlocked.get("outline_neon"):
                    self.cosmetics_unlocked["outline_neon"] = True
                    changed = True
                self.cosmetics_equipped["outline"] = "outline_neon"
                changed = True

        return changed

    def ensure_mastery(self, weapon_ids: List[str]) -> bool:
        changed = False
        for wid in weapon_ids:
            _, entry_changed = self.ensure_mastery_entry(wid)
            if entry_changed:
                changed = True
        return changed

    def ensure_mastery_entry(self, weapon_id: str) -> Tuple[Dict[str, int], bool]:
        changed = False
        if weapon_id not in self.weapon_mastery or not isinstance(self.weapon_mastery.get(weapon_id), dict):
            self.weapon_mastery[weapon_id] = {}
            changed = True
        stats = self.weapon_mastery[weapon_id]
        if "level" not in stats:
            stats["level"] = 0
            changed = True
        if "hits" not in stats:
            stats["hits"] = 0
            changed = True
        if "total_kills" not in stats:
            stats["total_kills"] = int(stats.get("kills", 0))
            changed = True
        if "total_wins" not in stats:
            stats["total_wins"] = int(stats.get("games", 0))
            changed = True
        if "level_kills" not in stats:
            stats["level_kills"] = 0
            changed = True
        if "level_wins" not in stats:
            stats["level_wins"] = 0
            changed = True
        req_level = min(int(stats.get("level", 0)) + 1, MAX_MASTERY_LEVEL)
        req_kills, req_wins = mastery_requirements(req_level)
        if "req_kills" not in stats:
            stats["req_kills"] = req_kills
            changed = True
        if "req_wins" not in stats:
            stats["req_wins"] = req_wins
            changed = True
        return stats, changed

    def load(self):
        self.defaults()
        try:
            if not os.path.exists(self.path):
                return
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.coins = int(data.get("coins", 0))
            self.shop_levels = dict(data.get("shop_levels", self.shop_levels))
            self.weapon_unlocks = dict(data.get("weapon_unlocks", self.weapon_unlocks))
            self.map_unlocks = dict(data.get("map_unlocks", self.map_unlocks))
            self.minigame_clears = dict(data.get("minigame_clears", {}))
            self.minigame_best = {k: float(v) for k, v in dict(data.get("minigame_best", {})).items()}
            self.selected_weapon = str(data.get("selected_weapon", self.selected_weapon))
            self.cosmetic_outline_alt = bool(data.get("cosmetic_outline_alt", False))
            self.bundles_purchased = dict(data.get("bundles_purchased", {}))
            self.cosmetics_unlocked = dict(data.get("cosmetics_unlocked", {}))
            self.cosmetics_equipped = dict(data.get("cosmetics_equipped", {}))
            self.daily_challenges = dict(data.get("daily_challenges", {}))
            self.weekly_challenges = dict(data.get("weekly_challenges", {}))
            self.weapon_mastery = dict(data.get("weapon_mastery", {}))
            self.settings = dict(data.get("settings", self.settings))
            self.leaderboard = list(data.get("leaderboard", []))

            for k in ["meta_damage", "meta_move", "meta_hp", "meta_xp", "meta_dash", "meta_armor", "meta_bulletspeed"]:
                if k not in self.shop_levels:
                    self.shop_levels[k] = 0

            # Legacy saves stored the damage-resistance upgrade under "armor" while the code read
            # "meta_armor", so it silently did nothing. Migrate the progress instead of dropping it.
            legacy_armor = safe_int(self.shop_levels.pop("armor", 0))
            if legacy_armor > 0:
                self.shop_levels["meta_armor"] = max(safe_int(self.shop_levels.get("meta_armor", 0)), legacy_armor)

            if "audio" not in self.settings:
                self.settings["audio"] = True
            if "shake" not in self.settings:
                self.settings["shake"] = True
            if "damage_numbers" not in self.settings:
                self.settings["damage_numbers"] = True
            if "fullscreen" not in self.settings:
                self.settings["fullscreen"] = True

            if "pistol" not in self.weapon_unlocks:
                self.weapon_unlocks["pistol"] = True

            if not self.weapon_unlocks.get(self.selected_weapon, False):
                self.selected_weapon = "pistol"

            if not isinstance(self.bundles_purchased, dict):
                self.bundles_purchased = {}
            if not isinstance(self.map_unlocks, dict):
                self.map_unlocks = {MAP_DEFAULT_ID: True}
            self.map_unlocks[MAP_DEFAULT_ID] = True
            if not isinstance(self.minigame_clears, dict):
                self.minigame_clears = {}
            if not isinstance(self.minigame_best, dict):
                self.minigame_best = {}
            if not isinstance(self.cosmetics_unlocked, dict):
                self.cosmetics_unlocked = {}
            if not isinstance(self.cosmetics_equipped, dict):
                self.cosmetics_equipped = {}
            if not isinstance(self.daily_challenges, dict):
                self.daily_challenges = {}
            if not isinstance(self.weekly_challenges, dict):
                self.weekly_challenges = {}
            if not isinstance(self.weapon_mastery, dict):
                self.weapon_mastery = {}

            self.leaderboard = [
                e for e in self.leaderboard
                if isinstance(e, dict)
                and "score" in e
                and "time" in e
                and "wave" in e
                and "level" in e
            ]
            self.leaderboard.sort(key=lambda e: (e["score"], e["wave"], e["time"]), reverse=True)
            self.leaderboard = self.leaderboard[:LEADERBOARD_LIMIT]
        except Exception:
            self.defaults()

    def save(self):
        try:
            data = {
                "coins": int(self.coins),
                "shop_levels": self.shop_levels,
                "weapon_unlocks": self.weapon_unlocks,
                "map_unlocks": self.map_unlocks,
                "minigame_clears": self.minigame_clears,
                "minigame_best": self.minigame_best,
                "selected_weapon": self.selected_weapon,
                "cosmetic_outline_alt": bool(self.cosmetic_outline_alt),
                "bundles_purchased": self.bundles_purchased,
                "cosmetics_unlocked": self.cosmetics_unlocked,
                "cosmetics_equipped": self.cosmetics_equipped,
                "daily_challenges": self.daily_challenges,
                "weekly_challenges": self.weekly_challenges,
                "weapon_mastery": self.weapon_mastery,
                "settings": self.settings,
                "leaderboard": self.leaderboard,
            }
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def best_score(self) -> int:
        return max((safe_int(e.get("score", 0)) for e in self.leaderboard), default=0)

    def add_leaderboard_entry(self, score: int, time_s: int, wave: int, level: int):
        entry = {
            "score": int(score),
            "time": int(time_s),
            "wave": int(wave),
            "level": int(level),
        }
        self.leaderboard.append(entry)
        self.leaderboard = [
            e for e in self.leaderboard
            if isinstance(e, dict)
            and "score" in e
            and "time" in e
            and "wave" in e
            and "level" in e
        ]
        self.leaderboard.sort(key=lambda e: (e["score"], e["wave"], e["time"]), reverse=True)
        self.leaderboard = self.leaderboard[:LEADERBOARD_LIMIT]
