"""Window / fullscreen handling."""
from __future__ import annotations

import math
import os
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
from tankgame.viewport import desktop_size




class DisplayMixin:

    def apply_display_mode(self):
        """(Re)create the window to match the fullscreen preference.

        Fullscreen is true *desktop* fullscreen: FULLSCREEN together with SCALED makes SDL cover
        the entire monitor (taskbar included) at its native resolution without a video-mode
        switch, so alt-tabbing stays instant and nothing behind the game shows through. The
        fixed logical frame is stretched onto it; the logical size already matches the
        monitor's aspect ratio (tankgame.viewport), so nothing is letterboxed or squashed.

        Windowed mode is resizable and can be maximised; SCALED keeps the picture in proportion.
        SCALED also maps mouse input back to logical coordinates, so no other code has to know
        how big the real window is.
        """
        if self.save.settings.get("fullscreen", False):
            try:
                self.screen = pygame.display.set_mode((WIDTH, HEIGHT),
                                                      pygame.FULLSCREEN | pygame.SCALED)
                return
            except pygame.error:
                pass
            # Fallback: a borderless window pinned to the top-left corner at the desktop size.
            desk = desktop_size()
            if desk is not None:
                os.environ["SDL_VIDEO_WINDOW_POS"] = "0,0"
                try:
                    self.screen = pygame.display.set_mode(desk, pygame.NOFRAME | pygame.SCALED)
                    return
                except pygame.error:
                    pass
                finally:
                    os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
        os.environ["SDL_VIDEO_CENTERED"] = "1"
        try:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE | pygame.SCALED)
        except pygame.error:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT))

    def toggle_fullscreen(self):
        self.save.settings["fullscreen"] = not bool(self.save.settings.get("fullscreen", False))
        self.apply_display_mode()
        self.save.save()
