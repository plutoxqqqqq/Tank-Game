"""The shop screen."""
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



class ShopScreenMixin:

    def draw_shop(self, events):
        self.screen.fill(C_BG)
        cx = WIDTH // 2
        draw_text(self.screen, self.font_shop_title, "SHOP", (cx, 62), C_TEXT, center=True)
        draw_text(self.screen, self.font_ui, f"Coins: {self.save.coins}", (cx, 92), C_COIN, center=True)

        mouse_pos = pygame.mouse.get_pos()
        mouse_down = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)

        for tab in self.shop_tabs:
            tab.update(mouse_pos, mouse_down)
            tab.draw(self.screen, self.font_shop_item, active=(tab.tab_id == self.shop_tab))

        box = pygame.Rect(70, 175, WIDTH - 140, HEIGHT - 270)
        if self.shop_tab != "cosmetics":
            pygame.draw.rect(self.screen, (*C_PANEL, 235), box, border_radius=12)
            pygame.draw.rect(self.screen, (*C_WALL_EDGE, 220), box, 1, border_radius=12)

        if self.shop_tab == "cosmetics":
            for tab in self.cosmetic_tabs:
                tab.update(mouse_pos, mouse_down)
                tab.draw(self.screen, self.font_shop_desc, active=(tab.tab_id == self.cosmetics_category))

            controls_top = min(self.shop_prev_btn.rect.top, self.shop_back_btn.rect.top)
            list_top = 220
            list_bottom = controls_top - 12
            cosmetic_box = pygame.Rect(70, list_top, WIDTH - 140, list_bottom - list_top)
            pygame.draw.rect(self.screen, (*C_PANEL, 235), cosmetic_box, border_radius=12)
            pygame.draw.rect(self.screen, (*C_WALL_EDGE, 220), cosmetic_box, 1, border_radius=12)

            cosmetics = [c for c in COSMETICS if c.category == self.cosmetics_category]
            row_h = 64
            gap = 8
            rows_per_page = max(1, (cosmetic_box.h - 24) // (row_h + gap))
            total_pages = max(1, math.ceil(len(cosmetics) / rows_per_page))
            self.shop_page = clamp(self.shop_page, 0, total_pages - 1)

            start = self.shop_page * rows_per_page
            end = start + rows_per_page
            page_items = cosmetics[start:end]

            has_prev = self.shop_page > 0
            has_next = (self.shop_page + 1) < total_pages
            self.shop_prev_btn.enabled = has_prev
            self.shop_next_btn.enabled = has_next

            x0 = cosmetic_box.x + 18
            y = cosmetic_box.y + 14
            row_w = cosmetic_box.w - 36

            for cosmetic in page_items:
                row = pygame.Rect(x0, y, row_w, row_h)
                y += (row_h + gap)

                pygame.draw.rect(self.screen, (*C_PANEL_2, 245), row, border_radius=12)
                pygame.draw.rect(self.screen, (*C_WALL_EDGE, 200), row, 2, border_radius=12)

                unlocked = bool(self.save.cosmetics_unlocked.get(cosmetic.id, False))
                equipped = self.save.cosmetics_equipped.get(cosmetic.category) == cosmetic.id
                status = "Owned" if unlocked else ("Bundle Exclusive" if cosmetic.bundle_only else "Locked")
                cost_txt = "--" if unlocked or cosmetic.bundle_only else f"{cosmetic.cost} coins"
                cat_txt = cosmetic.category.upper()

                swatch = pygame.Rect(row.x + 12, row.y + 16, 32, 32)
                pygame.draw.rect(self.screen, (*cosmetic.color, 255), swatch, border_radius=8)
                pygame.draw.rect(self.screen, C_WALL_EDGE, swatch, 2, border_radius=8)

                draw_text(self.screen, self.font_shop_item, f"{cosmetic.name}  •  {cat_txt}", (row.x + 56, row.y + 8), C_TEXT, shadow=False)
                draw_text(self.screen, self.font_shop_desc, cosmetic.desc, (row.x + 56, row.y + 34), C_TEXT_DIM, shadow=False)
                draw_text(self.screen, self.font_shop_small, status, (row.right - 300, row.y + 10),
                          C_OK if unlocked else C_TEXT_DIM, shadow=False)
                draw_text(self.screen, self.font_shop_small, cost_txt, (row.right - 300, row.y + 34), C_COIN, shadow=False)

                action_rect = pygame.Rect(row.right - 120, row.y + 13, 100, 38)
                if equipped:
                    pygame.draw.rect(self.screen, (*C_OK, 220), action_rect, border_radius=10)
                    pygame.draw.rect(self.screen, C_WALL_EDGE, action_rect, 2, border_radius=10)
                    rect_centered_text(self.screen, self.font_shop_small, "EQUIPPED", action_rect, (10, 20, 20), shadow=False)
                else:
                    label = "Equip" if unlocked else ("Bundle" if cosmetic.bundle_only else "Buy")
                    btn = Button(action_rect, label, callback=lambda c=cosmetic: self.equip_cosmetic(c) if self.save.cosmetics_unlocked.get(c.id, False) else self.buy_cosmetic(c))
                    btn.enabled = unlocked or (not cosmetic.bundle_only and self.save.coins >= cosmetic.cost)
                    btn.update(1 / 60, mouse_pos, mouse_down, events)
                    btn.draw(self.screen, self.font_shop_small)

            self.shop_back_btn.update(1 / 60, mouse_pos, mouse_down, events)
            self.shop_back_btn.draw(self.screen, self.font_med)

            self.shop_prev_btn.update(1 / 60, mouse_pos, mouse_down, events)
            self.shop_next_btn.update(1 / 60, mouse_pos, mouse_down, events)
            self.shop_prev_btn.draw(self.screen, self.font_med)
            self.shop_next_btn.draw(self.screen, self.font_med)

            page_txt = f"Page {self.shop_page + 1}/{total_pages}"
            mid_x = (self.shop_prev_btn.rect.centerx + self.shop_next_btn.rect.centerx) // 2
            below_y = self.shop_prev_btn.rect.bottom + 10
            draw_text(self.screen, self.font_tiny, page_txt, (mid_x, below_y), C_TEXT_DIM, center=True, shadow=False)
            return

        if self.shop_tab == "bundles":
            items = BUNDLES
            # Bundle rows are 86 tall + 12 gap - using the generic 72+12 step overflowed the panel.
            rows_per_page = self._shop_rows_per_page(box, row_h=86)
            total_pages = max(1, math.ceil(len(items) / max(1, rows_per_page)))
            self.shop_page = clamp(self.shop_page, 0, total_pages - 1)

            start = self.shop_page * rows_per_page
            end = start + rows_per_page
            page_items = items[start:end]

            has_prev = self.shop_page > 0
            has_next = (self.shop_page + 1) < total_pages
            self.shop_prev_btn.enabled = has_prev
            self.shop_next_btn.enabled = has_next

            x0 = box.x + 18
            y = box.y + 14

            row_h = 86
            gap = 12
            row_w = box.w - 36

            for bundle in page_items:
                row = pygame.Rect(x0, y, row_w, row_h)
                y += (row_h + gap)

                pygame.draw.rect(self.screen, (*C_PANEL_2, 245), row, border_radius=12)
                pygame.draw.rect(self.screen, (*C_WALL_EDGE, 200), row, 2, border_radius=12)

                weapons, meta, cosmetics = self.resolve_bundle_items(bundle)
                owned = self.bundle_is_owned(bundle)
                cost = self.bundle_price(bundle)
                includes = []
                includes += [WEAPONS[w].name for w in weapons if w in WEAPONS]
                includes += [SHOP_ITEMS_BY_ID[m].name for m in meta if m in SHOP_ITEMS_BY_ID]
                includes += [COSMETICS_BY_ID[c].name for c in cosmetics if c in COSMETICS_BY_ID]
                includes_txt = ", ".join(includes) if includes else "No bundle items available"

                draw_text(self.screen, self.font_shop_item, bundle.name, (row.x + 14, row.y + 10), C_TEXT, shadow=False)
                draw_text(self.screen, self.font_shop_desc, bundle.desc, (row.x + 14, row.y + 38), C_TEXT_DIM, shadow=False)
                draw_text(self.screen, self.font_shop_small, includes_txt, (row.x + 14, row.y + 62), C_TEXT_DIM, shadow=False)

                status_txt = "OWNED" if owned else f"{int(bundle.discount * 100)}% off"
                draw_text(self.screen, self.font_shop_small, status_txt, (row.right - 310, row.y + 16),
                          C_OK if owned else C_TEXT_DIM, shadow=False)
                cost_txt = "OWNED" if owned else f"{cost} coins"
                draw_text(self.screen, self.font_shop_small, cost_txt, (row.right - 310, row.y + 44), C_COIN, shadow=False)

                buy_rect = pygame.Rect(row.right - 110, row.y + 22, 92, 40)
                btn = Button(buy_rect, "Buy", callback=lambda b=bundle: self.buy_bundle(b))
                btn.enabled = (not owned) and (self.save.coins >= cost) and cost > 0
                btn.update(1 / 60, mouse_pos, mouse_down, events)
                btn.draw(self.screen, self.font_shop_small)

            self.shop_back_btn.update(1 / 60, mouse_pos, mouse_down, events)
            self.shop_back_btn.draw(self.screen, self.font_med)

            self.shop_prev_btn.update(1 / 60, mouse_pos, mouse_down, events)
            self.shop_next_btn.update(1 / 60, mouse_pos, mouse_down, events)
            self.shop_prev_btn.draw(self.screen, self.font_med)
            self.shop_next_btn.draw(self.screen, self.font_med)

            page_txt = f"Page {self.shop_page + 1}/{total_pages}"
            mid_x = (self.shop_prev_btn.rect.centerx + self.shop_next_btn.rect.centerx) // 2
            below_y = self.shop_prev_btn.rect.bottom + 10
            draw_text(self.screen, self.font_tiny, page_txt, (mid_x, below_y), C_TEXT_DIM, center=True, shadow=False)
            return

        items = self._shop_items_for_tab()

        rows_per_page = self._shop_rows_per_page(box)
        total_pages = max(1, math.ceil(len(items) / max(1, rows_per_page)))
        self.shop_page = clamp(self.shop_page, 0, total_pages - 1)

        start = self.shop_page * rows_per_page
        end = start + rows_per_page
        page_items = items[start:end]

        has_prev = self.shop_page > 0
        has_next = (self.shop_page + 1) < total_pages
        self.shop_prev_btn.enabled = has_prev
        self.shop_next_btn.enabled = has_next

        x0 = box.x + 18
        y = box.y + 14

        row_h = 72
        gap = 12
        row_w = box.w - 36

        for item in page_items:
            row = pygame.Rect(x0, y, row_w, row_h)
            y += (row_h + gap)

            pygame.draw.rect(self.screen, (*C_PANEL_2, 245), row, border_radius=12)
            pygame.draw.rect(self.screen, (*C_WALL_EDGE, 200), row, 2, border_radius=12)

            maxed = self.is_maxed(item)
            cost = self.shop_cost(item)

            if item.kind == "weapon":
                unlocked = bool(self.save.weapon_unlocks.get(item.weapon_id, False))
                lvl_txt = "Unlocked" if unlocked else "Locked"
                lvl_col = C_OK if unlocked else C_TEXT_DIM
                cost_txt = "MAX" if maxed else f"{cost} coins"
            elif item.kind == "map":
                owned = bool(self.save.map_unlocks.get(item.weapon_id, False))
                lvl_txt = "Owned" if owned else "Locked"
                lvl_col = C_OK if owned else C_TEXT_DIM
                cost_txt = "MAX" if maxed else f"{cost} coins"
            else:
                lvl = int(self.save.shop_levels.get(item.id, 0))
                lvl_txt = f"Level {lvl}/{item.max_level}"
                lvl_col = C_TEXT_DIM
                cost_txt = "MAX" if maxed else f"{cost} coins"

            draw_text(self.screen, self.font_shop_item, item.name, (row.x + 14, row.y + 10), C_TEXT, shadow=False)
            draw_text(self.screen, self.font_shop_desc, item.desc, (row.x + 14, row.y + 38), C_TEXT_DIM, shadow=False)
            draw_text(self.screen, self.font_shop_small, lvl_txt, (row.right - 310, row.y + 14), lvl_col, shadow=False)
            draw_text(self.screen, self.font_shop_small, cost_txt, (row.right - 310, row.y + 38), C_COIN, shadow=False)

            buy_rect = pygame.Rect(row.right - 110, row.y + 16, 92, 40)
            label = "Buy" if not maxed else ("Owned" if item.kind in ("weapon", "map") else "Max")
            btn = Button(buy_rect, label, callback=lambda it=item: self.buy_item(it))
            btn.enabled = self.can_buy(item)
            btn.update(1 / 60, mouse_pos, mouse_down, events)
            btn.draw(self.screen, self.font_shop_small)

        self.shop_back_btn.update(1 / 60, mouse_pos, mouse_down, events)
        self.shop_back_btn.draw(self.screen, self.font_med)

        self.shop_prev_btn.update(1 / 60, mouse_pos, mouse_down, events)
        self.shop_next_btn.update(1 / 60, mouse_pos, mouse_down, events)
        self.shop_prev_btn.draw(self.screen, self.font_med)
        self.shop_next_btn.draw(self.screen, self.font_med)

        page_txt = f"Page {self.shop_page + 1}/{total_pages}"
        mid_x = (self.shop_prev_btn.rect.centerx + self.shop_next_btn.rect.centerx) // 2
        below_y = self.shop_prev_btn.rect.bottom + 10
        draw_text(self.screen, self.font_tiny, page_txt, (mid_x, below_y), C_TEXT_DIM, center=True, shadow=False)
