"""Menu screens: main menu, settings and controls (liquid-glass style)."""
from __future__ import annotations

import math
import time

import pygame
from pygame.math import Vector2

from tankgame.config import *
from tankgame.util import *
from tankgame.ui import glass
from tankgame.data.weapons import WEAPONS
from tankgame.ui.widgets import cached_button


def _mouse_state(events):
    return pygame.mouse.get_pos(), any(
        e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)


class MenuScreenMixin:

    def draw_menu(self, events):
        glass.background(self.screen)
        cx = WIDTH // 2
        t = time.time()
        self.refresh_challenges()

        # Title with a soft animated glow and a gradient rule beneath it.
        glass.text(self.screen, "TANK GAME", 78, (cx, 70), glass.GL_TEXT,
                   align="center", bold=True, glow=True)
        glass.text(self.screen, "S U R V I V A L", 26, (cx, 118),
                   glass.lerp_color(glass.GL_ACCENT, glass.GL_ACCENT_2, glass.pulse(0.3)),
                   align="center", bold=True)
        glass.accent_rule(self.screen, cx, 140, 330)

        # Status card: coins, selected tank, best score, challenge progress.
        card_w = min(768, WIDTH - 60)
        panel = pygame.Rect(cx - card_w // 2, 156, card_w, 70)
        glass.panel(self.screen, panel, accent=glass.GL_ACCENT, glow=True)
        wdef = WEAPONS.get(self.save.selected_weapon, WEAPONS["pistol"])
        glass.text(self.screen, "COINS", 16, (panel.x + 22, panel.y + 12), glass.GL_TEXT_FAINT, bold=True)
        glass.text(self.screen, f"{self.save.coins:,}", 30, (panel.x + 22, panel.y + 30), glass.GL_COIN, bold=True)
        glass.text(self.screen, "SELECTED TANK", 16, (panel.x + int(card_w * 0.30), panel.y + 12), glass.GL_TEXT_FAINT, bold=True)
        glass.text(self.screen, wdef.name, 30, (panel.x + int(card_w * 0.30), panel.y + 30), glass.GL_ACCENT, bold=True)

        daily = list(self.save.daily_challenges.get("items", []) or [])
        weekly = list(self.save.weekly_challenges.get("items", []) or [])
        daily_done = sum(1 for i in daily if i.get("claimed"))
        weekly_done = sum(1 for i in weekly if i.get("claimed"))
        glass.text(self.screen, f"BEST  {self.save.best_score():,}", 18,
                   (panel.right - 22, panel.y + 14), glass.GL_TEXT, align="right", bold=True)
        glass.text(self.screen, f"DAILY {daily_done}/{len(daily)}    WEEKLY {weekly_done}/{len(weekly)}",
                   16, (panel.right - 22, panel.y + 42), glass.GL_TEXT_DIM, align="right")

        mouse_pos, mouse_down = _mouse_state(events)
        for b in self.menu_buttons:
            b.update(1 / 60, mouse_pos, mouse_down, events)
            b.draw(self.screen, self.font_small if b.small else self.font_med)

        self.menu_quit_btn.update(1 / 60, mouse_pos, mouse_down, events)
        self.menu_quit_btn.draw(self.screen, self.font_med)

        # Footer controls hint on a glass strip.
        strip_w = min(720, WIDTH - 60)
        strip = pygame.Rect(cx - strip_w // 2, HEIGHT - 70, strip_w, 50)
        glass.panel(self.screen, strip, radius=16, alpha=32, shadow=False)
        glass.text(self.screen, "WASD move   ·   Mouse aim   ·   Hold LMB fire   ·   Space dash",
                   17, (cx, strip.y + 14), glass.GL_TEXT_DIM, align="center")
        glass.text(self.screen, "F auto-fire   ·   ESC pause   ·   Enter start run",
                   17, (cx, strip.y + 31), glass.GL_TEXT_FAINT, align="center")

    def draw_settings(self, events):
        glass.background(self.screen)
        cx = WIDTH // 2
        glass.text(self.screen, "SETTINGS", 64, (cx, 70), glass.GL_TEXT, align="center", bold=True, glow=True)
        glass.text(self.screen, "Tune how your runs feel", 22, (cx, 116), glass.GL_TEXT_DIM, align="center")

        box_w = min(WIDTH - 120, 860)
        box = pygame.Rect(WIDTH // 2 - box_w // 2, 156, box_w, 24 + 86 + 22 + 48 + 20 + 104 + 20)
        glass.panel(self.screen, box, accent=glass.GL_ACCENT, glow=True)

        mouse_pos, mouse_down = _mouse_state(events)
        options = [
            ("Fullscreen", "fullscreen"),
            ("Audio", "audio"),
            ("Screen Shake", "shake"),
            ("Damage Numbers", "damage_numbers"),
        ]
        opt_gap = 14
        usable = box.w - 48
        opt_w = (usable - (len(options) - 1) * opt_gap) // len(options)
        opt_h = 86
        opt_y = box.y + 24
        opt_x = box.x + 24

        for i, (label, key) in enumerate(options):
            rect = pygame.Rect(opt_x + i * (opt_w + opt_gap), opt_y, opt_w, opt_h)
            on = bool(self.save.settings.get(key, True))
            hot = rect.collidepoint(mouse_pos)
            glass.panel(self.screen, rect, radius=16, alpha=46 if hot else 32,
                        accent=glass.GL_ACCENT if hot else None, shadow=False)
            size = glass.fit_size(label, 20, rect.w - 16, 13, bold=True)
            glass.text(self.screen, label, size, (rect.centerx, rect.y + 20),
                       glass.GL_TEXT, align="center", bold=True)
            sw = pygame.Rect(rect.centerx - 34, rect.y + 44, 68, 30)
            self._glass_toggle(sw, on)
            if hot and mouse_down:
                if key == "fullscreen":
                    self.toggle_fullscreen()
                else:
                    self.toggle_setting(key)

        rby = opt_y + opt_h + 22
        glass.text(self.screen, "RESET", 20, (box.x + 26, rby + 25), glass.GL_TEXT_DIM, align="midleft", bold=True)
        reset_gap = 14
        reset_w = min(250, (box.w - 140 - reset_gap) // 2)
        reset_h = 48
        reset_x = box.right - 24 - (reset_w * 2 + reset_gap)
        reset_settings_btn = cached_button("reset_settings", pygame.Rect(reset_x, rby, reset_w, reset_h),
                                           "Restore Defaults", self.reset_settings)
        reset_cosmetics_btn = cached_button("reset_cosmetics", pygame.Rect(reset_x + reset_w + reset_gap, rby, reset_w, reset_h),
                                            "Reset Cosmetics", self.reset_cosmetics)
        for btn in (reset_settings_btn, reset_cosmetics_btn):
            btn.update(1 / 60, mouse_pos, mouse_down, events)
            btn.draw(self.screen, self.font_shop_small)

        tips = [
            "Saves upgrade themselves — new tanks and cosmetics sync in automatically.",
            "Turn damage numbers off for a cleaner screen on spray tanks.",
            "Turn screen shake off if the camera motion bothers you.",
        ]
        hint_y = rby + reset_h + 20
        hint_box = pygame.Rect(box.x + 24, hint_y, box.w - 48, box.bottom - 20 - hint_y)
        glass.panel(self.screen, hint_box, radius=14, alpha=24, shadow=False)
        line_h = max(20, min(28, (hint_box.h - 16) // len(tips)))
        ty = hint_box.y + (hint_box.h - line_h * len(tips)) // 2
        for tip in tips:
            glass.text(self.screen, "•  " + glass.clip_text(tip, 19, hint_box.w - 44), 19,
                       (hint_box.x + 18, ty + line_h // 2), glass.GL_TEXT_DIM, align="midleft")
            ty += line_h

        if self.settings_back_btn:
            self.settings_back_btn.update(1 / 60, mouse_pos, mouse_down, events)
            self.settings_back_btn.draw(self.screen, self.font_med)

    def _glass_toggle(self, rect: pygame.Rect, on: bool):
        rad = rect.height // 2
        col = glass.GL_GOOD if on else (90, 98, 118)
        track = pygame.Surface(rect.size, pygame.SRCALPHA)
        if on:
            grad = glass._vgrad(rect.size, (*glass.lerp_color(col, (255, 255, 255), 0.3), 235),
                                (*col, 235))
            m = glass._round_mask(rect.size, rad)
            grad.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            track.blit(grad, (0, 0))
        else:
            pygame.draw.rect(track, (*col, 90), track.get_rect(), border_radius=rad)
            pygame.draw.rect(track, (255, 255, 255, 30), track.get_rect(), 1, border_radius=rad)
        self.screen.blit(track, rect.topleft)
        knob_x = rect.right - rad if on else rect.x + rad
        pygame.draw.circle(self.screen, (250, 253, 255), (knob_x, rect.centery), rad - 4)
        pygame.draw.circle(self.screen, (0, 0, 0, 40), (knob_x, rect.centery), rad - 4, 1)

    def draw_controls(self, events):
        glass.background(self.screen)
        cx = WIDTH // 2
        glass.text(self.screen, "CONTROLS", 64, (cx, 70), glass.GL_TEXT, align="center", bold=True, glow=True)
        glass.text(self.screen, "Everything you need to survive", 22, (cx, 116), glass.GL_TEXT_DIM, align="center")

        box_w = min(WIDTH - 120, 640)
        box = pygame.Rect(WIDTH // 2 - box_w // 2, 168, box_w, HEIGHT - 288)
        glass.panel(self.screen, box, accent=glass.GL_ACCENT, glow=True)

        lines = [
            ("WASD", "Drive your tank"),
            ("Mouse", "Aim the turret"),
            ("Left Mouse", "Fire — hold for full-auto"),
            ("F", "Toggle auto-fire"),
            ("Space", "Dash — briefly invulnerable"),
            ("ESC", "Pause / step back a screen"),
            ("Enter", "Start a run from the menu"),
        ]
        row_h = (box.h - 40) // len(lines)
        y = box.y + 20
        for key, desc in lines:
            key_rect = pygame.Rect(box.x + 28, y + (row_h - 36) // 2, 160, 36)
            glass.panel(self.screen, key_rect, radius=10, alpha=40, accent=glass.GL_ACCENT, shadow=False)
            glass.text(self.screen, key, 20, key_rect.center, glass.GL_ACCENT, align="center", bold=True)
            glass.text(self.screen, desc, 22, (key_rect.right + 22, key_rect.centery),
                       glass.GL_TEXT_DIM, align="midleft")
            y += row_h

        mouse_pos, mouse_down = _mouse_state(events)
        if self.controls_back_btn:
            self.controls_back_btn.update(1 / 60, mouse_pos, mouse_down, events)
            self.controls_back_btn.draw(self.screen, self.font_med)
