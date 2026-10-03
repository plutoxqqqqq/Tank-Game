"""Window / fullscreen handling."""
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

        Fullscreen is a borderless window at the monitor's native size - the way a maximised game
        takes the whole screen - with pygame.SCALED stretching the fixed logical frame onto it.
        The logical size tracks the monitor's aspect ratio (tankgame.viewport), so nothing is
        letterboxed or stretched out of shape. pygame.SCALED also converts mouse input back to
        logical coordinates, so no other code has to know the window is fullscreen.
        """
        if self.save.settings.get("fullscreen", False):
            desk = desktop_size()
            if desk is not None:
                try:
                    self.screen = pygame.display.set_mode(desk, pygame.NOFRAME | pygame.SCALED)
                    return
                except pygame.error:
                    pass
            try:
                self.screen = pygame.display.set_mode((WIDTH, HEIGHT),
                                                      pygame.FULLSCREEN | pygame.SCALED)
                return
            except pygame.error:
                pass
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))

    def toggle_fullscreen(self):
        self.save.settings["fullscreen"] = not bool(self.save.settings.get("fullscreen", False))
        self.apply_display_mode()
        self.save.save()
