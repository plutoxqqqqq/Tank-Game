"""The game-over screen."""
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



class GameOverScreenMixin:

    def draw_gameover(self, events):
        self.award_coins_if_needed()
        self.record_leaderboard_if_needed()
        # R (or ENTER) drops you straight back into a fresh run - no menu detour.
        for e in events:
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER):
                self.restart_run()
                return
        self.draw_background()
        self.draw_obstacles()
        self.draw_entities()
        self.draw_hud()

        self.draw_overlay_dim(215)
        cx = WIDTH // 2
        draw_text(self.screen, self.font_big, "GAME OVER", (cx, 112), C_ACCENT_2, center=True)
        if self.new_best:
            badge = pygame.Rect(cx - 118, 150, 236, 34)
            self.draw_panel(badge, (*C_OK, 55), (*C_OK, 225), radius=10)
            rect_centered_text(self.screen, self.font_ui, "NEW BEST SCORE", badge, C_OK, shadow=False)

        # 3 x 2 stat grid - the old single column ran underneath the Restart button.
        panel = pygame.Rect(cx - 330, 198, 660, 200)
        self.draw_panel(panel, (*C_PANEL, 236), (*C_WALL_EDGE, 220), radius=14)
        stats = (
            ("SCORE", str(self.player.score), C_TEXT),
            ("TIME", f"{int(self.survival_time)}s", C_TEXT),
            ("WAVE", str(self.wave), C_ACCENT),
            ("LEVEL", str(self.player.level), C_ACCENT),
            ("KILLS", str(int(self.run_stats["kills"])), C_TEXT),
            ("DAMAGE", f"{int(self.run_stats['damage'])}", C_TEXT),
            ("ACCURACY", f"{self.accuracy():.0f}%", C_TEXT),
            ("COINS EARNED", f"+{self.last_run_coins_earned}", C_COIN),
        )
        col_w = (panel.w - 48) // 4
        for i, (label, value, col) in enumerate(stats):
            sx = panel.x + 24 + (i % 4) * col_w
            sy = panel.y + 28 + (i // 4) * 84
            draw_text(self.screen, self.font_shop_small, label, (sx, sy), C_TEXT_DIM, shadow=False)
            draw_text(self.screen, self.font_med, value, (sx, sy + 24), col)

        if self.run_bonus_coins > 0:
            draw_text(self.screen, self.font_small,
                      f"includes +{self.run_bonus_coins} banked boss + twist bonus",
                      (panel.centerx, panel.bottom + 8), C_COIN, center=True, shadow=False)

        mouse_pos = pygame.mouse.get_pos()
        mouse_down = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)
        for b in self.gameover_buttons:
            b.update(1 / 60, mouse_pos, mouse_down, events)
            b.draw(self.screen, self.font_med)

        draw_text(self.screen, self.font_small, "Press R to restart  •  ESC for the menu",
                  (cx, HEIGHT - 24), C_TEXT_DIM, center=True, shadow=False)
        

    # =========================================================
    # MAIN LOOP
    # =========================================================
