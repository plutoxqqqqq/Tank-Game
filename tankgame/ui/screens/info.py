"""Information screens: leaderboard and challenges (liquid-glass style)."""
from __future__ import annotations

import pygame

from tankgame.config import *
from tankgame.util import *
from tankgame.ui import glass


def _mouse_state(events):
    return pygame.mouse.get_pos(), any(
        e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)


class InfoScreenMixin:

    def draw_leaderboard(self, events):
        glass.background(self.screen)
        cx = WIDTH // 2
        glass.text(self.screen, "LEADERBOARD", 64, (cx, 66), glass.GL_TEXT, align="center", bold=True, glow=True)
        glass.text(self.screen, "Your best runs by score", 22, (cx, 112), glass.GL_TEXT_DIM, align="center")

        box_w = min(WIDTH - 80, 820)
        box = pygame.Rect(WIDTH // 2 - box_w // 2, 158, box_w, HEIGHT - 244)
        glass.panel(self.screen, box, accent=glass.GL_ACCENT, glow=True)

        inner = box.w - 120
        cols = {
            "rank": box.x + 26,
            "score": box.x + 82,
            "time": int(box.x + 82 + inner * 0.34),
            "wave": int(box.x + 82 + inner * 0.60),
            "level": int(box.x + 82 + inner * 0.82),
        }
        head_y = box.y + 18
        for label, key in (("RANK", "rank"), ("SCORE", "score"), ("TIME", "time"),
                           ("WAVE", "wave"), ("LEVEL", "level")):
            glass.text(self.screen, label, 18, (cols[key], head_y), glass.GL_TEXT_FAINT, bold=True)
        glass.accent_rule(self.screen, box.centerx, head_y + 26, box.w // 2 - 20)

        entries = list(self.save.leaderboard)
        if not entries:
            glass.text(self.screen, "No runs yet — play a game to set a score.",
                       28, box.center, glass.GL_TEXT_DIM, align="center")
        else:
            row_y = head_y + 40
            row_h = 32
            gap = 6
            max_rows = max(1, (box.bottom - 16 - row_y) // (row_h + gap))
            shown = entries[:max_rows]
            for idx, entry in enumerate(shown, start=1):
                row = pygame.Rect(box.x + 14, row_y, box.w - 28, row_h)
                accent = glass.GL_GOLD if idx == 1 else (glass.GL_TEXT_DIM if idx <= 3 else None)
                glass.panel(self.screen, row, radius=10,
                            alpha=40 if idx == 1 else 26,
                            accent=accent if idx <= 3 else None, shadow=False)
                badge = pygame.Rect(row.x + 8, row.y + 4, 40, row_h - 8)
                glass.badge(self.screen, badge, str(idx),
                            color=glass.GL_GOLD if idx == 1 else glass.GL_ACCENT,
                            filled=idx == 1, size=16)
                col_c = glass.GL_TEXT if idx != 1 else glass.GL_GOLD
                glass.text(self.screen, f"{entry['score']:,}", 20, (cols['score'], row.y + 6), col_c, bold=True)
                glass.text(self.screen, f"{entry['time']}s", 20, (cols['time'], row.y + 6), glass.GL_TEXT_DIM)
                glass.text(self.screen, f"{entry['wave']}", 20, (cols['wave'], row.y + 6), glass.GL_TEXT_DIM)
                glass.text(self.screen, f"{entry['level']}", 20, (cols['level'], row.y + 6), glass.GL_TEXT_DIM)
                row_y += row_h + gap
            if len(entries) > len(shown):
                glass.text(self.screen, f"+{len(entries) - len(shown)} older run(s) hidden",
                           18, (box.centerx, box.bottom - 24), glass.GL_TEXT_FAINT, align="center")

        mouse_pos, mouse_down = _mouse_state(events)
        if self.leaderboard_back_btn:
            self.leaderboard_back_btn.update(1 / 60, mouse_pos, mouse_down, events)
            self.leaderboard_back_btn.draw(self.screen, self.font_med)

    def draw_challenges(self, events):
        glass.background(self.screen)
        self.refresh_challenges()
        cx = WIDTH // 2
        glass.text(self.screen, "CHALLENGES", 64, (cx, 60), glass.GL_TEXT, align="center", bold=True, glow=True)
        subtitle = ("Daily goals reset automatically" if self.challenges_view == "daily"
                    else "Weekly goals reset automatically")
        glass.text(self.screen, subtitle, 22, (cx, 106), glass.GL_TEXT_DIM, align="center")

        mouse_pos, mouse_down = _mouse_state(events)
        tab_y = 138
        tab_h = self.challenge_tabs[0].rect.height if self.challenge_tabs else 40
        for tab in self.challenge_tabs:
            tab.rect.y = tab_y
            tab.update(mouse_pos, mouse_down)
            tab.draw(self.screen, self.font_shop_item, active=(tab.tab_id == self.challenges_view))

        box_y = tab_y + tab_h + 18
        box_w = min(WIDTH - 80, 860)
        box = pygame.Rect(WIDTH // 2 - box_w // 2, box_y, box_w, HEIGHT - box_y - 104)
        glass.panel(self.screen, box, accent=glass.GL_ACCENT, glow=True)

        reset_label = f"Resets in {self.time_until_reset(self.challenges_view)}"
        header = "DAILY" if self.challenges_view == "daily" else "WEEKLY"
        glass.text(self.screen, f"{header}   ·   {reset_label}", 22,
                   (box.x + 22, box.y + 14), glass.GL_TEXT, bold=True)

        list_rect = pygame.Rect(box.x + 18, box.y + 50, box.w - 36, box.h - 66)
        items = (list(self.save.daily_challenges.get("items", []))
                 if self.challenges_view == "daily"
                 else list(self.save.weekly_challenges.get("items", [])))
        if not items:
            glass.text(self.screen, "No challenges available.", 26, list_rect.center,
                       glass.GL_TEXT_DIM, align="center")
        else:
            gap = 12
            row_h = min(76, (list_rect.h - gap * (len(items) - 1)) // max(1, len(items)))
            y = list_rect.y
            for item in items:
                row = pygame.Rect(list_rect.x, y, list_rect.w, row_h)
                y += row_h + gap
                progress = int(item.get("progress", 0))
                target = int(item.get("target", 1))
                claimed = bool(item.get("claimed", False))
                complete = progress >= target
                accent = glass.GL_GOOD if claimed else (glass.GL_ACCENT if complete else None)
                glass.panel(self.screen, row, radius=14, alpha=34, accent=accent, shadow=False)

                glass.text(self.screen, item.get("name", "Challenge"), 24,
                           (row.x + 16, row.y + 10), glass.GL_TEXT, bold=True)
                glass.text(self.screen, item.get("desc", ""), 20,
                           (row.x + 16, row.y + 36), glass.GL_TEXT_DIM)

                reward_txt = f"{int(item.get('reward', 0))} coins"
                status = "CLAIMED" if claimed else ("COMPLETE" if complete else f"{min(progress, target)}/{target}")
                status_col = glass.GL_GOOD if claimed else (glass.GL_ACCENT if complete else glass.GL_TEXT_DIM)
                glass.text(self.screen, reward_txt, 18, (row.right - 18, row.y + 14),
                           glass.GL_COIN, align="right", bold=True)
                glass.text(self.screen, status, 18, (row.right - 18, row.y + 36),
                           status_col, align="right", bold=True)

                bar = pygame.Rect(row.x + 16, row.bottom - 16, row.w - 32, 7)
                glass.progress_bar(self.screen, bar, clamp(progress / max(1, target), 0, 1),
                                   color=glass.GL_GOOD if claimed else glass.GL_ACCENT)

        if self.challenges_back_btn:
            self.challenges_back_btn.update(1 / 60, mouse_pos, mouse_down, events)
            self.challenges_back_btn.draw(self.screen, self.font_med)
