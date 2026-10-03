"""Reusable clickable widgets (flat house style)."""
from __future__ import annotations

import pygame

from tankgame.config import *
from tankgame.ui.text import *


class Button:
    def __init__(self, rect: pygame.Rect, text: str, callback, hotkey=None, small=False):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.callback = callback
        self.hotkey = hotkey
        self.small = small
        self.hover = False
        self.pulse = 0.0
        self.enabled = True

    def update(self, dt, mouse_pos, mouse_down, events):
        self.hover = self.enabled and self.rect.collidepoint(mouse_pos)
        self.pulse = (self.pulse + dt * 3.0) % (math.tau)

        clicked = False
        if self.hover and mouse_down:
            clicked = True

        for e in events:
            if e.type == pygame.KEYDOWN and self.hotkey and e.key == self.hotkey:
                clicked = True

        if clicked and self.enabled:
            self.callback()

    def draw(self, surf, font, alpha=255):
        """Flat button: one fill, one hairline border, and a gentle lift on hover."""
        base = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        if not self.enabled:
            bg = (*C_PANEL, int(alpha * 0.6))
            edge = (*C_WALL_EDGE, int(alpha * 0.6))
        elif self.hover:
            bg = (44, 58, 70, alpha)
            edge = (*C_ACCENT, alpha)
        else:
            bg = (*C_PANEL_2, alpha)
            edge = (*C_WALL_EDGE, alpha)

        pygame.draw.rect(base, bg, base.get_rect(), border_radius=10)
        pygame.draw.rect(base, edge, base.get_rect(), 1, border_radius=10)
        if self.hover and self.enabled:
            # Thin accent underline instead of the old animated glow.
            pygame.draw.rect(base, (*C_ACCENT, alpha), pygame.Rect(0, self.rect.height - 3, self.rect.width, 3),
                             border_radius=2)

        surf.blit(base, self.rect.topleft)
        txt_col = C_TEXT if self.enabled else (104, 112, 132)
        draw_text(surf, font, self.text, self.rect.center, txt_col, center=True, shadow=False)


class TabButton:
    """Small tab-like button for Shop navigation."""
    def __init__(self, rect: pygame.Rect, text: str, on_click, tab_id: str):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.on_click = on_click
        self.tab_id = tab_id
        self.hover = False

    def update(self, mouse_pos, mouse_down):
        self.hover = self.rect.collidepoint(mouse_pos)
        if self.hover and mouse_down:
            self.on_click(self.tab_id)

    def draw(self, surf, font, active=False):
        bg = (*C_PANEL_2, 245) if active else (*C_PANEL, 200)
        edge = C_ACCENT if active else (C_WALL_EDGE if not self.hover else C_TEXT_DIM)
        pygame.draw.rect(surf, bg, self.rect, border_radius=10)
        pygame.draw.rect(surf, edge, self.rect, 1, border_radius=10)
        rect_centered_text(surf, font, self.text, self.rect,
                           C_TEXT if active else C_TEXT_DIM, shadow=False)
