"""The minigame list screen."""
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



class MinigameScreenMixin:

    def draw_minigames(self, events):
        self.screen.fill(C_BG)
        cx = WIDTH // 2
        draw_text(self.screen, self.font_big, "MINIGAMES", (cx, 52), C_TEXT, center=True)
        draw_text(self.screen, self.font_ui, "Short challenges - the further you get, the more coins",
                  (cx, 86), C_TEXT_DIM, center=True, shadow=False)
        draw_text_right(self.screen, self.font_ui, f"Coins: {self.save.coins}", (WIDTH - 44, 28), C_COIN, shadow=False)

        mouse_pos = pygame.mouse.get_pos()
        mouse_down = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)

        for rect, mg in self.mg_play_buttons:
            hover = rect.collidepoint(mouse_pos)
            clears = int(self.save.minigame_clears.get(mg.id, 0))
            best = float(self.save.minigame_best.get(mg.id, 0.0))
            bg = (*C_PANEL_2, 250) if hover else (*C_PANEL, 240)
            pygame.draw.rect(self.screen, bg, rect, border_radius=12)
            pygame.draw.rect(self.screen, mg.accent if hover else C_WALL_EDGE, rect, 1, border_radius=12)
            pygame.draw.rect(self.screen, mg.accent, pygame.Rect(rect.x, rect.y + 7, 4, rect.h - 14),
                             border_radius=2)

            compact = rect.h < 48
            name_font = self.font_shop_small if compact else self.font_shop_item
            desc_font = self.font_tiny if compact else self.font_shop_small
            draw_text(self.screen, name_font, mg.name, (rect.x + 20, rect.y + (3 if compact else 7)),
                      C_TEXT, shadow=False)
            draw_text(self.screen, desc_font, mg.desc, (rect.x + 20, rect.y + (21 if compact else 30)),
                      C_TEXT_DIM, shadow=False)

            pips_x = rect.right - 316
            for i in range(5):
                col = mg.accent if i < mg.difficulty else (58, 64, 80)
                pygame.draw.circle(self.screen, col, (pips_x + i * 13, rect.y + 18), 4)
            draw_text(self.screen, self.font_tiny, f"DIFFICULTY {mg.difficulty}/5",
                      (pips_x - 4, rect.y + 28), C_TEXT_DIM, shadow=False)

            reward_txt = f"+{mg.reward} coins" if clears == 0 else f"+{mg.reward}  x{clears} cleared"
            draw_text_right(self.screen, self.font_shop_small, reward_txt, (rect.right - 118, rect.y + 10),
                            C_COIN, shadow=False)
            if best > 0.0:
                draw_text_right(self.screen, self.font_tiny, f"best {int(best * 100)}%",
                                (rect.right - 118, rect.y + 30), C_TEXT_DIM, shadow=False)

            btn_rect = pygame.Rect(rect.right - 100, rect.y + 8, 86, rect.h - 16)
            btn = Button(btn_rect, "Play", lambda mid=mg.id: self.start_minigame(mid))
            btn.update(1 / 60, mouse_pos, mouse_down, events)
            btn.draw(self.screen, self.font_shop_small)

        if self.minigame_result is not None:
            res = self.minigame_result
            band = getattr(self, "mg_result_rect", None) or pygame.Rect(cx - 330, 108, 660, 46)
            ok = bool(res["cleared"])
            col = C_OK if ok else C_WARN
            self.draw_panel(band, (*C_PANEL, 250), (*col, 230), radius=12)
            draw_text(self.screen, self.font_shop_small,
                      f"{'CLEARED' if ok else 'FAILED'}  -  {res['name']}", (band.x + 16, band.y + 3),
                      col, shadow=False)
            draw_text(self.screen, self.font_tiny,
                      f"+{res['coins']} coins   ({int(float(res['progress']) * 100)}% of the objective)",
                      (band.x + 16, band.y + 24), C_COIN, shadow=False)
            if band.collidepoint(mouse_pos) and mouse_down:
                self.minigame_result = None   # click to dismiss

        self.mg_back_btn.update(1 / 60, mouse_pos, mouse_down, events)
        self.mg_back_btn.draw(self.screen, self.font_med)
        draw_text(self.screen, self.font_small, "ESC or Back returns to the menu",
                  (cx, HEIGHT - 24), C_TEXT_DIM, center=True, shadow=False)
