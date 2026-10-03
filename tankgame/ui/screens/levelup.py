"""Level-up card picker (liquid-glass style)."""
from __future__ import annotations

import pygame
from pygame.math import Vector2

from tankgame.config import *
from tankgame.util import *
from tankgame.ui import glass
from tankgame.data.upgrades import UPGRADES_BY_ID


class LevelUpScreenMixin:

    def draw_levelup(self, events):
        self.draw_background()
        self.draw_obstacles()
        self.draw_entities()
        self.draw_minigame_view()
        glass.frost_backdrop(self.screen, dim=150)

        cx = WIDTH // 2
        glass.text(self.screen, "LEVEL UP", 72, (cx, 70), glass.GL_ACCENT, align="center", bold=True, glow=True)
        queued = max(0, self.pending_levelups - 1)
        subtitle = "Choose an upgrade" if queued == 0 else f"Choose an upgrade  ·  {queued} more queued"
        glass.text(self.screen, subtitle, 22, (cx, 116), glass.GL_TEXT_DIM, align="center")

        mouse_pos = pygame.mouse.get_pos()
        mouse_down = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)

        pick_keys = {pygame.K_1: 0, pygame.K_KP1: 0, pygame.K_2: 1, pygame.K_KP2: 1,
                     pygame.K_3: 2, pygame.K_KP3: 2}
        for e in events:
            if e.type == pygame.KEYDOWN and e.key in pick_keys:
                idx = pick_keys[e.key]
                if idx < len(self.level_cards):
                    self.pick_upgrade(self.level_cards[idx][1])
                    return

        for idx, (rect, up) in enumerate(self.level_cards):
            hover = rect.collidepoint(mouse_pos)
            is_ultra = up.ultra
            accent = glass.GL_GOLD if is_ultra else (glass.GL_ACCENT if hover else None)
            tint = (92, 78, 30) if is_ultra else (120, 138, 172)
            glass.panel(self.screen, rect, radius=16, tint=tint,
                        alpha=96 if (is_ultra or hover) else 72,
                        accent=accent, glow=is_ultra or hover, shadow=True)

            tag = pygame.Rect(rect.right - 168, rect.centery - 24, 144, 48)
            glass.badge(self.screen, tag, f"{idx + 1}. {up.tag}",
                        color=glass.GL_GOLD if is_ultra else glass.GL_ACCENT,
                        filled=is_ultra, size=18)

            name_col = glass.GL_GOLD if is_ultra else glass.GL_TEXT
            glass.text(self.screen, up.name, 28, (rect.x + 20, rect.y + 16), name_col, bold=True)
            glass.text(self.screen, glass.clip_text(up.desc, 20, rect.w - 210), 20,
                       (rect.x + 20, rect.y + 48), glass.lerp_color(glass.GL_TEXT_DIM, glass.GL_GOLD, 0.4) if is_ultra else glass.GL_TEXT_DIM)

            note = up.bonus_note_for(self.player.weapon_id)
            if is_ultra:
                glass.icon_star(self.screen, (rect.x + 27, rect.bottom - 16), 8, glass.GL_GOLD)
                glass.text(self.screen, "ULTRA — exclusive to your tank", 18,
                           (rect.x + 40, rect.bottom - 24), glass.GL_GOLD, bold=True)
            elif note:
                glass.icon_chevron(self.screen, (rect.x + 25, rect.bottom - 16), 5, glass.GL_WARN)
                glass.text(self.screen, glass.clip_text(note, 18, rect.w - 230), 18,
                           (rect.x + 38, rect.bottom - 24), glass.GL_WARN)

            if hover and mouse_down:
                self.pick_upgrade(up)
                return
