"""Reusable clickable widgets in the liquid-glass house style.

The public API is unchanged from the old flat widgets (``Button.update/draw`` and
``TabButton.update/draw``), so every screen keeps working - only the look changes: frosted
pill fills, a bright specular top edge, a smooth hover lift and a quick press dip.
"""
from __future__ import annotations

import pygame

from tankgame.config import *
from tankgame.ui.text import draw_text, rect_centered_text, get_font
from tankgame.ui import glass


def _fit_font(font, label: str, max_w: int):
    """The given font, or a smaller default font if the label would not fit."""
    if font.size(label)[0] <= max_w:
        return font
    size = font.get_height()
    while size > 12 and get_font(size).size(label)[0] > max_w:
        size -= 1
    return get_font(size)


class Button:
    def __init__(self, rect: pygame.Rect, text: str, callback, hotkey=None, small=False,
                 kind: str = "normal"):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.callback = callback
        self.hotkey = hotkey
        self.small = small
        self.kind = kind          # normal | primary | danger | ghost
        self.hover = False
        self.enabled = True
        self._hi = 0.0            # eased hover amount 0..1
        self._press = 0.0         # eased press amount 0..1
        self._down = False

    def update(self, dt, mouse_pos, mouse_down, events):
        self.hover = self.enabled and self.rect.collidepoint(mouse_pos)
        target = 1.0 if self.hover else 0.0
        self._hi += (target - self._hi) * min(1.0, dt * 14.0)
        self._press += ((1.0 if (self.hover and self._down) else 0.0) - self._press) * min(1.0, dt * 20.0)

        clicked = False
        if self.hover and mouse_down:
            clicked = True
        self._down = self.hover and (mouse_down or self._down and pygame.mouse.get_pressed(3)[0])
        for e in events:
            if e.type == pygame.KEYDOWN and self.hotkey and e.key == self.hotkey:
                clicked = True
        if clicked and self.enabled:
            self.callback()

    def _colors(self):
        if self.kind == "primary":
            return glass.GL_ACCENT, glass.GL_ACCENT_2
        if self.kind == "danger":
            return glass.GL_BAD, (255, 150, 120)
        return glass.GL_ACCENT, glass.GL_ACCENT

    def draw(self, surf, font, alpha=255):
        r = self.rect
        lift = int(self._hi * 2.0 - self._press * 2.0)
        draw_r = pygame.Rect(r.x, r.y - lift, r.w, r.h)
        rad = min(draw_r.height // 2, 16)
        a0, a1 = self._colors()

        if not self.enabled:
            glass.panel(surf, draw_r, radius=rad, tint=(60, 66, 82), alpha=40,
                        accent=None, glow=False, shadow=False)
            draw_text(surf, _fit_font(font, self.text, draw_r.w - 14), self.text, draw_r.center,
                      (110, 118, 138), center=True)
            return

        primary = self.kind in ("primary", "danger")
        if primary:
            base = glass._vgrad(draw_r.size, (*glass.lerp_color(a0, (255, 255, 255), 0.22), 236),
                                (*glass.lerp_color(a0, a1, 0.5), 236))
            mask = glass._round_mask(draw_r.size, rad)
            base.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            glass._drop_shadow(surf, draw_r, rad)
            surf.blit(base, draw_r.topleft)
            sheen = pygame.Surface((draw_r.w, draw_r.h // 2), pygame.SRCALPHA)
            pygame.draw.rect(sheen, (255, 255, 255, int(70 + 40 * self._hi)), sheen.get_rect(),
                             border_top_left_radius=rad, border_top_right_radius=rad)
            surf.blit(sheen, draw_r.topleft)
            txt_col = (10, 16, 20)
        else:
            tint = glass.lerp_color((150, 170, 205), a0, 0.18 * self._hi)
            glass.panel(surf, draw_r, radius=rad, tint=tint,
                        alpha=int(40 + 44 * self._hi),
                        accent=a0 if self._hi > 0.02 else None,
                        glow=False, shadow=self._hi > 0.3)
            txt_col = glass.lerp_color(glass.GL_TEXT, (255, 255, 255), self._hi)

        if self._hi > 0.02 and not primary:
            under = pygame.Surface((draw_r.w, 3), pygame.SRCALPHA)
            under.fill((*a0, int(200 * self._hi)))
            surf.blit(under, (draw_r.x, draw_r.bottom - 3))

        draw_text(surf, _fit_font(font, self.text, draw_r.w - 14), self.text, draw_r.center, txt_col, center=True)


class TabButton:
    """Segmented-control style tab."""
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
        r = self.rect
        rad = min(r.height // 2, 14)
        if active:
            grad = glass._vgrad(r.size, (*glass.lerp_color(glass.GL_ACCENT, (255, 255, 255), 0.25), 235),
                                (*glass.lerp_color(glass.GL_ACCENT, glass.GL_ACCENT_2, 0.5), 235))
            mask = glass._round_mask(r.size, rad)
            grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(grad, r.topleft)
            sheen = pygame.Surface((r.w, r.h // 2), pygame.SRCALPHA)
            pygame.draw.rect(sheen, (255, 255, 255, 70), sheen.get_rect(),
                             border_top_left_radius=rad, border_top_right_radius=rad)
            surf.blit(sheen, r.topleft)
            col = (12, 18, 24)
        else:
            glass.panel(surf, r, radius=rad, tint=(140, 158, 190),
                        alpha=46 if self.hover else 30,
                        accent=glass.GL_ACCENT if self.hover else None,
                        glow=False, shadow=False)
            col = glass.GL_TEXT if self.hover else glass.GL_TEXT_DIM
        rect_centered_text(surf, _fit_font(font, self.text, r.w - 14), self.text, r, col)


_BUTTON_CACHE = {}


def cached_button(key, rect, text, callback, kind="normal", enabled=True) -> Button:
    """A Button that survives across frames (so its hover/press animation can play out) for
    screens that lay their buttons out every frame. ``key`` must be stable per logical button."""
    b = _BUTTON_CACHE.get(key)
    if b is None:
        b = Button(rect, text, callback, kind=kind)
        _BUTTON_CACHE[key] = b
    b.rect = pygame.Rect(rect)
    b.text = text
    b.callback = callback
    b.kind = kind
    b.enabled = enabled
    return b
