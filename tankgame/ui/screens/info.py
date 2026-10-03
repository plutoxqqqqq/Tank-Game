"""Information screens: leaderboard and challenges."""
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



class InfoScreenMixin:

    def draw_leaderboard(self, events):
        self.screen.fill(C_BG)
        cx = WIDTH // 2

        draw_text(self.screen, self.font_big, "LEADERBOARD", (cx, 92), C_TEXT, center=True)
        draw_text(self.screen, self.font_ui, "Top runs by score", (cx, 128), C_TEXT_DIM, center=True, shadow=False)

        # 10 leaderboard rows at the old 50px step ran straight off the bottom of the box.
        box = pygame.Rect(140, 166, WIDTH - 280, HEIGHT - 252)
        pygame.draw.rect(self.screen, (*C_PANEL, 235), box, border_radius=12)
        pygame.draw.rect(self.screen, (*C_WALL_EDGE, 220), box, 1, border_radius=12)

        header = pygame.Rect(box.x + 10, box.y + 12, box.w - 20, 42)
        pygame.draw.rect(self.screen, (*C_PANEL_2, 240), header, border_radius=12)
        pygame.draw.rect(self.screen, (*C_WALL_EDGE, 200), header, 2, border_radius=12)

        col_rank = header.x + 16
        col_score = header.x + 110
        col_time = header.x + 300
        col_wave = header.x + 470
        col_level = header.right - 110

        header_y = header.y + 12
        draw_text(self.screen, self.font_ui, "RANK", (col_rank, header_y), C_TEXT_DIM, shadow=False)
        draw_text(self.screen, self.font_ui, "SCORE", (col_score, header_y), C_TEXT_DIM, shadow=False)
        draw_text(self.screen, self.font_ui, "TIME", (col_time, header_y), C_TEXT_DIM, shadow=False)
        draw_text(self.screen, self.font_ui, "WAVE", (col_wave, header_y), C_TEXT_DIM, shadow=False)
        draw_text(self.screen, self.font_ui, "LEVEL", (col_level, header_y), C_TEXT_DIM, shadow=False)

        entries = list(self.save.leaderboard)
        if not entries:
            draw_text(self.screen, self.font_med, "No runs yet — play a game to set a score!", (cx, box.centery), C_TEXT_DIM, center=True, shadow=False)
        else:
            row_y = header.bottom + 8
            row_gap = 2
            row_h = 28
            # Never let rows spill out of the panel, whatever the save file contains.
            max_rows = max(1, (box.bottom - 12 - row_y) // (row_h + row_gap))
            shown = entries[:max_rows]
            for idx, entry in enumerate(shown, start=1):
                row = pygame.Rect(box.x + 10, row_y, box.w - 20, row_h)
                row_color = (*C_PANEL_2, 220) if idx % 2 == 0 else (*C_PANEL_2, 180)
                if idx == 1:
                    row_color = (*C_ACCENT, 60)
                pygame.draw.rect(self.screen, row_color, row, border_radius=8)
                pygame.draw.rect(self.screen, (*C_WALL_EDGE, 150), row, 1, border_radius=8)

                badge = pygame.Rect(row.x + 8, row.y + 4, 44, row_h - 8)
                badge_color = (*C_ACCENT, 220) if idx == 1 else (*C_PANEL, 220)
                pygame.draw.rect(self.screen, badge_color, badge, border_radius=6)
                pygame.draw.rect(self.screen, (*C_WALL_EDGE, 190), badge, 2, border_radius=6)
                rect_centered_text(self.screen, self.font_tiny, f"{idx}", badge, (10, 20, 20), shadow=False)

                draw_text(self.screen, self.font_small, f"{entry['score']}", (col_score, row.y + 4), C_TEXT, shadow=False)
                draw_text(self.screen, self.font_small, f"{entry['time']}s", (col_time, row.y + 4), C_TEXT, shadow=False)
                draw_text(self.screen, self.font_small, f"{entry['wave']}", (col_wave, row.y + 4), C_TEXT, shadow=False)
                draw_text(self.screen, self.font_small, f"{entry['level']}", (col_level, row.y + 4), C_TEXT, shadow=False)
                row_y += row_h + row_gap

            if len(entries) > len(shown):
                draw_text(self.screen, self.font_small, f"+{len(entries) - len(shown)} older run(s) hidden",
                          (box.centerx, box.bottom - 26), C_TEXT_DIM, center=True, shadow=False)

        mouse_pos = pygame.mouse.get_pos()
        mouse_down = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)
        if self.leaderboard_back_btn:
            self.leaderboard_back_btn.update(1 / 60, mouse_pos, mouse_down, events)
            self.leaderboard_back_btn.draw(self.screen, self.font_med)

    def draw_challenges(self, events):
        self.screen.fill(C_BG)
        self.refresh_challenges()
        cx = WIDTH // 2

        title_y = 92
        subtitle_y = 128
        tab_y = subtitle_y + 32
        tab_gap = 18

        draw_text(self.screen, self.font_big, "CHALLENGES", (cx, title_y), C_TEXT, center=True)
        subtitle = "Daily goals reset automatically" if self.challenges_view == "daily" else "Weekly goals reset automatically"
        draw_text(self.screen, self.font_ui, subtitle, (cx, subtitle_y), C_TEXT_DIM, center=True, shadow=False)

        mouse_pos = pygame.mouse.get_pos()
        mouse_down = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)

        tab_h = self.challenge_tabs[0].rect.height if self.challenge_tabs else 0
        for tab in self.challenge_tabs:
            tab.rect.y = tab_y
            tab.update(mouse_pos, mouse_down)
            tab.draw(self.screen, self.font_shop_item, active=(tab.tab_id == self.challenges_view))

        box_y = tab_y + tab_h + tab_gap
        box_bottom = HEIGHT - 110
        box = pygame.Rect(120, box_y, WIDTH - 240, box_bottom - box_y)
        pygame.draw.rect(self.screen, (*C_PANEL, 235), box, border_radius=12)
        pygame.draw.rect(self.screen, (*C_WALL_EDGE, 220), box, 1, border_radius=12)

        list_rect = pygame.Rect(box.x + 16, box.y + 32, box.w - 32, box.h - 48)
        reset_label = f"Resets in {self.time_until_reset(self.challenges_view)}"
        header = "DAILY" if self.challenges_view == "daily" else "WEEKLY"
        draw_text(self.screen, self.font_shop_item, f"{header}  •  {reset_label}", (list_rect.x, box.y + 10), C_TEXT, shadow=False)

        def draw_list(items, rect):
            if not items:
                draw_text(self.screen, self.font_small, "No challenges available.", (rect.centerx, rect.centery), C_TEXT_DIM, center=True, shadow=False)
                return
            row_h = 64
            gap = 10
            y = rect.y + 8
            for item in items:
                row = pygame.Rect(rect.x, y, rect.w, row_h)
                y += row_h + gap
                pygame.draw.rect(self.screen, (*C_PANEL_2, 245), row, border_radius=12)
                pygame.draw.rect(self.screen, (*C_WALL_EDGE, 200), row, 2, border_radius=12)

                progress = int(item.get("progress", 0))
                target = int(item.get("target", 1))
                claimed = bool(item.get("claimed", False))

                draw_text(self.screen, self.font_shop_item, item.get("name", "Challenge"), (row.x + 12, row.y + 8), C_TEXT, shadow=False)
                draw_text(self.screen, self.font_shop_desc, item.get("desc", ""), (row.x + 12, row.y + 34), C_TEXT_DIM, shadow=False)

                progress_txt = f"{min(progress, target)}/{target}"
                reward_txt = f"{int(item.get('reward', 0))} coins"
                progress_w = self.font_shop_small.size(progress_txt)[0]
                reward_w = self.font_shop_small.size(reward_txt)[0]
                info_gap = 10
                status_x = row.right - 120
                group_w = progress_w + info_gap + reward_w
                group_x = max(row.x + row.w * 0.5, status_x - 16 - group_w)
                info_y = row.y + 18
                draw_text(self.screen, self.font_shop_small, progress_txt, (group_x, info_y), C_TEXT_DIM, shadow=False)
                draw_text(self.screen, self.font_shop_small, reward_txt, (group_x + progress_w + info_gap, info_y), C_COIN, shadow=False)

                status = "CLAIMED" if claimed else ("COMPLETE" if progress >= target else "IN PROGRESS")
                status_col = C_OK if claimed else (C_ACCENT if progress >= target else C_TEXT_DIM)
                draw_text(self.screen, self.font_shop_small, status, (status_x, row.y + 24), status_col, shadow=False)

                bar_w = 220
                bar_h = 8
                bar_x = row.right - bar_w - 18
                bar_y = row.y + row.h - 16
                pygame.draw.rect(self.screen, (10, 10, 12), pygame.Rect(bar_x, bar_y, bar_w, bar_h), border_radius=6)
                fill_w = int(bar_w * clamp(progress / max(1, target), 0, 1))
                pygame.draw.rect(self.screen, C_ACCENT, pygame.Rect(bar_x, bar_y, fill_w, bar_h), border_radius=6)

        items = list(self.save.daily_challenges.get("items", [])) if self.challenges_view == "daily" else list(self.save.weekly_challenges.get("items", []))
        draw_list(items, list_rect)

        if self.challenges_back_btn:
            self.challenges_back_btn.update(1 / 60, mouse_pos, mouse_down, events)
            self.challenges_back_btn.draw(self.screen, self.font_med)
