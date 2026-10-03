"""Assembles the Game class from its mixins."""
from __future__ import annotations

from tankgame.game.app import AppMixin
from tankgame.game.display import DisplayMixin
from tankgame.game.meta import MetaMixin
from tankgame.game.world import WorldMixin
from tankgame.game.combat import CombatMixin
from tankgame.game.progression import ProgressionMixin
from tankgame.game.minigames import MinigameMixin
from tankgame.game.run import RunMixin
from tankgame.game.render import RenderMixin
from tankgame.ui.screens.menu import MenuScreenMixin
from tankgame.ui.screens.info import InfoScreenMixin
from tankgame.ui.screens.weapons import WeaponsScreenMixin
from tankgame.ui.screens.shop import ShopScreenMixin
from tankgame.ui.screens.minigames import MinigameScreenMixin
from tankgame.ui.screens.levelup import LevelUpScreenMixin
from tankgame.ui.screens.paused import PausedScreenMixin
from tankgame.ui.screens.gameover import GameOverScreenMixin


class Game(AppMixin, DisplayMixin, MetaMixin, WorldMixin, CombatMixin, ProgressionMixin,
           MinigameMixin, RunMixin, RenderMixin, MenuScreenMixin, InfoScreenMixin,
           WeaponsScreenMixin, ShopScreenMixin, MinigameScreenMixin, LevelUpScreenMixin,
           PausedScreenMixin, GameOverScreenMixin):
    """A full game session. Behaviour lives in the mixins; see the package docs."""
