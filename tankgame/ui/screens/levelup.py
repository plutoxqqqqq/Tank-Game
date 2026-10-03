"""The level-up card screen."""
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



class LevelUpScreenMixin:

    def draw_levelup(self, events):
        self.draw_background()
        self.draw_obstacles()
        self.draw_entities()
        self.draw_minigame_view()
        self.draw_hud()

        self.draw_overlay_dim(205)
        cx = WIDTH // 2
        draw_text(self.screen, self.font_big, "LEVEL UP!", (cx, 92), C_ACCENT, center=True)
        queued = max(0, self.pending_levelups - 1)
        subtitle = "Pick an upgrade" if queued == 0 else f"Pick an upgrade  •  {queued} more queued"
        draw_text(self.screen, self.font_ui, subtitle, (cx, 126), C_TEXT_DIM, center=True, shadow=False)

        box = pygame.Rect(cx - 380, 150, 760, 352)
        self.draw_panel(box, (*C_PANEL, 236), (*C_WALL_EDGE, 220), radius=14)

        mouse_pos = pygame.mouse.get_pos()
        mouse_down = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)

        # 1/2/3 (or numpad) picks a card without touching the mouse.
        pick_keys = {pygame.K_1: 0, pygame.K_KP1: 0, pygame.K_2: 1, pygame.K_KP2: 1, pygame.K_3: 2, pygame.K_KP3: 2}
        for e in events:
            if e.type == pygame.KEYDOWN and e.key in pick_keys:
                idx = pick_keys[e.key]
                if idx < len(self.level_cards):
                    self.pick_upgrade(self.level_cards[idx][1])
                    return

        for idx, (rect, up) in enumerate(self.level_cards):
            hover = rect.collidepoint(mouse_pos)
            is_ultra = up.ultra
            if is_ultra:
                # GOLD, unmistakably: a warm amber fill behind gold trim, so an ultra never reads as
                # another ordinary (teal) card. The colour lives in the trim + text, not the text
                # alone, so it stays legible.
                bg = (74, 58, 14, 252) if hover else (56, 44, 10, 248)
                edge = C_ULTRA
            else:
                bg = (*C_PANEL_2, 250) if hover else (*C_PANEL_2, 235)
                edge = C_ACCENT if hover else C_WALL_EDGE
            pygame.draw.rect(self.screen, bg, rect, border_radius=14)
            pygame.draw.rect(self.screen, edge, rect, 4 if is_ultra else 2, border_radius=14)
            if is_ultra:
                # Double gold ring reads instantly as the rare pick.
                pygame.draw.rect(self.screen, (196, 158, 46), rect.inflate(-10, -10), 2, border_radius=10)

            tag_area = pygame.Rect(rect.right - 158, rect.y + 14, 132, rect.h - 28)
            if is_ultra:
                pygame.draw.rect(self.screen, (*C_ULTRA, 240), tag_area, border_radius=12)
                pygame.draw.rect(self.screen, (255, 244, 196), tag_area, 2, border_radius=12)
            else:
                pygame.draw.rect(self.screen, (*C_PANEL, 230), tag_area, border_radius=12)
                pygame.draw.rect(self.screen, (*C_WALL_EDGE, 210), tag_area, 2, border_radius=12)
            rect_centered_text(self.screen, self.font_shop_small, f"{idx + 1}. {up.tag}", tag_area,
                               (44, 32, 0) if is_ultra else C_ACCENT, shadow=False)

            draw_text(self.screen, self.font_shop_item, up.name, (rect.x + 18, rect.y + 16),
                      C_ULTRA if is_ultra else C_TEXT, shadow=not is_ultra)
            draw_text(self.screen, self.font_shop_desc, up.desc, (rect.x + 18, rect.y + 46),
                      (255, 232, 168) if is_ultra else C_TEXT_DIM, shadow=False)

            # Tank kicker: this card pays extra while you drive your tank.
            note = up.bonus_note_for(self.player.weapon_id)
            if is_ultra:
                draw_text(self.screen, self.font_shop_desc, "\u2605 ULTRA \u2014 exclusive to your tank",
                          (rect.x + 18, rect.y + 66), C_ULTRA, shadow=False)
            elif note:
                draw_text(self.screen, self.font_shop_desc, f"\u25b6 {note}", (rect.x + 18, rect.y + 66),
                          C_WARN, shadow=False)

            if hover and mouse_down:
                self.pick_upgrade(up)
                return
