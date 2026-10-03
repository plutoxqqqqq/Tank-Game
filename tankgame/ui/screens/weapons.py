"""Weapons + mastery screens."""
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



class WeaponsScreenMixin:

    def draw_weapons(self, events):
        self.screen.fill(C_BG)
        cx = WIDTH // 2

        # countdown any hint toast
        self.weapon_notice_timer = max(0.0, self.weapon_notice_timer - (1 / 60))

        draw_text(self.screen, self.font_shop_title, "WEAPONS", (cx, 62), C_TEXT, center=True)
        subtitle = "Pick an unlocked troop (buy more in Shop → WEAPONS)." if self.weapons_view == "weapons" else "Mastery tracks each weapon's usage and progression over time."
        draw_text(self.screen, self.font_ui, subtitle,
                  (cx, 94), C_TEXT_DIM, center=True, shadow=False)

        mouse_pos = pygame.mouse.get_pos()
        mouse_down = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)

        for tab in self.weapon_tabs:
            tab.update(mouse_pos, mouse_down)
            tab.draw(self.screen, self.font_shop_item, active=(tab.tab_id == self.weapons_view))

        box = pygame.Rect(70, 160, WIDTH - 140, HEIGHT - 255)
        pygame.draw.rect(self.screen, (*C_PANEL, 235), box, border_radius=12)
        pygame.draw.rect(self.screen, (*C_WALL_EDGE, 220), box, 1, border_radius=12)

        if self.weapons_view == "mastery":
            try:
                total_pages = self.draw_weapon_mastery(box, mouse_pos, mouse_down, events)
            except Exception:
                if not self.mastery_error_logged:
                    print("Mastery tab error:")
                    traceback.print_exc()
                    self.mastery_error_logged = True
                total_pages = 1
                draw_text(self.screen, self.font_med, "Mastery data unavailable.", (cx, box.centery), C_TEXT_DIM, center=True, shadow=False)
        else:
            cols = 3
            rows = 3  # ✅ force 3 rows => 9 cards per page

            gap_x = 10
            gap_y = 12
            pad = 14

            # Compute card sizes so 3x3 fits perfectly in the box
            usable_w = box.w - pad * 2
            usable_h = box.h - pad * 2

            card_w = (usable_w - gap_x * (cols - 1)) // cols
            card_h = (usable_h - gap_y * (rows - 1)) // rows

            cards_per_page = cols * rows

            weapon_ids = list(WEAPONS.keys())  # insertion order; new weapons auto included
            total_pages = max(1, math.ceil(len(weapon_ids) / cards_per_page))
            self.weapon_page = int(clamp(self.weapon_page, 0, total_pages - 1))

            start = self.weapon_page * cards_per_page
            end = start + cards_per_page
            page_ids = weapon_ids[start:end]

            # enable/disable buttons
            self.weapon_prev_btn.enabled = self.weapon_page > 0
            self.weapon_next_btn.enabled = (self.weapon_page + 1) < total_pages

            start_x = box.x + pad
            start_y = box.y + pad

            for i, wid in enumerate(page_ids):
                c = i % cols
                r = i // cols
                rect = pygame.Rect(
                    start_x + c * (card_w + gap_x),
                    start_y + r * (card_h + gap_y),
                    card_w,
                    card_h
                )

                wdef = WEAPONS[wid]
                unlocked = bool(self.save.weapon_unlocks.get(wid, False))
                equipped = (self.save.selected_weapon == wid) and unlocked

                hover = rect.collidepoint(mouse_pos)
                if hover and mouse_down:
                    if unlocked:
                        self.save.selected_weapon = wid
                        self.save.save()
                        self.audio_play("buy")
                    else:
                        self.weapon_notice_text = "LOCKED — buy it in SHOP → WEAPONS"
                        self.weapon_notice_timer = 1.2
                        self.audio_play("hit")

                bg = (*C_PANEL_2, 245) if unlocked else (*C_PANEL_2, 190)
                edge = C_ACCENT if hover else C_WALL_EDGE
                pygame.draw.rect(self.screen, bg, rect, border_radius=14)
                pygame.draw.rect(self.screen, edge, rect, 2, border_radius=14)
                accent = C_OK if equipped else (C_ACCENT if unlocked else (70, 76, 100))
                pygame.draw.rect(self.screen, accent, pygame.Rect(rect.x, rect.y + 12, 6, rect.h - 24), border_radius=3)

                title_col = C_TEXT if unlocked else C_TEXT_DIM
                draw_text(self.screen, self.font_shop_item, wdef.name, (rect.x + 18, rect.y + 10), title_col, shadow=False)
                draw_text(self.screen, self.font_shop_desc, wdef.desc, (rect.x + 18, rect.y + 36), C_TEXT_DIM, shadow=False)

                trait = trait_of(wid)
                if trait.name:
                    trait_txt = clamp_text(self.font_tiny, f"{trait.name}: {trait.desc}", rect.w - 36)
                    draw_text(self.screen, self.font_tiny, trait_txt, (rect.x + 18, rect.y + 58),
                              C_ACCENT_2 if unlocked else C_TEXT_DIM, shadow=False)

                extra = ""
                if wdef.splash_radius > 0:
                    extra += "  •  SPLASH"
                if wdef.chain > 0:
                    extra += "  •  CHAIN"
                if getattr(wdef, "base_pierce", 0) > 0:
                    extra += f"  •  PIERCE+{wdef.base_pierce}"

                shots = wdef.radial if wdef.radial > 0 else max(1, wdef.bullets_per_shot)
                dps = wdef.base_damage * shots / max(0.01, wdef.fire_cd)
                stats = f"DMG {wdef.base_damage}  •  CD {wdef.fire_cd:.2f}s  •  ~{dps:.0f} DPS{extra}"
                draw_text(self.screen, self.font_shop_small, clamp_text(self.font_shop_small, stats, rect.w - 28),
                          (rect.x + 18, rect.y + 78), C_ACCENT if unlocked else C_TEXT_DIM, shadow=False)

                badge = pygame.Rect(rect.right - 110, rect.y + 10, 96, 28)
                if equipped:
                    pygame.draw.rect(self.screen, (*C_OK, 230), badge, border_radius=10)
                    pygame.draw.rect(self.screen, C_WALL_EDGE, badge, 2, border_radius=10)
                    rect_centered_text(self.screen, self.font_shop_small, "EQUIPPED", badge, (10, 20, 20), shadow=False)
                elif not unlocked:
                    pygame.draw.rect(self.screen, (*C_TEXT_DIM, 180), badge, border_radius=10)
                    pygame.draw.rect(self.screen, C_WALL_EDGE, badge, 2, border_radius=10)
                    rect_centered_text(self.screen, self.font_shop_small, "LOCKED", badge, (25, 25, 32), shadow=False)

        # Back + pagination buttons
        self.weapon_back_btn.update(1 / 60, mouse_pos, mouse_down, events)
        self.weapon_back_btn.draw(self.screen, self.font_med)

        self.weapon_prev_btn.update(1 / 60, mouse_pos, mouse_down, events)
        self.weapon_next_btn.update(1 / 60, mouse_pos, mouse_down, events)
        self.weapon_prev_btn.draw(self.screen, self.font_med)
        self.weapon_next_btn.draw(self.screen, self.font_med)

        page_txt = f"Page {self.weapon_page + 1}/{total_pages}"
        mid_x = (self.weapon_prev_btn.rect.centerx + self.weapon_next_btn.rect.centerx) // 2
        below_y = self.weapon_prev_btn.rect.bottom + 10
        draw_text(self.screen, self.font_tiny, page_txt, (mid_x, below_y), C_TEXT_DIM, center=True, shadow=False)

        if self.weapon_notice_timer > 0 and self.weapon_notice_text:
            draw_text(self.screen, self.font_small, self.weapon_notice_text, (cx, HEIGHT - 118), C_WARN, center=True, shadow=True)

    def draw_weapon_mastery(self, box: pygame.Rect, mouse_pos, mouse_down, events) -> int:
        cols = 2
        rows = 3
        gap_x = 12
        gap_y = 14
        pad = 16

        usable_w = box.w - pad * 2
        usable_h = box.h - pad * 2
        card_w = (usable_w - gap_x * (cols - 1)) // cols
        card_h = (usable_h - gap_y * (rows - 1)) // rows

        cards_per_page = cols * rows
        weapon_ids = list(WEAPONS.keys())
        total_pages = max(1, math.ceil(len(weapon_ids) / cards_per_page))
        self.weapon_page = int(clamp(self.weapon_page, 0, total_pages - 1))

        start = self.weapon_page * cards_per_page
        end = start + cards_per_page
        page_ids = weapon_ids[start:end]

        self.weapon_prev_btn.enabled = self.weapon_page > 0
        self.weapon_next_btn.enabled = (self.weapon_page + 1) < total_pages

        start_x = box.x + pad
        start_y = box.y + pad

        for i, wid in enumerate(page_ids):
            c = i % cols
            r = i // cols
            rect = pygame.Rect(
                start_x + c * (card_w + gap_x),
                start_y + r * (card_h + gap_y),
                card_w,
                card_h
            )

            stats, changed = self.save.ensure_mastery_entry(wid)
            if changed:
                self.save.save()
            level = int(stats.get("level", 0))
            level_kills = int(stats.get("level_kills", 0))
            level_wins = int(stats.get("level_wins", 0))
            total_kills = int(stats.get("total_kills", stats.get("kills", 0)))
            total_wins = int(stats.get("total_wins", stats.get("games", 0)))
            req_level = min(level + 1, MAX_MASTERY_LEVEL)
            req_kills = int(stats.get("req_kills", mastery_requirements(req_level)[0]))
            req_wins = int(stats.get("req_wins", mastery_requirements(req_level)[1]))

            unlocked = bool(self.save.weapon_unlocks.get(wid, False))
            pygame.draw.rect(self.screen, (*C_PANEL_2, 245) if unlocked else (*C_PANEL, 225), rect, border_radius=14)
            pygame.draw.rect(self.screen, C_WALL_EDGE if unlocked else (44, 48, 66), rect, 2, border_radius=14)

            wdef = WEAPONS[wid]
            accent = C_ACCENT if unlocked else (110, 118, 140)
            pygame.draw.rect(self.screen, accent, pygame.Rect(rect.x, rect.y + 12, 6, rect.h - 24), border_radius=3)
            pad_x = rect.x + 18
            inner_w = rect.w - 36

            mastery_label = "MAX" if level >= MAX_MASTERY_LEVEL else f"Lv. {level}/{MAX_MASTERY_LEVEL}"
            mastery_w = self.font_shop_small.size(mastery_label)[0]
            weapon_name = clamp_text(self.font_shop_item, wdef.name, max(60, inner_w - mastery_w - 16))
            draw_text(self.screen, self.font_shop_item, weapon_name, (pad_x, rect.y + 10),
                      C_TEXT if unlocked else C_TEXT_DIM, shadow=False)
            draw_text_right(self.screen, self.font_shop_small, mastery_label, (rect.right - 16, rect.y + 15), accent, shadow=False)

            col_gap = 14
            col_w = (inner_w - col_gap) // 2
            stat_y = rect.y + 42
            draw_text(self.screen, self.font_tiny, f"Kills {min(level_kills, req_kills)} / {req_kills}",
                      (pad_x, stat_y), C_TEXT_DIM, shadow=False)
            draw_text(self.screen, self.font_tiny, f"Runs {min(level_wins, req_wins)} / {req_wins}",
                      (pad_x + col_w + col_gap, stat_y), C_TEXT_DIM, shadow=False)

            bar_y = stat_y + 20
            bar_h = 10
            if level >= MAX_MASTERY_LEVEL:
                pygame.draw.rect(self.screen, (10, 10, 12), pygame.Rect(pad_x, bar_y, inner_w, bar_h), border_radius=5)
                pygame.draw.rect(self.screen, C_OK, pygame.Rect(pad_x, bar_y, inner_w, bar_h), border_radius=5)
            else:
                bars = (
                    (clamp(level_kills / max(1, req_kills), 0, 1), C_ACCENT),
                    (clamp(level_wins / max(1, req_wins), 0, 1), C_ACCENT_2),
                )
                for i, (frac, col) in enumerate(bars):
                    bx = pad_x + i * (col_w + col_gap)
                    pygame.draw.rect(self.screen, (10, 10, 12), pygame.Rect(bx, bar_y, col_w, bar_h), border_radius=5)
                    if frac > 0:
                        pygame.draw.rect(self.screen, col, pygame.Rect(bx, bar_y, max(3, int(col_w * frac)), bar_h), border_radius=5)

            if unlocked:
                footer = f"Total kills {total_kills}   •   Runs finished {total_wins}"
                draw_text(self.screen, self.font_tiny, clamp_text(self.font_tiny, footer, inner_w),
                          (pad_x, bar_y + 20), C_TEXT_DIM, shadow=False)
            else:
                draw_text(self.screen, self.font_tiny, "Locked - unlock it in Shop → WEAPONS",
                          (pad_x, bar_y + 20), C_WARN, shadow=False)

        return total_pages
