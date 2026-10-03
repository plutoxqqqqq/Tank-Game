"""Pause screen + build/stats summaries."""
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



class PausedScreenMixin:

    def draw_paused(self, events):
        self.draw_background()
        self.draw_obstacles()
        self.draw_entities()
        self.draw_minigame_view()
        self.draw_hud()
        self.draw_overlay_dim(205)
        cx = WIDTH // 2
        draw_text(self.screen, self.font_big, "PAUSED", (cx, 128), C_TEXT, center=True)
        draw_text(self.screen, self.font_ui,
                  f"Wave {self.wave}  •  Score {self.player.score}  •  {int(self.survival_time)}s survived",
                  (cx, 166), C_TEXT_DIM, center=True, shadow=False)
        trait = self.player.trait()
        if trait.name:
            draw_text(self.screen, self.font_small,
                      f"{self.player.weapon.name} — {trait.name}: {trait.desc}",
                      (cx, 196), C_ACCENT_2, center=True, shadow=False)

        # ---------------- Build summary + live stats, either side of the buttons ----------------
        panel_y, panel_h = 232, 214
        self.draw_pause_build_summary(pygame.Rect(58, panel_y, 302, panel_h))
        self.draw_pause_stats(pygame.Rect(WIDTH - 360, panel_y, 302, panel_h))

        mouse_pos = pygame.mouse.get_pos()
        mouse_down = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)
        for b in self.pause_buttons:
            b.update(1 / 60, mouse_pos, mouse_down, events)
            b.draw(self.screen, self.font_med)

        # Free, mid-run targeting switches: drone modes for the Drone tank, and aimbot lead modes
        # for any tank that picked up the Aimbot ultra.
        picker_y = 456
        if self.player.weapon_id == "nanite_swarm":
            self.draw_mode_picker(
                "DRONE TARGET MODE", DRONE_TARGET_MODES, self.player.drone_target_mode,
                lambda m: setattr(self.player, "drone_target_mode", m),
                f"{self.player.get_drone_count()} drones", picker_y, mouse_pos, mouse_down)
            picker_y += 74
        if self.player.aimbot:
            self.draw_mode_picker(
                "AIMBOT LEAD MODE", DRONE_TARGET_MODES, self.player.aimbot_mode,
                lambda m: setattr(self.player, "aimbot_mode", m),
                "shots lead the chosen target", picker_y, mouse_pos, mouse_down)

        draw_text(self.screen, self.font_small, "ESC resumes the run", (cx, HEIGHT - 26), C_TEXT_DIM, center=True, shadow=False)

    def draw_mode_picker(self, title, modes, current, apply_mode, note, top, mouse_pos, mouse_down):
        """Generic free target-mode selector (no cost, no cooldown). Used by drones and aimbot."""
        cx = WIDTH // 2
        draw_text(self.screen, self.font_small, title, (cx, top), C_ACCENT, center=True, shadow=False)
        gap = 10
        bw = min(150, (WIDTH - 80 - gap * (len(modes) - 1)) // len(modes))
        bh = 40
        total = len(modes) * bw + (len(modes) - 1) * gap
        x0 = cx - total // 2
        hover_desc = ""
        for i, (mid, name, desc) in enumerate(modes):
            rect = pygame.Rect(x0 + i * (bw + gap), top + 24, bw, bh)
            active = current == mid
            hover = rect.collidepoint(mouse_pos)
            self.draw_panel(rect, (*C_ULTRA, 70) if active else (*C_PANEL_2, 235),
                            (*C_ULTRA, 230) if active else (*C_WALL_EDGE, 200), radius=10)
            rect_centered_text(self.screen, self.font_tiny, name.upper(), rect,
                               C_ULTRA if active else C_TEXT, shadow=False)
            if hover:
                hover_desc = desc
                if mouse_down and not active:
                    apply_mode(mid)
                    self.audio_play("buy")
        desc_now = next((d for m_id, _n, d in modes if m_id == current), "")
        draw_text(self.screen, self.font_tiny, f"{note}  •  {hover_desc or desc_now}",
                  (cx, top + 70), C_TEXT_DIM, center=True, shadow=False)

    def draw_pause_build_summary(self, box: pygame.Rect):
        """What you have actually taken this run - the one thing the old pause screen never showed."""
        self.draw_panel(box, (*C_PANEL, 232), (*C_WALL_EDGE, 215), radius=14)
        draw_text(self.screen, self.font_small, "BUILD", (box.x + 14, box.y + 10), C_ACCENT, shadow=False)

        taken = [(up_id, n) for up_id, n in self.player.upgrade_counts.items() if n > 0]
        if not taken:
            draw_text(self.screen, self.font_tiny, "No upgrades yet —", (box.x + 14, box.y + 40), C_TEXT_DIM, shadow=False)
            draw_text(self.screen, self.font_tiny, "level up to start a build.", (box.x + 14, box.y + 60), C_TEXT_DIM, shadow=False)
            return

        rows = box.h // 24 - 2
        for i, (up_id, n) in enumerate(taken[:rows]):
            up = UPGRADES_BY_ID.get(up_id)
            is_ultra = bool(up and up.ultra)
            name = up.name if up else up_id
            if is_ultra:
                name = "\u2605 " + name
            y = box.y + 40 + i * 22
            draw_text(self.screen, self.font_tiny, name, (box.x + 14, y),
                      C_ULTRA if is_ultra else C_TEXT, shadow=False)
            if n > 1:
                draw_text_right(self.screen, self.font_tiny, f"x{n}", (box.right - 14, y),
                                C_ULTRA if is_ultra else C_ACCENT, shadow=False)
        if len(taken) > rows:
            draw_text(self.screen, self.font_tiny, f"+{len(taken) - rows} more", (box.x + 14, box.bottom - 24),
                      C_TEXT_DIM, shadow=False)

    def draw_pause_stats(self, box: pygame.Rect):
        """Live numbers behind the run: what the tank is doing right now, plus wave twist + buffs."""
        self.draw_panel(box, (*C_PANEL, 232), (*C_WALL_EDGE, 215), radius=14)
        draw_text(self.screen, self.font_small, "STATS", (box.x + 14, box.y + 10), C_ACCENT, shadow=False)
        who = self.player

        pierce = who.piercing + int(getattr(who.weapon, "base_pierce", 0))
        rows = [
            ("Damage", f"{fmt_amount(who.get_damage())} / shot"),
            ("Fire rate", f"{1.0 / max(0.01, who.get_fire_cooldown()):.1f} shots/s"),
            ("Crit", f"{who.get_crit_chance() * 100:.0f}%  x{who.get_crit_mult():.1f}"),
            ("Move speed", f"{who.get_move_speed():.0f}"),
            ("Pierce", str(pierce)),
        ]
        leech = who.get_lifesteal()
        if leech > 0.0:
            rows.append(("Lifesteal", f"1 HP / {int(round(1.0 / leech))} dmg"))

        for i, (label, value) in enumerate(rows):
            y = box.y + 40 + i * 22
            draw_text(self.screen, self.font_tiny, label, (box.x + 14, y), C_TEXT_DIM, shadow=False)
            draw_text_right(self.screen, self.font_tiny, value, (box.right - 14, y), C_TEXT, shadow=False)

        info_y = box.y + 40 + len(rows) * 22 + 6
        draw_text(self.screen, self.font_tiny, f"MAP: {self.current_map.name.upper()}",
                  (box.x + 14, info_y), C_TEXT_DIM, shadow=False)
        info_y += 20
        if self.wave_mutator is not None:
            mut = self.wave_mutator
            draw_text(self.screen, self.font_tiny, f"WAVE: {mut.name}", (box.x + 14, info_y), mut.color, shadow=False)
            info_y += 20
        active = [k for k, v in who.effects.items() if v > 0]
        if active:
            draw_text(self.screen, self.font_tiny, "BUFFS: " + ", ".join(k.replace("_", " ").upper() for k in active),
                      (box.x + 14, info_y), C_OK, shadow=False)
