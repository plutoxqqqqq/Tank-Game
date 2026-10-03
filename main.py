"""Tank Game Rebirth — entry point.

The game used to be this one file. It now lives in the ``tankgame`` package, split by
responsibility (config, data, entities, art, ui, game). This module boots it and re-exports the
public names, so anything that did ``import main`` keeps working unchanged.

    python main.py

See ``CHANGELOG.md`` for the full history and ``tankgame/README.md`` for the layout.
"""
from __future__ import annotations

import pygame
from pygame.math import Vector2

# Size the logical viewport to the monitor BEFORE the package modules import the constants, so
# fullscreen fills the whole screen with no letterboxing.
from tankgame.viewport import configure_viewport

configure_viewport()

# Re-export the public surface (constants, data tables, entities, helpers) so `import main` still
# exposes everything callers and the smoke-test harness rely on.
from tankgame.config import *          # noqa: E402,F401,F403
from tankgame.util import *            # noqa: E402,F401,F403
from tankgame.ui.text import *         # noqa: E402,F401,F403
from tankgame.audio import *           # noqa: E402,F401,F403
from tankgame.save import SaveManager  # noqa: E402,F401
from tankgame.data.weapons import *    # noqa: E402,F401,F403
from tankgame.data.traits import *     # noqa: E402,F401,F403
from tankgame.data.upgrades import *   # noqa: E402,F401,F403
from tankgame.data.shop import *       # noqa: E402,F401,F403
from tankgame.data.maps import *       # noqa: E402,F401,F403
from tankgame.data.mutators import *   # noqa: E402,F401,F403
from tankgame.data.minigames import *  # noqa: E402,F401,F403
from tankgame.data.mastery import *    # noqa: E402,F401,F403
from tankgame.entities.fx import *     # noqa: E402,F401,F403
from tankgame.entities.projectile import *  # noqa: E402,F401,F403
from tankgame.entities.pickup import *      # noqa: E402,F401,F403
from tankgame.entities.enemies import *     # noqa: E402,F401,F403
from tankgame.entities.drone import *       # noqa: E402,F401,F403
from tankgame.entities.meteor import *      # noqa: E402,F401,F403
from tankgame.entities.player import Player  # noqa: E402,F401
from tankgame.art.tank_art import draw_tank  # noqa: E402,F401
from tankgame.ui.widgets import Button, TabButton  # noqa: E402,F401
from tankgame.game import Game              # noqa: E402,F401


def main() -> None:
    Game().run()


if __name__ == "__main__":
    main()
