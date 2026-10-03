"""Shop screen (liquid-glass style): meta, weapons, maps, cosmetics and bundles."""
from __future__ import annotations

import math

import pygame

from tankgame.config import *
from tankgame.util import *
from tankgame.ui import glass
from tankgame.data.weapons import WEAPONS
from tankgame.data.shop import (SHOP_ITEMS_BY_ID, SHOP_ITEMS_BY_WEAPON, COSMETICS,
                                COSMETICS_BY_ID, BUNDLES)
from tankgame.ui.widgets import Button, cached_button


def _mouse_state(events):
    return pygame.mouse.get_pos(), any(
        e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)


class ShopScreenMixin:

    def draw_shop(self, events):
        glass.background(self.screen)
        cx = WIDTH // 2
        glass.text(self.screen, "SHOP", 60, (cx, 44), glass.GL_TEXT, align="center", bold=True, glow=True)
        glass.text(self.screen, f"{self.save.coins:,} coins", 24, (cx, 88), glass.GL_COIN, align="center", bold=True)

        mouse_pos, mouse_down = _mouse_state(events)
        for tab in self.shop_tabs:
            tab.update(mouse_pos, mouse_down)
            tab.draw(self.screen, self.font_shop_item, active=(tab.tab_id == self.shop_tab))

        controls_top = self.shop_prev_btn.rect.top
        if self.shop_tab == "cosmetics":
            for tab in self.cosmetic_tabs:
                tab.update(mouse_pos, mouse_down)
                tab.draw(self.screen, self.font_shop_desc, active=(tab.tab_id == self.cosmetics_category))
            list_top = 222
        else:
            list_top = 176
        box = pygame.Rect(70, list_top, WIDTH - 140, controls_top - 14 - list_top)
        glass.panel(self.screen, box, accent=glass.GL_ACCENT, glow=True)

        if self.shop_tab == "cosmetics":
            self._draw_shop_cosmetics(box, mouse_pos, mouse_down, events)
        elif self.shop_tab == "bundles":
            self._draw_shop_bundles(box, mouse_pos, mouse_down, events)
        else:
            self._draw_shop_items(box, mouse_pos, mouse_down, events)

        self.shop_back_btn.update(1 / 60, mouse_pos, mouse_down, events)
        self.shop_back_btn.draw(self.screen, self.font_med)
        self.shop_prev_btn.update(1 / 60, mouse_pos, mouse_down, events)
        self.shop_next_btn.update(1 / 60, mouse_pos, mouse_down, events)
        self.shop_prev_btn.draw(self.screen, self.font_med)
        self.shop_next_btn.draw(self.screen, self.font_med)

    def _page(self, items, box, row_h, gap=12):
        rows_per_page = max(1, (box.h - 28) // (row_h + gap))
        total_pages = max(1, math.ceil(len(items) / rows_per_page))
        self.shop_page = int(clamp(self.shop_page, 0, total_pages - 1))
        start = self.shop_page * rows_per_page
        page = items[start:start + rows_per_page]
        self.shop_prev_btn.enabled = self.shop_page > 0
        self.shop_next_btn.enabled = (self.shop_page + 1) < total_pages
        mid_x = (self.shop_prev_btn.rect.centerx + self.shop_next_btn.rect.centerx) // 2
        glass.text(self.screen, f"Page {self.shop_page + 1}/{total_pages}", 18,
                   (mid_x, self.shop_prev_btn.rect.bottom + 8), glass.GL_TEXT_DIM, align="center")
        return page

    def _draw_shop_items(self, box, mouse_pos, mouse_down, events):
        items = self._shop_items_for_tab()
        row_h = 74
        page = self._page(items, box, row_h)
        x0, y = box.x + 18, box.y + 16
        for item in page:
            row = pygame.Rect(x0, y, box.w - 36, row_h)
            y += row_h + 12
            maxed = self.is_maxed(item)
            cost = self.shop_cost(item)
            glass.panel(self.screen, row, radius=14, alpha=30, shadow=False)

            if item.kind == "weapon":
                owned = bool(self.save.weapon_unlocks.get(item.weapon_id, False))
                status = "UNLOCKED" if owned else "LOCKED"
                status_col = glass.GL_GOOD if owned else glass.GL_TEXT_DIM
            elif item.kind == "map":
                owned = bool(self.save.map_unlocks.get(item.weapon_id, False))
                status = "OWNED" if owned else "LOCKED"
                status_col = glass.GL_GOOD if owned else glass.GL_TEXT_DIM
            else:
                lvl = int(self.save.shop_levels.get(item.id, 0))
                status = f"LEVEL {lvl}/{item.max_level}"
                status_col = glass.GL_ACCENT

            glass.text(self.screen, item.name, 26, (row.x + 16, row.y + 10), glass.GL_TEXT, bold=True)
            glass.text(self.screen, glass.clip_text(item.desc, 20, row.w - 320), 20,
                       (row.x + 16, row.y + 40), glass.GL_TEXT_DIM)
            glass.text(self.screen, status, 18, (row.right - 150, row.y + 14), status_col, align="right", bold=True)
            cost_txt = "MAX" if maxed else f"{cost:,} coins"
            glass.text(self.screen, cost_txt, 18, (row.right - 150, row.y + 40),
                       glass.GL_COIN if not maxed else glass.GL_TEXT_FAINT, align="right", bold=True)

            buy = pygame.Rect(row.right - 126, row.centery - 22, 108, 44)
            label = "Buy" if not maxed else ("Owned" if item.kind in ("weapon", "map") else "Max")
            btn = cached_button(("shop", item.id), buy, label, lambda it=item: self.buy_item(it),
                                kind="primary" if self.can_buy(item) else "normal",
                                enabled=self.can_buy(item))
            btn.update(1 / 60, mouse_pos, mouse_down, events)
            btn.draw(self.screen, self.font_shop_small)

    def _draw_shop_cosmetics(self, box, mouse_pos, mouse_down, events):
        items = [c for c in COSMETICS if c.category == self.cosmetics_category]
        row_h = 68
        page = self._page(items, box, row_h, gap=10)
        x0, y = box.x + 18, box.y + 14
        for c in page:
            row = pygame.Rect(x0, y, box.w - 36, row_h)
            y += row_h + 10
            unlocked = bool(self.save.cosmetics_unlocked.get(c.id, False))
            equipped = self.save.cosmetics_equipped.get(c.category) == c.id
            glass.panel(self.screen, row, radius=14, alpha=34,
                        accent=glass.GL_GOOD if equipped else None, shadow=False)

            swatch = pygame.Rect(row.x + 14, row.centery - 17, 34, 34)
            sw = pygame.Surface(swatch.size, pygame.SRCALPHA)
            pygame.draw.rect(sw, (*c.color, 255), sw.get_rect(), border_radius=10)
            pygame.draw.rect(sw, (255, 255, 255, 60), sw.get_rect(), 1, border_radius=10)
            self.screen.blit(sw, swatch.topleft)

            glass.text(self.screen, c.name, 24, (row.x + 60, row.y + 10), glass.GL_TEXT, bold=True)
            glass.text(self.screen, glass.clip_text(c.desc, 20, row.w - 360), 20,
                       (row.x + 60, row.y + 38), glass.GL_TEXT_DIM)
            status = "Owned" if unlocked else ("Bundle Exclusive" if c.bundle_only else f"{c.cost} coins")
            glass.text(self.screen, status, 18, (row.right - 150, row.centery),
                       glass.GL_GOOD if unlocked else glass.GL_COIN, align="midright")

            action = pygame.Rect(row.right - 126, row.centery - 20, 108, 40)
            if equipped:
                glass.badge(self.screen, action, "EQUIPPED", color=glass.GL_GOOD, size=16)
            else:
                label = "Equip" if unlocked else ("Bundle" if c.bundle_only else "Buy")
                can = unlocked or (not c.bundle_only and self.save.coins >= c.cost)
                btn = cached_button(("cosmetic", c.id), action, label,
                                    lambda cc=c: self.equip_cosmetic(cc) if self.save.cosmetics_unlocked.get(cc.id, False) else self.buy_cosmetic(cc),
                                    kind="primary" if can else "normal", enabled=can)
                btn.update(1 / 60, mouse_pos, mouse_down, events)
                btn.draw(self.screen, self.font_shop_small)

    def _draw_shop_bundles(self, box, mouse_pos, mouse_down, events):
        row_h = 92
        page = self._page(BUNDLES, box, row_h)
        x0, y = box.x + 18, box.y + 16
        for bundle in page:
            row = pygame.Rect(x0, y, box.w - 36, row_h)
            y += row_h + 12
            weapons, meta, cosmetics = self.resolve_bundle_items(bundle)
            owned = self.bundle_is_owned(bundle)
            cost = self.bundle_price(bundle)
            glass.panel(self.screen, row, radius=14, alpha=32,
                        accent=glass.GL_ACCENT_2 if not owned else glass.GL_GOOD, shadow=False)
            includes = []
            includes += [WEAPONS[w].name for w in weapons if w in WEAPONS]
            includes += [SHOP_ITEMS_BY_ID[m].name for m in meta if m in SHOP_ITEMS_BY_ID]
            includes += [COSMETICS_BY_ID[c].name for c in cosmetics if c in COSMETICS_BY_ID]
            includes_txt = ", ".join(includes) if includes else "No bundle items available"

            glass.text(self.screen, bundle.name, 26, (row.x + 16, row.y + 10), glass.GL_TEXT, bold=True)
            glass.text(self.screen, glass.clip_text(bundle.desc, 20, row.w - 320), 20,
                       (row.x + 16, row.y + 38), glass.GL_TEXT_DIM)
            glass.text(self.screen, glass.clip_text("Includes: " + includes_txt, 18, row.w - 320),
                       18, (row.x + 16, row.y + 62), glass.GL_TEXT_FAINT)
            status = "OWNED" if owned else f"{int(bundle.discount * 100)}% off"
            glass.text(self.screen, status, 18, (row.right - 150, row.y + 20),
                       glass.GL_GOOD if owned else glass.GL_ACCENT_2, align="right", bold=True)
            glass.text(self.screen, "OWNED" if owned else f"{cost:,} coins", 18,
                       (row.right - 150, row.y + 48), glass.GL_COIN, align="right", bold=True)

            buy = pygame.Rect(row.right - 126, row.centery - 22, 108, 44)
            can = (not owned) and (self.save.coins >= cost) and cost > 0
            btn = cached_button(("bundle", bundle.id), buy, "Owned" if owned else "Buy",
                                lambda b=bundle: self.buy_bundle(b),
                                kind="primary" if can else "normal", enabled=can)
            btn.update(1 / 60, mouse_pos, mouse_down, events)
            btn.draw(self.screen, self.font_shop_small)
