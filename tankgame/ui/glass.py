"""Liquid-glass UI toolkit.

A small, self-contained set of drawing primitives that give the whole UI an Apple-ish
"frosted glass" look: translucent panels with a soft vertical gradient, a bright specular
line along the top edge, a hairline border, and a gentle drop shadow. Everything is cached
by size so a screen full of panels still draws cheaply.

Nothing here touches game state - screens build a small layout and call these helpers, so
the look lives in one place and every screen stays consistent.
"""
from __future__ import annotations

import math
import time
from typing import Dict, Optional, Tuple

import pygame

from tankgame.config import *
from tankgame.ui.text import get_font

Color = Tuple[int, int, int]
ColorA = Tuple[int, int, int, int]


# ---------------------------------------------------------------------------
# Palette - a cool, deep-glass theme with a cyan->magenta accent.
# ---------------------------------------------------------------------------
GL_BG_TOP = (10, 13, 20)
GL_BG_BOT = (6, 8, 13)
GL_GLASS = (150, 170, 205)          # tint the frosted fill leans toward
GL_TEXT = (238, 243, 252)
GL_TEXT_DIM = (158, 170, 196)
GL_TEXT_FAINT = (108, 120, 146)
GL_ACCENT = (95, 227, 209)
GL_ACCENT_2 = (158, 130, 255)
GL_ACCENT_3 = (255, 120, 184)
GL_GOOD = (120, 232, 160)
GL_WARN = (255, 196, 92)
GL_BAD = (255, 110, 128)
GL_GOLD = (255, 209, 102)
GL_COIN = (255, 214, 120)

_RADIUS = 18

_panel_cache: Dict[tuple, pygame.Surface] = {}
_shadow_cache: Dict[tuple, pygame.Surface] = {}
_vignette_cache: Dict[Tuple[int, int], pygame.Surface] = {}
_bg_cache: Dict[Tuple[int, int], pygame.Surface] = {}
_bar_cache: Dict[tuple, pygame.Surface] = {}


def clear_cache():
    _panel_cache.clear()
    _shadow_cache.clear()
    _vignette_cache.clear()
    _bg_cache.clear()
    _bar_cache.clear()
    _text_cache.clear()


def pulse(speed: float = 1.0, lo: float = 0.0, hi: float = 1.0, phase: float = 0.0) -> float:
    """A 0..1 sine pulse on the wall clock, remapped to [lo, hi]."""
    t = 0.5 + 0.5 * math.sin(time.time() * speed * math.tau + phase)
    return lo + (hi - lo) * t


def lerp_color(a, b, t: float) -> Color:
    t = max(0.0, min(1.0, t))
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def _vgrad(size: Tuple[int, int], top: ColorA, bottom: ColorA) -> pygame.Surface:
    """A vertical gradient surface with per-row alpha."""
    w, h = size
    surf = pygame.Surface((1, h), pygame.SRCALPHA)
    for y in range(h):
        t = y / max(1, h - 1)
        surf.set_at((0, y), (
            int(top[0] + (bottom[0] - top[0]) * t),
            int(top[1] + (bottom[1] - top[1]) * t),
            int(top[2] + (bottom[2] - top[2]) * t),
            int(top[3] + (bottom[3] - top[3]) * t),
        ))
    return pygame.transform.smoothscale(surf, (w, h))


def background(screen: pygame.Surface):
    """A deep vertical-gradient backdrop with a faint diagonal sheen - the base of every menu."""
    w, h = screen.get_size()
    key = (w, h)
    bg = _bg_cache.get(key)
    if bg is None:
        bg = pygame.Surface((w, h)).convert()
        grad = _vgrad((w, h), (*GL_BG_TOP, 255), (*GL_BG_BOT, 255))
        bg.blit(grad, (0, 0))
        # Two soft accent glows bleeding in from the corners.
        glow = pygame.Surface((w, h), pygame.SRCALPHA)
        _radial(glow, (int(w * 0.18), int(h * 0.12)), int(h * 0.7),
                (*GL_ACCENT, 26), (*GL_ACCENT, 0))
        _radial(glow, (int(w * 0.86), int(h * 0.92)), int(h * 0.8),
                (*GL_ACCENT_2, 26), (*GL_ACCENT_2, 0))
        bg.blit(glow, (0, 0))
        _bg_cache[key] = bg
    screen.blit(bg, (0, 0))


def _radial(surf, center, radius, inner: ColorA, outer: ColorA, steps: int = 26):
    """Cheap radial gradient: concentric filled circles from inner to outer colour."""
    cx, cy = center
    for i in range(steps, 0, -1):
        t = i / steps
        r = int(radius * t)
        if r <= 0:
            continue
        col = (
            int(outer[0] + (inner[0] - outer[0]) * (1 - t)),
            int(outer[1] + (inner[1] - outer[1]) * (1 - t)),
            int(outer[2] + (inner[2] - outer[2]) * (1 - t)),
            int(outer[3] + (inner[3] - outer[3]) * (1 - t)),
        )
        pygame.draw.circle(surf, col, (cx, cy), r)


def _round_mask(size: Tuple[int, int], radius: int) -> pygame.Surface:
    m = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(m, (255, 255, 255, 255), m.get_rect(), border_radius=radius)
    return m


def _make_panel(w: int, h: int, radius: int, tint: Color, alpha: int,
                accent: Optional[Color], glow: bool) -> pygame.Surface:
    """Build (and cache) one frosted-glass panel surface of the given size/style."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)

    # Base frosted fill: a translucent vertical gradient, lighter at the top like lit glass.
    top = (min(255, tint[0] + 14), min(255, tint[1] + 16), min(255, tint[2] + 20), alpha)
    bot = (max(0, tint[0] - 10), max(0, tint[1] - 10), max(0, tint[2] - 8), min(255, alpha + 18))
    grad = _vgrad((w, h), top, bot)
    mask = _round_mask((w, h), radius)
    grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(grad, (0, 0))

    # Specular sheen: a bright soft band hugging the top third, clipped to the rounded top.
    sheen_h = max(8, h // 3)
    sheen = _vgrad((w, sheen_h), (255, 255, 255, 42), (255, 255, 255, 0))
    smask = pygame.Surface((w, sheen_h), pygame.SRCALPHA)
    pygame.draw.rect(smask, (255, 255, 255, 255), smask.get_rect(),
                     border_top_left_radius=radius, border_top_right_radius=radius)
    sheen.blit(smask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(sheen, (0, 0))

    # Hairline border: a bright inner top edge fading to a dark bottom edge = glass thickness.
    border = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(border, (255, 255, 255, 36), border.get_rect(), 1, border_radius=radius)
    surf.blit(border, (0, 0))
    if accent is not None:
        line = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(line, (*accent, 150), line.get_rect(), 2, border_radius=radius)
        surf.blit(line, (0, 0))
        if glow and w > radius * 2 + 4:
            # A faint lit accent along the straight part of the top edge.
            bar = pygame.Surface((w - radius * 2, 2), pygame.SRCALPHA)
            bar.fill((*accent, 120))
            surf.blit(bar, (radius, 1))

    return surf


def panel(screen: pygame.Surface, rect: pygame.Rect, *, radius: int = _RADIUS,
          tint: Color = GL_GLASS, alpha: int = 44, accent: Optional[Color] = None,
          glow: bool = False, shadow: bool = True):
    """Draw a frosted-glass panel. Cached by (size, style) so repeats are free."""
    rect = pygame.Rect(rect)
    if rect.width <= 0 or rect.height <= 0:
        return
    if shadow:
        _drop_shadow(screen, rect, radius)
    key = (rect.width, rect.height, radius, tint, alpha, accent, glow)
    surf = _panel_cache.get(key)
    if surf is None:
        surf = _make_panel(rect.width, rect.height, radius, tint, alpha, accent, glow)
        _panel_cache[key] = surf
    screen.blit(surf, rect.topleft)


def _drop_shadow(screen, rect: pygame.Rect, radius: int):
    pad = 18
    key = (rect.width, rect.height, radius)
    sh = _shadow_cache.get(key)
    if sh is None:
        sw, shh = rect.width + pad * 2, rect.height + pad * 2
        sh = pygame.Surface((sw, shh), pygame.SRCALPHA)
        for i in range(pad, 0, -2):
            a = int(60 * (1 - i / pad) ** 2)
            r = pygame.Rect(pad - i, pad - i + 4, rect.width + i * 2, rect.height + i * 2)
            pygame.draw.rect(sh, (0, 0, 0, a), r, border_radius=radius + i)
        _shadow_cache[key] = sh
    screen.blit(sh, (rect.x - pad, rect.y - pad))


def vignette(screen: pygame.Surface, strength: int = 150):
    """A soft darkening at the edges - sits over the arena behind a modal."""
    w, h = screen.get_size()
    key = (w, h)
    v = _vignette_cache.get(key)
    if v is None:
        v = pygame.Surface((w, h), pygame.SRCALPHA)
        v.fill((4, 6, 11, 255))
        _radial(v, (w // 2, h // 2), int(max(w, h) * 0.62),
                (0, 0, 0, 0), (0, 0, 0, 0))
        # Clear an elliptical centre so the middle stays readable.
        clear = pygame.Surface((w, h), pygame.SRCALPHA)
        _radial(clear, (w // 2, h // 2), int(max(w, h) * 0.66),
                (0, 0, 0, 255), (0, 0, 0, 0))
        v.blit(clear, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        _vignette_cache[key] = v
    tmp = v.copy()
    tmp.set_alpha(strength)
    screen.blit(tmp, (0, 0))


def scrim(screen: pygame.Surface, alpha: int = 150):
    """A flat dimming layer behind modals/pause - cheaper than the vignette."""
    w, h = screen.get_size()
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill((5, 7, 12, alpha))
    screen.blit(s, (0, 0))


def accent_rule(screen: pygame.Surface, cx: int, y: int, half_w: int,
                c0: Color = GL_ACCENT, c1: Color = GL_ACCENT_3):
    """A thin horizontal gradient divider, bright in the middle, fading at the ends."""
    w = half_w * 2
    line = pygame.Surface((w, 3), pygame.SRCALPHA)
    for x in range(w):
        t = x / max(1, w - 1)
        edge = 1.0 - abs(t - 0.5) * 2.0   # 0 at ends, 1 in middle
        col = lerp_color(c0, c1, t)
        line.set_at((x, 1), (*col, int(210 * edge)))
        line.set_at((x, 0), (*col, int(90 * edge)))
        line.set_at((x, 2), (*col, int(90 * edge)))
    screen.blit(line, (cx - half_w, y))


_text_cache: Dict[tuple, pygame.Surface] = {}
_TEXT_CACHE_MAX = 1200


def _render(s: str, size: int, color, bold: bool) -> pygame.Surface:
    """Rendered text, cached: HUD numbers and labels repeat every frame."""
    key = (s, size, tuple(color[:3]), bold)
    img = _text_cache.get(key)
    if img is None:
        font = get_font(size)
        font.set_bold(bold)
        img = font.render(s, True, color[:3])
        font.set_bold(False)
        if len(_text_cache) >= _TEXT_CACHE_MAX:
            _text_cache.clear()
        _text_cache[key] = img
    return img


def text(screen, s: str, size: int, pos, color=GL_TEXT, *, align="left",
         bold=False, alpha=255, glow=False):
    """Draw text via the shared font cache. See ``_place`` for the align modes."""
    img = _render(s, size, color, bold)
    if glow:
        gr = img.get_rect()
        _place(gr, pos, align)
        g = img.copy()
        g.set_alpha(int(70 * alpha / 255))
        for off in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            screen.blit(g, (gr.x + off[0], gr.y + off[1]))
    if alpha < 255:
        img = img.copy()
        img.set_alpha(alpha)
    r = img.get_rect()
    _place(r, pos, align)
    screen.blit(img, r)
    return r


def _place(rect: pygame.Rect, pos, align: str):
    """left/right/center anchor the top edge (center anchors the middle);
    midleft/midright anchor the vertical middle."""
    if align == "center":
        rect.center = pos
    elif align == "right":
        rect.topright = pos
    elif align == "midright":
        rect.midright = pos
    elif align == "midleft":
        rect.midleft = pos
    else:
        rect.topleft = pos


def clip_text(s: str, size: int, max_w: int, bold=False) -> str:
    font = get_font(size)
    font.set_bold(bold)
    if font.size(s)[0] <= max_w:
        font.set_bold(False)
        return s
    ell = "…"
    while s and font.size(s + ell)[0] > max_w:
        s = s[:-1]
    font.set_bold(False)
    return s + ell


def progress_bar(screen, rect: pygame.Rect, frac: float, *, color=GL_ACCENT,
                 track=(255, 255, 255, 26), glow=True, radius: Optional[int] = None):
    """A rounded progress/fill bar with a soft lit fill."""
    frac = max(0.0, min(1.0, frac))
    r = radius if radius is not None else rect.height // 2
    tkey = ("track", rect.width, rect.height, tuple(track), r)
    track_s = _bar_cache.get(tkey)
    if track_s is None:
        track_s = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(track_s, track, track_s.get_rect(), border_radius=r)
        pygame.draw.rect(track_s, (255, 255, 255, 30), track_s.get_rect(), 1, border_radius=r)
        _bar_cache[tkey] = track_s
    screen.blit(track_s, rect.topleft)
    if frac <= 0:
        return
    fw = max(rect.height, int(rect.width * frac))
    fkey = ("fill", fw, rect.height, tuple(color[:3]), r, glow)
    fill = _bar_cache.get(fkey)
    if fill is None:
        fill = pygame.Surface((fw, rect.height), pygame.SRCALPHA)
        c0 = lerp_color(color, (255, 255, 255), 0.25)
        grad = _vgrad((fw, rect.height), (*c0, 255), (*color[:3], 255))
        grad.blit(_round_mask((fw, rect.height), r), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        fill.blit(grad, (0, 0))
        if glow:
            sheen = pygame.Surface((fw, max(2, rect.height // 2)), pygame.SRCALPHA)
            pygame.draw.rect(sheen, (255, 255, 255, 60), sheen.get_rect(),
                             border_top_left_radius=r, border_top_right_radius=r)
            fill.blit(sheen, (0, 0))
        if len(_bar_cache) > 1500:
            _bar_cache.clear()
        _bar_cache[fkey] = fill
    screen.blit(fill, rect.topleft)


def badge(screen, rect: pygame.Rect, label: str, *, color=GL_ACCENT, filled=True,
          size=18):
    """A small pill badge with centred text."""
    r = rect.height // 2
    key = ("badge", rect.width, rect.height, tuple(color[:3]), filled)
    cached = _bar_cache.get(key)
    if cached is not None:
        screen.blit(cached, rect.topleft)
        text(screen, label, size, rect.center, (12, 18, 24) if filled else color, align="center", bold=True)
        return
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    if filled:
        grad = _vgrad(rect.size, (*lerp_color(color, (255, 255, 255), 0.2), 235),
                      (*color, 235))
        m = _round_mask(rect.size, r)
        grad.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        s.blit(grad, (0, 0))
        txt_col = (12, 18, 24)
    else:
        pygame.draw.rect(s, (*color, 40), s.get_rect(), border_radius=r)
        pygame.draw.rect(s, (*color, 220), s.get_rect(), 1, border_radius=r)
        txt_col = color
    _bar_cache[key] = s
    screen.blit(s, rect.topleft)
    text(screen, label, size, rect.center, txt_col, align="center", bold=True)


def frost_backdrop(screen: pygame.Surface, factor: int = 6, dim: int = 120):
    """Blur whatever is on screen right now (down/upscale) and dim it - a real frosted backdrop
    for modal screens, so busy gameplay never bleeds through the cards drawn on top."""
    w, h = screen.get_size()
    small = pygame.transform.smoothscale(screen, (max(1, w // factor), max(1, h // factor)))
    small = pygame.transform.smoothscale(small, (max(1, w // (factor // 2 or 1)), max(1, h // (factor // 2 or 1))))
    screen.blit(pygame.transform.smoothscale(small, (w, h)), (0, 0))
    scrim(screen, dim)


def icon_star(screen, center, r: int, color):
    """A filled five-point star (the default font has no star glyph)."""
    cx, cy = center
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
    pygame.draw.polygon(screen, color, pts)


def icon_chevron(screen, center, size: int, color, width: int = 2):
    """A right-pointing chevron (stand-in for the missing arrow glyphs)."""
    cx, cy = center
    pygame.draw.lines(screen, color, False,
                      [(cx - size // 2, cy - size), (cx + size // 2, cy), (cx - size // 2, cy + size)], width)


def icon_close(screen, rect: pygame.Rect, color, width: int = 3):
    pad = max(4, rect.w // 3)
    pygame.draw.line(screen, color, (rect.x + pad, rect.y + pad), (rect.right - pad - 1, rect.bottom - pad - 1), width)
    pygame.draw.line(screen, color, (rect.right - pad - 1, rect.y + pad), (rect.x + pad, rect.bottom - pad - 1), width)


def fit_size(s: str, max_size: int, max_w: int, min_size: int = 12, bold: bool = False) -> int:
    """Largest font size (down to min_size) at which ``s`` fits in ``max_w`` pixels."""
    size = max_size
    while size > min_size:
        font = get_font(size)
        font.set_bold(bold)
        w = font.size(s)[0]
        font.set_bold(False)
        if w <= max_w:
            break
        size -= 1
    return size
