"""Font helpers and the shared text-drawing primitives."""
from __future__ import annotations

import pygame

from tankgame.config import *


def draw_text(surf, font, text, pos, color=C_TEXT, center=False, shadow=False):
    """Text with an optional *thin* shadow.

    Defaults to no shadow now - the old hard 2px black drop shadow on every label is what made the
    whole UI look dated. Screens that sit directly over the arena can still ask for one.
    """
    img = font.render(text, True, color)
    r = img.get_rect()
    if center:
        r.center = pos
    else:
        r.topleft = pos
    if shadow:
        sh = font.render(text, True, (8, 10, 14))
        sh_r = sh.get_rect(center=r.center) if center else sh.get_rect(topleft=(r.x + 1, r.y + 1))
        surf.blit(sh, sh_r)
    surf.blit(img, r)
    return r


def draw_text_right(surf, font, text, topright, color=C_TEXT, shadow=True):
    img = font.render(text, True, color)
    r = img.get_rect()
    r.topright = topright
    if shadow:
        sh = font.render(text, True, (0, 0, 0))
        surf.blit(sh, sh.get_rect(topright=(r.right + 2, r.top + 2)))
    surf.blit(img, r)
    return r


_FONT_CACHE: Dict[int, pygame.font.Font] = {}


def get_font(size: int) -> pygame.font.Font:
    """Shared default font, cached so draw code never builds one per frame."""
    f = _FONT_CACHE.get(size)
    if f is None:
        f = pygame.font.Font(None, size)
        _FONT_CACHE[size] = f
    return f


def clamp_text(font, text, max_width):
    if font.size(text)[0] <= max_width:
        return text
    ellipsis = "..."
    ellipsis_w = font.size(ellipsis)[0]
    if ellipsis_w >= max_width:
        return ellipsis
    trimmed = text
    target_w = max_width - ellipsis_w
    while trimmed and font.size(trimmed)[0] > target_w:
        trimmed = trimmed[:-1]
    return f"{trimmed}{ellipsis}"


def circle_outline(surf, color, pos, radius, width=2):
    pygame.draw.circle(surf, color, (int(pos[0]), int(pos[1])), int(radius), int(width))

def rect_centered_text(surf, font, text, rect: pygame.Rect, color, shadow=False):
    img = font.render(text, True, color)
    r = img.get_rect()
    r.center = rect.center
    if shadow:
        sh = font.render(text, True, (0, 0, 0))
        sh_r = sh.get_rect(center=(r.centerx + 2, r.centery + 2))
        surf.blit(sh, sh_r)
    surf.blit(img, r)
