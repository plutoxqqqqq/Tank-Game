"""Minigame list screen (liquid-glass style)."""
from __future__ import annotations

import pygame

from tankgame.config import *
from tankgame.util import *
from tankgame.ui import glass
from tankgame.ui.widgets import cached_button


def _mouse_state(events):
    return pygame.mouse.get_pos(), any(
        e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)


class MinigameScreenMixin:

    def draw_minigames(self, events):
        glass.background(self.screen)
        cx = WIDTH // 2
        glass.text(self.screen, "MINIGAMES", 58, (cx, 40), glass.GL_TEXT, align="center", bold=True, glow=True)
        glass.text(self.screen, "Short challenges — the further you get, the more coins", 20,
                   (cx, 80), glass.GL_TEXT_DIM, align="center")
        glass.text(self.screen, f"{self.save.coins:,} coins", 22, (WIDTH - 44, 30),
                   glass.GL_COIN, align="midright", bold=True)

        mouse_pos, mouse_down = _mouse_state(events)
        for rect, mg in self.mg_play_buttons:
            hover = rect.collidepoint(mouse_pos)
            clears = int(self.save.minigame_clears.get(mg.id, 0))
            best = float(self.save.minigame_best.get(mg.id, 0.0))
            glass.panel(self.screen, rect, radius=14, alpha=44 if hover else 30,
                        accent=mg.accent if hover else None, shadow=hover)
            bar = pygame.Surface((5, rect.h - 16), pygame.SRCALPHA)
            bar.fill((*mg.accent, 230))
            self.screen.blit(bar, (rect.x + 10, rect.y + 8))

            compact = rect.h < 50
            glass.text(self.screen, mg.name, 24 if not compact else 20,
                       (rect.x + 26, rect.y + (4 if compact else 8)), glass.GL_TEXT, bold=True)
            glass.text(self.screen, glass.clip_text(mg.desc, 18, rect.w - 420), 18,
                       (rect.x + 26, rect.y + (24 if compact else 32)), glass.GL_TEXT_DIM)

            pips_x = rect.right - 330
            for i in range(5):
                col = mg.accent if i < mg.difficulty else (70, 78, 96)
                pygame.draw.circle(self.screen, col, (pips_x + i * 14, rect.centery - 6), 4)
            glass.text(self.screen, f"DIFF {mg.difficulty}/5", 16,
                       (pips_x - 4, rect.centery + 2), glass.GL_TEXT_FAINT)

            reward_txt = f"+{mg.reward}" + (f"  ·  x{clears}" if clears else "")
            glass.text(self.screen, reward_txt, 18, (rect.right - 128, rect.y + 10),
                       glass.GL_COIN, align="right", bold=True)
            if best > 0.0:
                glass.text(self.screen, f"best {int(best * 100)}%", 16,
                           (rect.right - 128, rect.bottom - 24), glass.GL_TEXT_FAINT, align="right")

            btn = pygame.Rect(rect.right - 104, rect.centery - (rect.h - 16) // 2, 88, rect.h - 16)
            b = cached_button(("minigame", mg.id), btn, "Play", lambda mid=mg.id: self.start_minigame(mid), kind="primary")
            b.update(1 / 60, mouse_pos, mouse_down, events)
            b.draw(self.screen, self.font_shop_small)

        if self.minigame_result is not None:
            res = self.minigame_result
            band = getattr(self, "mg_result_rect", None) or pygame.Rect(cx - 330, 104, 660, 48)
            ok = bool(res["cleared"])
            col = glass.GL_GOOD if ok else glass.GL_WARN
            glass.panel(self.screen, band, radius=14, alpha=40, accent=col, shadow=True)
            glass.text(self.screen, f"{'CLEARED' if ok else 'FINISHED'}  —  {res['name']}", 20,
                       (band.x + 18, band.centery), col, align="midleft", bold=True)
            glass.text(self.screen, f"+{res['coins']} coins  ·  {int(float(res['progress']) * 100)}% of the objective   ×",
                       17, (band.right - 18, band.centery), glass.GL_COIN, align="midright")
            if band.collidepoint(mouse_pos) and mouse_down:
                self.minigame_result = None

        self.mg_back_btn.update(1 / 60, mouse_pos, mouse_down, events)
        self.mg_back_btn.draw(self.screen, self.font_med)
        glass.text(self.screen, "ESC or Back returns to the menu", 18, (cx, HEIGHT - 24),
                   glass.GL_TEXT_FAINT, align="center")
