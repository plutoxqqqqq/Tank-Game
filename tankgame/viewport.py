"""Decide the logical viewport so fullscreen fills the screen with no black bars.

The game always draws at a fixed logical resolution and lets ``pygame.SCALED`` stretch that onto
the real window. If the logical resolution shares the monitor's aspect ratio there is nothing to
letterbox, so at startup we pick the width that matches the desktop at our fixed height. This runs
once, before the rest of the package imports ``config``, so every module sees the final size.
"""
from __future__ import annotations

from typing import Optional, Tuple

import pygame

from tankgame import config

DEFAULT_W, DEFAULT_H = 1100, 650
MIN_W, MAX_W = 700, 2560


def desktop_size() -> Optional[Tuple[int, int]]:
    """Best-effort (width, height) of the primary monitor, or None if unavailable."""
    try:
        if not pygame.display.get_init():
            pygame.display.init()
    except Exception:
        pass
    try:
        sizes = pygame.display.get_desktop_sizes()
        if sizes:
            w, h = sizes[0]
            if w > 0 and h > 0:
                return int(w), int(h)
    except Exception:
        pass
    return None


def configure_viewport() -> Tuple[int, int]:
    """Set ``config.WIDTH``/``HEIGHT`` to fill the monitor with no bars; return the chosen size."""
    width = DEFAULT_W
    desk = desktop_size()
    if desk is not None:
        dw, dh = desk
        if dw > 0 and dh > 0:
            width = max(MIN_W, min(MAX_W, int(round(DEFAULT_H * dw / dh))))
    config.WIDTH = width
    config.HEIGHT = DEFAULT_H
    return width, DEFAULT_H
