"""Game-over screen (liquid-glass style)."""
from __future__ import annotations

import pygame

from tankgame.config import *
from tankgame.util import *
from tankgame.ui import glass


class GameOverScreenMixin:

    def draw_gameover(self, events):
        self.award_coins_if_needed()
        self.record_leaderboard_if_needed()
        for e in events:
            if (e.type == pygame.KEYDOWN and e.key in (pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER)
                    and not (getattr(e, "mod", 0) & pygame.KMOD_ALT)):
                self.restart_run()
                return
        self.draw_background()
        self.draw_obstacles()
        self.draw_entities()
        glass.frost_backdrop(self.screen, dim=170)
        cx = WIDTH // 2

        glass.text(self.screen, "GAME OVER", 76, (cx, 100), glass.GL_ACCENT_3, align="center", bold=True, glow=True)
        if self.new_best:
            badge = pygame.Rect(cx - 120, 152, 240, 36)
            glass.badge(self.screen, badge, "NEW BEST SCORE", color=glass.GL_GOOD, size=20)

        panel_w = min(680, WIDTH - 40)
        panel = pygame.Rect(cx - panel_w // 2, 202, panel_w, 200)
        glass.panel(self.screen, panel, alpha=92, accent=glass.GL_ACCENT, glow=True)
        stats = (
            ("SCORE", f"{self.player.score:,}", glass.GL_TEXT),
            ("TIME", f"{int(self.survival_time)}s", glass.GL_TEXT),
            ("WAVE", str(self.wave), glass.GL_ACCENT),
            ("LEVEL", str(self.player.level), glass.GL_ACCENT),
            ("KILLS", str(int(self.run_stats["kills"])), glass.GL_TEXT),
            ("DAMAGE", f"{int(self.run_stats['damage']):,}", glass.GL_TEXT),
            ("ACCURACY", f"{self.accuracy():.0f}%", glass.GL_TEXT),
            ("COINS", f"+{self.last_run_coins_earned}", glass.GL_COIN),
        )
        col_w = (panel.w - 48) // 4
        for i, (label, value, col) in enumerate(stats):
            sx = panel.x + 24 + (i % 4) * col_w
            sy = panel.y + 26 + (i // 4) * 88
            glass.text(self.screen, label, 18, (sx, sy), glass.GL_TEXT_FAINT, bold=True)
            glass.text(self.screen, value, 34, (sx, sy + 24), col, bold=True)

        if self.run_bonus_coins > 0:
            glass.text(self.screen, f"includes +{self.run_bonus_coins} banked boss + twist bonus",
                       18, (panel.centerx, panel.bottom + 8), glass.GL_COIN, align="center")

        mouse_pos = pygame.mouse.get_pos()
        mouse_down = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)
        for b in self.gameover_buttons:
            b.update(1 / 60, mouse_pos, mouse_down, events)
            b.draw(self.screen, self.font_med)

        glass.text(self.screen, "Press R to restart   ·   ESC for the menu", 18,
                   (cx, HEIGHT - 24), glass.GL_TEXT_FAINT, align="center")
