"""Menu screens: main menu, settings and controls."""
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



class MenuScreenMixin:

    def draw_menu(self, events):
        self.screen.fill(C_BG)
        cx = WIDTH // 2
        t = time.time()
        self.refresh_challenges()

        draw_text(self.screen, self.font_big, "TANK GAME SURVIVAL", (cx, 80), C_TEXT, center=True)
        draw_text(self.screen, self.font_ui, "survive • upgrade • progress • unlock tanks", (cx, 118), C_TEXT_DIM, center=True, shadow=False)
        pygame.draw.line(self.screen, C_ACCENT, (cx - 360, 138), (cx + 360, 138), 2)
        pygame.draw.line(self.screen, C_ACCENT_2, (cx - 300, 144), (cx + 300, 144), 2)
        pygame.draw.circle(self.screen, C_ACCENT, (int(cx + math.sin(t * 1.3) * 340), 138), 4)
        pygame.draw.circle(self.screen, C_ACCENT_2, (int(cx + math.cos(t * 1.1) * 320), 138), 4)

        panel = pygame.Rect(cx - 380, 158, 760, 84)
        pygame.draw.rect(self.screen, (*C_PANEL, 235), panel, border_radius=12)
        pygame.draw.rect(self.screen, (*C_WALL_EDGE, 220), panel, 1, border_radius=12)

        wdef = WEAPONS.get(self.save.selected_weapon, WEAPONS["pistol"])
        draw_text(self.screen, self.font_ui, f"Coins: {self.save.coins}", (panel.x + 18, panel.y + 12), C_COIN, shadow=False)
        draw_text(self.screen, self.font_ui, f"Selected: {wdef.name}", (panel.x + 18, panel.y + 44), C_ACCENT, shadow=False)

        daily = list(self.save.daily_challenges.get("items", []) or [])
        weekly = list(self.save.weekly_challenges.get("items", []) or [])
        daily_done = sum(1 for i in daily if i.get("claimed"))
        weekly_done = sum(1 for i in weekly if i.get("claimed"))
        draw_text_right(self.screen, self.font_small, f"BEST SCORE   {self.save.best_score()}",
                        (panel.right - 18, panel.y + 14), C_TEXT_DIM, shadow=False)
        draw_text_right(self.screen, self.font_small, f"DAILY {daily_done}/{len(daily)}     WEEKLY {weekly_done}/{len(weekly)}",
                        (panel.right - 18, panel.y + 46), C_TEXT_DIM, shadow=False)

        mouse_pos = pygame.mouse.get_pos()
        mouse_down = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)
        for b in self.menu_buttons:
            b.update(1 / 60, mouse_pos, mouse_down, events)
            b.draw(self.screen, self.font_small if b.small else self.font_med)

        # Top-left X quit button
        self.menu_quit_btn.update(1 / 60, mouse_pos, mouse_down, events)
        self.menu_quit_btn.draw(self.screen, self.font_med)

        pygame.draw.line(self.screen, C_WALL_EDGE, (cx - 300, 546), (cx + 300, 546), 1)
        draw_text(self.screen, self.font_small, "WASD move  •  Mouse aim  •  Hold LMB shoot  •  Space dash",
                  (cx, 566), C_TEXT_DIM, center=True, shadow=False)
        draw_text(self.screen, self.font_small, "F auto-fire  •  ESC pause  •  ENTER start run",
                  (cx, 590), C_TEXT_DIM, center=True, shadow=False)

    def draw_settings(self, events):
        self.screen.fill(C_BG)
        cx = WIDTH // 2

        draw_text(self.screen, self.font_big, "SETTINGS", (cx, 92), C_TEXT, center=True)
        draw_text(self.screen, self.font_ui, "Customize your run feel", (cx, 128), C_TEXT_DIM, center=True, shadow=False)

        box = pygame.Rect(140, 175, WIDTH - 280, HEIGHT - 275)
        pygame.draw.rect(self.screen, (*C_PANEL, 235), box, border_radius=12)
        pygame.draw.rect(self.screen, (*C_WALL_EDGE, 220), box, 1, border_radius=12)

        opt_w = 248
        opt_h = 52
        opt_y = box.y + 34
        opt_gap = 14

        mouse_pos = pygame.mouse.get_pos()
        mouse_down = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)

        options = [
            ("Fullscreen", "fullscreen"),
            ("Audio", "audio"),
            ("Shake", "shake"),
            ("Damage #s", "damage_numbers"),
        ]
        usable = box.w - 52
        opt_w = (usable - (len(options) - 1) * opt_gap) // len(options)
        total_w = len(options) * opt_w + (len(options) - 1) * opt_gap
        opt_x = box.x + (box.w - total_w) // 2

        def draw_option(label, key, x):
            value_on = bool(self.save.settings.get(key, True))
            rect = pygame.Rect(x, opt_y, opt_w, opt_h)
            pygame.draw.rect(self.screen, (*C_PANEL_2, 245), rect, border_radius=12)
            pygame.draw.rect(self.screen, (*C_WALL_EDGE, 200), rect, 2, border_radius=12)
            draw_text(self.screen, self.font_shop_small, label, (rect.x + 14, rect.y + 15), C_TEXT, shadow=False)
            badge = pygame.Rect(rect.right - 66, rect.y + 12, 52, 28)
            pygame.draw.rect(self.screen, (*C_OK, 220) if value_on else (*C_TEXT_DIM, 160), badge, border_radius=8)
            pygame.draw.rect(self.screen, C_WALL_EDGE, badge, 2, border_radius=8)
            rect_centered_text(self.screen, self.font_tiny, "ON" if value_on else "OFF", badge,
                               (10, 20, 20) if value_on else (25, 25, 32), shadow=False)
            if rect.collidepoint(mouse_pos) and mouse_down:
                if key == "fullscreen":
                    self.toggle_fullscreen()
                else:
                    self.toggle_setting(key)

        for i, (label, key) in enumerate(options):
            draw_option(label, key, opt_x + i * (opt_w + opt_gap))

        reset_y = opt_y + opt_h + 46
        draw_text(self.screen, self.font_shop_item, "RESET", (box.x + 26, reset_y), C_TEXT, shadow=False)

        reset_btn_y = reset_y + 32
        reset_w = 240
        reset_h = 46
        reset_gap = 16
        reset_w_total = reset_w * 2 + reset_gap
        reset_x = box.x + (box.w - reset_w_total) // 2

        reset_settings_btn = Button(pygame.Rect(reset_x, reset_btn_y, reset_w, reset_h), "Defaults", self.reset_settings)
        reset_cosmetics_btn = Button(pygame.Rect(reset_x + reset_w + reset_gap, reset_btn_y, reset_w, reset_h), "Reset Cosmetics", self.reset_cosmetics)

        for btn in (reset_settings_btn, reset_cosmetics_btn):
            btn.update(1 / 60, mouse_pos, mouse_down, events)
            btn.draw(self.screen, self.font_shop_small)

        hint_y = reset_btn_y + reset_h + 34
        hint_box = pygame.Rect(box.x + 26, hint_y, box.w - 52, 96)
        pygame.draw.rect(self.screen, (*C_PANEL_2, 150), hint_box, border_radius=12)
        pygame.draw.rect(self.screen, (*C_WALL_EDGE, 150), hint_box, 2, border_radius=12)
        tips = [
            "Loaded saves are upgraded automatically - new weapons and cosmetics sync themselves in.",
            "Damage numbers can be turned off for a cleaner screen on spammy tanks.",
            "Screen shake off is recommended if the camera whipping makes you seasick.",
        ]
        ty = hint_box.y + 12
        for tip in tips:
            draw_text(self.screen, self.font_shop_small, clamp_text(self.font_shop_small, tip, hint_box.w - 28),
                      (hint_box.x + 14, ty), C_TEXT_DIM, shadow=False)
            ty += 26

        if self.settings_back_btn:
            self.settings_back_btn.update(1 / 60, mouse_pos, mouse_down, events)
            self.settings_back_btn.draw(self.screen, self.font_med)

    def draw_controls(self, events):
        self.screen.fill(C_BG)
        cx = WIDTH // 2
        draw_text(self.screen, self.font_big, "CONTROLS", (cx, 92), C_TEXT, center=True)
        draw_text(self.screen, self.font_ui, "Everything you need to survive", (cx, 128), C_TEXT_DIM, center=True, shadow=False)

        box = pygame.Rect(200, 170, WIDTH - 400, HEIGHT - 290)
        pygame.draw.rect(self.screen, (*C_PANEL, 235), box, border_radius=12)
        pygame.draw.rect(self.screen, (*C_WALL_EDGE, 220), box, 1, border_radius=12)

        lines = [
            ("WASD", " Drive your tank"),
            ("Mouse", " Aim the turret"),
            ("Left Mouse", " Fire (hold for full-auto)"),
            ("F", " Toggle auto-fire"),
            ("Space", " Dash - briefly invulnerable"),
            ("ESC", " Pause / step back a screen"),
            ("Enter", " Start a run from the menu"),
        ]
        y = box.y + 20
        for key, desc in lines:
            key_rect = pygame.Rect(box.x + 22, y, 148, 34)
            pygame.draw.rect(self.screen, (*C_PANEL_2, 245), key_rect, border_radius=9)
            pygame.draw.rect(self.screen, (*C_WALL_EDGE, 210), key_rect, 2, border_radius=9)
            rect_centered_text(self.screen, self.font_small, key, key_rect, C_ACCENT, shadow=False)
            draw_text(self.screen, self.font_shop_small, desc, (key_rect.right + 16, y + 7), C_TEXT_DIM, shadow=False)
            y += 42

        mouse_pos = pygame.mouse.get_pos()
        mouse_down = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)
        if self.controls_back_btn:
            self.controls_back_btn.update(1 / 60, mouse_pos, mouse_down, events)
            self.controls_back_btn.draw(self.screen, self.font_med)
