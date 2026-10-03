"""Weapons screen (liquid-glass style): tank picker + mastery grid."""
from __future__ import annotations

import math
import traceback

import pygame

from tankgame.config import *
from tankgame.util import *
from tankgame.ui import glass
from tankgame.data.weapons import WEAPONS
from tankgame.data.traits import trait_of
from tankgame.data.mastery import MAX_MASTERY_LEVEL, mastery_requirements


def _mouse_state(events):
    return pygame.mouse.get_pos(), any(
        e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)


class WeaponsScreenMixin:

    def draw_weapons(self, events):
        glass.background(self.screen)
        cx = WIDTH // 2
        self.weapon_notice_timer = max(0.0, self.weapon_notice_timer - (1 / 60))

        glass.text(self.screen, "WEAPONS", 58, (cx, 44), glass.GL_TEXT, align="center", bold=True, glow=True)
        subtitle = ("Pick an unlocked tank — buy more in Shop › Weapons"
                    if self.weapons_view == "weapons"
                    else "Mastery tracks each tank's kills and runs over time")
        glass.text(self.screen, subtitle, 20, (cx, 84), glass.GL_TEXT_DIM, align="center")

        mouse_pos, mouse_down = _mouse_state(events)
        for tab in self.weapon_tabs:
            tab.update(mouse_pos, mouse_down)
            tab.draw(self.screen, self.font_shop_item, active=(tab.tab_id == self.weapons_view))

        box = pygame.Rect(70, 162, WIDTH - 140, HEIGHT - 258)
        glass.panel(self.screen, box, accent=glass.GL_ACCENT, glow=True)

        if self.weapons_view == "mastery":
            try:
                total_pages = self.draw_weapon_mastery(box, mouse_pos, mouse_down, events)
            except Exception:
                if not self.mastery_error_logged:
                    traceback.print_exc()
                    self.mastery_error_logged = True
                total_pages = 1
                glass.text(self.screen, "Mastery data unavailable.", 28, box.center,
                           glass.GL_TEXT_DIM, align="center")
        else:
            total_pages = self._draw_weapon_grid(box, mouse_pos, mouse_down)

        self.weapon_back_btn.update(1 / 60, mouse_pos, mouse_down, events)
        self.weapon_back_btn.draw(self.screen, self.font_med)
        self.weapon_prev_btn.update(1 / 60, mouse_pos, mouse_down, events)
        self.weapon_next_btn.update(1 / 60, mouse_pos, mouse_down, events)
        self.weapon_prev_btn.draw(self.screen, self.font_med)
        self.weapon_next_btn.draw(self.screen, self.font_med)

        mid_x = (self.weapon_prev_btn.rect.centerx + self.weapon_next_btn.rect.centerx) // 2
        glass.text(self.screen, f"Page {self.weapon_page + 1}/{total_pages}", 18,
                   (mid_x, self.weapon_prev_btn.rect.bottom + 8), glass.GL_TEXT_DIM, align="center")

        if self.weapon_notice_timer > 0 and self.weapon_notice_text:
            glass.text(self.screen, self.weapon_notice_text, 22, (cx, HEIGHT - 116),
                       glass.GL_WARN, align="center", bold=True)

    def _draw_weapon_grid(self, box, mouse_pos, mouse_down) -> int:
        cols = 3 if box.w >= 820 else 2
        rows = 3
        gap_x, gap_y, pad = 12, 12, 16
        card_w = (box.w - pad * 2 - gap_x * (cols - 1)) // cols
        card_h = (box.h - pad * 2 - gap_y * (rows - 1)) // rows
        per_page = cols * rows

        weapon_ids = list(WEAPONS.keys())
        total_pages = max(1, math.ceil(len(weapon_ids) / per_page))
        self.weapon_page = int(clamp(self.weapon_page, 0, total_pages - 1))
        page = weapon_ids[self.weapon_page * per_page:self.weapon_page * per_page + per_page]
        self.weapon_prev_btn.enabled = self.weapon_page > 0
        self.weapon_next_btn.enabled = (self.weapon_page + 1) < total_pages

        for i, wid in enumerate(page):
            c, r = i % cols, i // cols
            rect = pygame.Rect(box.x + pad + c * (card_w + gap_x),
                               box.y + pad + r * (card_h + gap_y), card_w, card_h)
            wdef = WEAPONS[wid]
            unlocked = bool(self.save.weapon_unlocks.get(wid, False))
            equipped = (self.save.selected_weapon == wid) and unlocked
            hover = rect.collidepoint(mouse_pos)
            if hover and mouse_down:
                if unlocked:
                    self.save.selected_weapon = wid
                    self.save.save()
                    self.audio_play("buy")
                else:
                    self.weapon_notice_text = "LOCKED — buy it in Shop › Weapons"
                    self.weapon_notice_timer = 1.3
                    self.audio_play("hit")

            accent = glass.GL_GOOD if equipped else (glass.GL_ACCENT if (unlocked and hover) else None)
            glass.panel(self.screen, rect, radius=16,
                        alpha=48 if (hover and unlocked) else (34 if unlocked else 20),
                        accent=accent, glow=equipped, shadow=hover and unlocked)

            title_col = glass.GL_TEXT if unlocked else glass.GL_TEXT_FAINT
            name_w = rect.w - 36 - (104 if (equipped or not unlocked) else 0)
            glass.text(self.screen, glass.clip_text(wdef.name, 26, name_w, bold=True), 26,
                       (rect.x + 18, rect.y + 12), title_col, bold=True)
            glass.text(self.screen, glass.clip_text(wdef.desc, 20, rect.w - 36), 20,
                       (rect.x + 18, rect.y + 40), glass.GL_TEXT_DIM)
            trait = trait_of(wid)
            if trait.name:
                glass.text(self.screen, glass.clip_text(f"{trait.name}: {trait.desc}", 17, rect.w - 36),
                           17, (rect.x + 18, rect.y + 64),
                           glass.GL_ACCENT_2 if unlocked else glass.GL_TEXT_FAINT)

            shots = wdef.radial if wdef.radial > 0 else max(1, wdef.bullets_per_shot)
            dps = wdef.base_damage * shots / max(0.01, wdef.fire_cd)
            stats = f"DMG {wdef.base_damage}  ·  {dps:.0f} DPS"
            glass.text(self.screen, stats, 18, (rect.x + 18, rect.bottom - 30),
                       glass.GL_ACCENT if unlocked else glass.GL_TEXT_FAINT, bold=True)

            tag = pygame.Rect(rect.right - 110, rect.y + 12, 94, 28)
            if equipped:
                glass.badge(self.screen, tag, "EQUIPPED", color=glass.GL_GOOD, size=15)
            elif not unlocked:
                glass.badge(self.screen, tag, "LOCKED", color=glass.GL_TEXT_DIM, filled=False, size=15)
        return total_pages

    def draw_weapon_mastery(self, box, mouse_pos, mouse_down, events) -> int:
        cols, rows = 2, 3
        gap_x, gap_y, pad = 12, 14, 16
        card_w = (box.w - pad * 2 - gap_x * (cols - 1)) // cols
        card_h = (box.h - pad * 2 - gap_y * (rows - 1)) // rows
        per_page = cols * rows
        weapon_ids = list(WEAPONS.keys())
        total_pages = max(1, math.ceil(len(weapon_ids) / per_page))
        self.weapon_page = int(clamp(self.weapon_page, 0, total_pages - 1))
        page = weapon_ids[self.weapon_page * per_page:self.weapon_page * per_page + per_page]
        self.weapon_prev_btn.enabled = self.weapon_page > 0
        self.weapon_next_btn.enabled = (self.weapon_page + 1) < total_pages

        for i, wid in enumerate(page):
            c, r = i % cols, i // cols
            rect = pygame.Rect(box.x + pad + c * (card_w + gap_x),
                               box.y + pad + r * (card_h + gap_y), card_w, card_h)
            stats, changed = self.save.ensure_mastery_entry(wid)
            if changed:
                self.save.save()
            level = int(stats.get("level", 0))
            level_kills = int(stats.get("level_kills", 0))
            level_wins = int(stats.get("level_wins", 0))
            total_kills = int(stats.get("total_kills", stats.get("kills", 0)))
            total_wins = int(stats.get("total_wins", stats.get("games", 0)))
            req_level = min(level + 1, MAX_MASTERY_LEVEL)
            req_kills = int(stats.get("req_kills", mastery_requirements(req_level)[0]))
            req_wins = int(stats.get("req_wins", mastery_requirements(req_level)[1]))
            unlocked = bool(self.save.weapon_unlocks.get(wid, False))
            wdef = WEAPONS[wid]

            glass.panel(self.screen, rect, radius=16, alpha=34 if unlocked else 20,
                        accent=glass.GL_GOLD if level >= MAX_MASTERY_LEVEL else None, shadow=False)
            pad_x = rect.x + 18
            inner_w = rect.w - 36
            label = "MAX" if level >= MAX_MASTERY_LEVEL else f"Lv {level}/{MAX_MASTERY_LEVEL}"
            accent = glass.GL_GOLD if level >= MAX_MASTERY_LEVEL else (glass.GL_ACCENT if unlocked else glass.GL_TEXT_FAINT)
            glass.text(self.screen, glass.clip_text(wdef.name, 24, inner_w - 70, bold=True), 24,
                       (pad_x, rect.y + 12), glass.GL_TEXT if unlocked else glass.GL_TEXT_FAINT, bold=True)
            glass.text(self.screen, label, 18, (rect.right - 18, rect.y + 18), accent, align="right", bold=True)

            stat_y = rect.y + 46
            glass.text(self.screen, f"Kills {min(level_kills, req_kills)}/{req_kills}", 17,
                       (pad_x, stat_y), glass.GL_TEXT_DIM)
            glass.text(self.screen, f"Runs {min(level_wins, req_wins)}/{req_wins}", 17,
                       (rect.right - 18, stat_y), glass.GL_TEXT_DIM, align="right")

            bar = pygame.Rect(pad_x, stat_y + 24, inner_w, 9)
            if level >= MAX_MASTERY_LEVEL:
                glass.progress_bar(self.screen, bar, 1.0, color=glass.GL_GOOD)
            else:
                col_w = (inner_w - 10) // 2
                glass.progress_bar(self.screen, pygame.Rect(bar.x, bar.y, col_w, 9),
                                   clamp(level_kills / max(1, req_kills), 0, 1), color=glass.GL_ACCENT)
                glass.progress_bar(self.screen, pygame.Rect(bar.right - col_w, bar.y, col_w, 9),
                                   clamp(level_wins / max(1, req_wins), 0, 1), color=glass.GL_ACCENT_2)

            if unlocked:
                glass.text(self.screen, glass.clip_text(f"Total kills {total_kills}  ·  Runs {total_wins}", 17, inner_w),
                           17, (pad_x, bar.bottom + 10), glass.GL_TEXT_FAINT)
            else:
                glass.text(self.screen, "Locked — unlock in Shop › Weapons", 17,
                           (pad_x, bar.bottom + 10), glass.GL_WARN)
        return total_pages
