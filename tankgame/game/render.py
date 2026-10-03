"""World rendering and the HUD (menu screens live in tankgame/ui/screens)."""
from __future__ import annotations

import math
import random
import sys
import time
import traceback
from typing import Dict, List, Optional, Tuple

import pygame
from pygame.math import Vector2

from tankgame.config import *
from tankgame.util import *
from tankgame.ui.text import *
from tankgame.audio import *
from tankgame.save import SaveManager
from tankgame.data.weapons import WEAPONS
from tankgame.data.traits import TRAITS, trait_of, TraitDef
from tankgame.data.upgrades import UPGRADES, UPGRADES_BY_ID, UpgradeDef
from tankgame.data.shop import (SHOP_ITEMS, SHOP_ITEMS_BY_ID, SHOP_ITEMS_BY_WEAPON,
                                SHOP_ITEMS_BY_MAP, ShopItemDef, COSMETICS, COSMETICS_BY_ID,
                                DEFAULT_COSMETICS, BUNDLES, CosmeticDef, BundleDef,
                                BUNDLE_ONLY_COSMETIC_VALUE)
from tankgame.data.maps import MAPS, MAPS_BY_ID, MapDef, map_of
from tankgame.data.mutators import MUTATORS, MUTATORS_BY_ID, MutatorDef
from tankgame.data.minigames import (MINIGAMES, MINIGAMES_BY_ID, MinigameDef,
                                      METEOR_TELEGRAPH_START, METEOR_TELEGRAPH_END,
                                      METEOR_RADIUS, METEOR_MAX_ACTIVE)
from tankgame.data.mastery import MAX_MASTERY_LEVEL, mastery_requirements
from tankgame.entities.player import Player
from tankgame.entities.enemies import (EnemyBase, Chaser, Ranged, Tank, Sprinter, Dasher,
                                        Pink, Boss)
from tankgame.entities.projectile import Projectile
from tankgame.entities.pickup import Pickup
from tankgame.entities.fx import Particle, FloatingText
from tankgame.entities.drone import Drone
from tankgame.entities.meteor import Meteor
from tankgame.art.tank_art import draw_tank
from tankgame.ui.widgets import Button, TabButton




class RenderMixin:

    def draw_background(self):
        self.screen.fill(C_BG)
        cam = self.cam + self.shake_vec
        start_x = int(cam.x // BG_GRID_SIZE) * BG_GRID_SIZE
        start_y = int(cam.y // BG_GRID_SIZE) * BG_GRID_SIZE

        for x in range(start_x, int(cam.x) + WIDTH + BG_GRID_SIZE, BG_GRID_SIZE):
            sx = x - cam.x
            pygame.draw.line(self.screen, C_GRID, (sx, 0), (sx, HEIGHT), 1)

        for y in range(start_y, int(cam.y) + HEIGHT + BG_GRID_SIZE, BG_GRID_SIZE):
            sy = y - cam.y
            pygame.draw.line(self.screen, C_GRID, (0, sy), (WIDTH, sy), 1)

        border = pygame.Rect(-cam.x, -cam.y, ARENA_W, ARENA_H)
        pygame.draw.rect(self.screen, (46, 53, 70), border, 2)

    def draw_obstacles(self):
        cam = self.cam + self.shake_vec
        for r in self.obstacles:
            rr = pygame.Rect(r.x - cam.x, r.y - cam.y, r.w, r.h)
            pygame.draw.rect(self.screen, C_WALL, rr, border_radius=8)
            pygame.draw.rect(self.screen, C_WALL_EDGE, rr, 1, border_radius=8)

    def draw_pickup_indicators(self, t_seconds: float):
        cam = self.cam + self.shake_vec

        # where the line "comes from" on screen (player)
        origin = Vector2(self.player.pos.x - cam.x, self.player.pos.y - cam.y)

        # pull markers inward so they don't clip
        inset = 22
        left = inset
        right = WIDTH - inset
        top = inset
        bottom = HEIGHT - inset

        def ray_to_screen_edge(o: Vector2, dirn: Vector2) -> Optional[Vector2]:
            """Return intersection point of ray o + t*dirn with inset screen rect."""
            t_candidates = []

            if abs(dirn.x) > 1e-8:
                t = (left - o.x) / dirn.x
                y = o.y + dirn.y * t
                if t > 0 and top <= y <= bottom:
                    t_candidates.append(t)

                t = (right - o.x) / dirn.x
                y = o.y + dirn.y * t
                if t > 0 and top <= y <= bottom:
                    t_candidates.append(t)

            if abs(dirn.y) > 1e-8:
                t = (top - o.y) / dirn.y
                x = o.x + dirn.x * t
                if t > 0 and left <= x <= right:
                    t_candidates.append(t)

                t = (bottom - o.y) / dirn.y
                x = o.x + dirn.x * t
                if t > 0 and left <= x <= right:
                    t_candidates.append(t)

            if not t_candidates:
                return None

            t_edge = min(t_candidates)
            p = o + dirn * t_edge
            p.x = clamp(p.x, left, right)
            p.y = clamp(p.y, top, bottom)
            return p

        # transparent overlay so arrows aren't loud (reused every frame)
        overlay = self.fx_overlay
        overlay.fill((0, 0, 0, 0))

        for p in self.pickups:
            # only track POWERUPS (rapid fire / damage / etc)
            if p.kind != "power":
                continue

            screen = Vector2(p.pos.x - cam.x, p.pos.y - cam.y)

            # if it's on-screen, don't show an indicator
            if (-10 <= screen.x <= WIDTH + 10) and (-10 <= screen.y <= HEIGHT + 10):
                continue

            d = screen - origin
            if d.length_squared() < 1e-6:
                continue
            dirn = d.normalize()

            edge = ray_to_screen_edge(origin, dirn)
            if edge is None:
                continue

            # little pulsing + color by type
            col = {
                "damage_boost": (255, 120, 220),
                "rapid_fire": (120, 255, 240),
                "speed_boost": (140, 255, 160),
                "shield": (200, 200, 255),
            }.get(p.power_type, (220, 210, 255))

            pulse = 0.5 + 0.5 * math.sin(t_seconds * 6.0 + (p.pos.x + p.pos.y) * 0.003)
            a = int(90 + 70 * pulse)  # subtle

            tip = edge
            back = tip - dirn * 18
            perp = Vector2(-dirn.y, dirn.x)

            left_pt = back + perp * 8
            right_pt = back - perp * 8

            # draw arrow
            pygame.draw.polygon(
                overlay,
                (*col, a),
                [(int(tip.x), int(tip.y)),
                 (int(left_pt.x), int(left_pt.y)),
                 (int(right_pt.x), int(right_pt.y))]
            )

            # small ring for clarity
            pygame.draw.circle(overlay, (*col, int(a * 0.75)), (int(tip.x), int(tip.y)), 12, 2)

        self.screen.blit(overlay, (0, 0))

    def draw_entities(self):
        cam = self.cam + self.shake_vec
        tsec = time.time()

        # Scorched ground sits under everything else so units read clearly over it.
        for h in self.hazards:
            hp = (int(h["pos"].x - cam.x), int(h["pos"].y - cam.y))
            frac = clamp(h["life"] / max(0.01, h["life_max"]), 0.0, 1.0)
            rad = int(h["radius"] * (0.85 + 0.15 * frac))
            pygame.draw.circle(self.screen, (96, 46, 22), hp, rad)
            pygame.draw.circle(self.screen, (196, 96, 40), hp, rad, 2)
            if frac > 0.05:
                pygame.draw.circle(self.screen, (255, 150, 60), hp, max(2, int(rad * 0.5 * frac)))

        for p in self.pickups:
            p.draw(self.screen, cam, tsec)

        for pt in self.particles:
            pt.draw(self.screen, cam)

        for b in self.projectiles:
            b.draw(self.screen, cam)
        for b in self.enemy_projectiles:
            b.draw(self.screen, cam)

        for e in self.enemies:
            e.draw(self.screen, cam)

        for d in self.drones:
            d.draw(self.screen, cam)

        for ft in self.float_texts:
            ft.draw(self.screen, cam, self.font_small)

        self.player.draw(self.screen, cam)
        self.draw_pickup_indicators(tsec)

    def draw_minigame_view(self):
        """Meteors and other minigame overlays - above the world, below the HUD."""
        cam = self.cam + self.shake_vec
        for m in self.meteors:
            m.draw(self.screen, cam)

    def _get_boss(self) -> Optional[Boss]:
        for e in self.enemies:
            if isinstance(e, Boss) and e.alive():
                return e
        return None

    def draw_panel(self, rect: pygame.Rect, fill, edge=None, radius: int = 12, border: int = 1):
        """Rounded panel that actually honours alpha.

        pygame.draw.* ignores the alpha byte when blitting straight onto the display surface, so
        the old "(*C_PANEL, 220)" HUD panels rendered fully opaque.
        """
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(s, fill, s.get_rect(), border_radius=radius)
        if edge is not None:
            pygame.draw.rect(s, edge, s.get_rect(), border, border_radius=radius)
        self.screen.blit(s, rect.topleft)

    def draw_hud(self):
        who = self.player
        x = UI_PAD
        y = UI_PAD
        y_top = y - 8

        # ---------------- Left panel: vitals ----------------
        per_row = 12
        pr = 7
        pip_gap = 6
        row_step = 20
        mhp = max(1, int(who.max_hp))
        hp = max(0, int(who.hp))
        rows = max(1, int(math.ceil(mhp / per_row)))

        hp_row_y = y_top + 16
        xp_y = hp_row_y + 18 + (rows - 1) * row_step
        dash_y = xp_y + 24
        weapon_y = dash_y + 26

        panel_w = 446
        panel_h = max(128, weapon_y + 20 - y_top)
        left_panel = pygame.Rect(x - 8, y_top, panel_w, panel_h)
        self.draw_panel(left_panel, (*C_PANEL, 238), (*C_WALL_EDGE, 215), radius=14)

        bar_x = x + 66
        bar_w = panel_w - 66 - 22

        hp_col = C_HEALTH if hp > mhp * 0.34 else C_WARN
        draw_text(self.screen, self.font_ui, "HP", (x + 6, y_top + 4), C_TEXT)
        draw_text_right(self.screen, self.font_tiny, f"{hp}/{mhp}", (left_panel.right - 18, y_top + 10), hp_col, shadow=False)

        for i in range(mhp):
            col_i = i % per_row
            row_i = i // per_row
            px = x + 64 + pr + col_i * (pr * 2 + pip_gap)
            py = hp_row_y + row_i * row_step
            if i < hp:
                pygame.draw.circle(self.screen, hp_col, (px, py), pr)
                circle_outline(self.screen, (255, 215, 230), (px, py), pr, 1)
            else:
                circle_outline(self.screen, (58, 66, 92), (px, py), pr, 2)

        xp_bar = pygame.Rect(bar_x, xp_y, bar_w, 14)
        pygame.draw.rect(self.screen, (10, 12, 18), xp_bar, border_radius=7)
        xp_frac = clamp(who.xp / max(1, who.xp_to_next), 0, 1)
        if xp_frac > 0:
            pygame.draw.rect(self.screen, C_XP, pygame.Rect(xp_bar.x, xp_bar.y, max(3, int(xp_bar.w * xp_frac)), xp_bar.h), border_radius=7)
        pygame.draw.rect(self.screen, (60, 200, 120), xp_bar, 1, border_radius=7)
        draw_text(self.screen, self.font_tiny, f"LVL {who.level}", (x + 6, xp_y), C_TEXT_DIM, shadow=False)
        draw_text_right(self.screen, self.font_tiny, f"{int(who.xp)}/{who.xp_to_next} XP", (xp_bar.right - 8, xp_bar.y + 1), C_TEXT, shadow=False)

        dash_bar = pygame.Rect(bar_x, dash_y, bar_w, 14)
        dash_ready = who.dash_cd_timer <= 0.0
        pygame.draw.rect(self.screen, (10, 12, 18), dash_bar, border_radius=7)
        dash_frac = 1.0 if dash_ready else clamp(1.0 - who.dash_cd_timer / max(0.01, who.get_dash_cooldown()), 0, 1)
        dash_col = C_ACCENT if dash_ready else (108, 128, 172)
        if dash_frac > 0:
            pygame.draw.rect(self.screen, dash_col, pygame.Rect(dash_bar.x, dash_bar.y, max(3, int(dash_bar.w * dash_frac)), dash_bar.h), border_radius=7)
        draw_text(self.screen, self.font_tiny, "DASH", (x + 6, dash_y), C_TEXT_DIM, shadow=False)
        draw_text_right(self.screen, self.font_tiny,
                        "READY [SPACE]" if dash_ready else f"{who.dash_cd_timer:.1f}s",
                        (dash_bar.right - 8, dash_bar.y + 1),
                        (12, 26, 22) if dash_ready else C_TEXT, shadow=False)

        draw_text(self.screen, self.font_small, who.weapon.name, (x + 6, weapon_y - 6), C_ACCENT, shadow=False)
        draw_text_right(self.screen, self.font_tiny, f"{fmt_amount(who.get_damage())} DMG / SHOT",
                        (left_panel.right - 18, weapon_y - 3), C_TEXT_DIM, shadow=False)

        # ---------------- Right panel: run stats ----------------
        rp_w = 336
        right_panel = pygame.Rect(WIDTH - UI_PAD - rp_w + 8, y_top, rp_w, panel_h)
        self.draw_panel(right_panel, (*C_PANEL, 238), (*C_WALL_EDGE, 215), radius=14)

        draw_text(self.screen, self.font_tiny, "SCORE", (right_panel.x + 16, y_top + 8), C_TEXT_DIM, shadow=False)
        draw_text_right(self.screen, self.font_med, str(who.score), (right_panel.right - 16, y_top + 2), C_TEXT)

        stats = (
            ("WAVE", str(self.wave), C_ACCENT),
            ("TIME", f"{int(self.survival_time)}s", C_TEXT),
            ("COINS", str(self.save.coins), C_COIN),
        )
        col_w = (right_panel.w - 32) // 3
        for i, (label, val, col) in enumerate(stats):
            cxs = right_panel.x + 16 + i * col_w
            draw_text(self.screen, self.font_tiny, label, (cxs, y_top + 32), C_TEXT_DIM, shadow=False)
            draw_text(self.screen, self.font_ui, val, (cxs, y_top + 46), col, shadow=False)

        wave_bar = pygame.Rect(right_panel.x + 16, y_top + 82, right_panel.w - 32, 12)
        pygame.draw.rect(self.screen, (10, 12, 18), wave_bar, border_radius=6)
        if self.in_boss_fight:
            wave_frac, wave_col, wave_label = 1.0, C_ACCENT_2, "BOSS FIGHT"
        elif self.boss_grace_timer > 0.0:
            wave_frac = clamp(self.boss_grace_timer / max(0.1, BOSS_GRACE_AFTER_DEATH), 0, 1)
            wave_col, wave_label = C_OK, "FIELD CLEAR"
        else:
            wave_frac = clamp(1.0 - self.wave_timer / WAVE_TIME_BASE, 0, 1)
            wave_col = C_ACCENT
            wave_label = f"NEXT WAVE IN {max(0.0, self.wave_timer):.1f}s"
        if wave_frac > 0:
            pygame.draw.rect(self.screen, wave_col, pygame.Rect(wave_bar.x, wave_bar.y, max(3, int(wave_bar.w * wave_frac)), wave_bar.h), border_radius=6)
        draw_text(self.screen, self.font_tiny, wave_label, (wave_bar.x, wave_bar.y - 16), C_TEXT_DIM, shadow=False)

        # Which map you rolled, plus a live drone tally for the Nanite Swarm tank.
        map_line = f"MAP: {self.current_map.name.upper()}"
        if self.drones:
            map_line += f"   \u2022   DRONES {len(self.drones)}"
        draw_text(self.screen, self.font_tiny, map_line, (right_panel.x + 16, wave_bar.bottom + 8),
                  C_TEXT_DIM, shadow=False)

        hud_bottom = max(left_panel.bottom, right_panel.bottom)

        # Minigame objective strip, centred just under the panels.
        if self.minigame is not None:
            mg = self.minigame
            if mg.duration > 0.0:
                mg_txt = f"{mg.name.upper()}   \u2022   {max(0.0, mg.duration - self.minigame_time):0.1f}s"
            else:
                mg_txt = f"{mg.name.upper()}   \u2022   FIND THE EXIT"
            draw_text(self.screen, self.font_small, mg_txt, (WIDTH // 2, hud_bottom + 6),
                      mg.accent, center=True, shadow=True)

        # ---------------- Boss bar: below the HUD panels, never over them ----------------
        boss = self._get_boss()
        if boss is not None:
            bw = 560
            bh = 16
            bx = WIDTH // 2 - bw // 2
            by = hud_bottom + 30
            boss_panel = pygame.Rect(bx - 14, by - 26, bw + 28, bh + 40)
            edge = C_ACCENT_2 if not boss.enraged else C_WARN
            self.draw_panel(boss_panel, (*C_PANEL, 240), (*edge, 215), radius=12)

            frac = clamp(boss.hp / max(1.0, boss.hp_max), 0, 1)
            draw_text(self.screen, self.font_small, "BOSS — ENRAGED" if boss.enraged else "BOSS",
                      (boss_panel.x + 14, by - 22), edge, shadow=False)
            draw_text_right(self.screen, self.font_small, f"{int(frac * 100)}%", (boss_panel.right - 14, by - 22), C_TEXT, shadow=False)

            pygame.draw.rect(self.screen, (10, 10, 14), pygame.Rect(bx, by, bw, bh), border_radius=8)
            fill_col = (255, 120, 140) if not boss.enraged else (255, 190, 80)
            if frac > 0:
                pygame.draw.rect(self.screen, fill_col, pygame.Rect(bx, by, max(2, int(bw * frac)), bh), border_radius=8)
            pygame.draw.rect(self.screen, (255, 210, 220), pygame.Rect(bx, by, bw, bh), 2, border_radius=8)

        # ---------------- Active power-up chips ----------------
        chip_labels = {"damage_boost": "DMG", "rapid_fire": "RAPID", "speed_boost": "SPEED", "shield": "SHIELD"}
        chip_cols = {
            "damage_boost": (255, 120, 220),
            "rapid_fire": (120, 255, 240),
            "speed_boost": (140, 255, 160),
            "shield": (200, 200, 255),
        }
        active = [(k, v) for k, v in who.effects.items() if v > 0]
        if active:
            chip_w = 124
            total = len(active) * chip_w + (len(active) - 1) * 8
            chip_x = WIDTH // 2 - total // 2
            for key, remaining in active:
                col = chip_cols.get(key, C_ACCENT)
                chip = pygame.Rect(chip_x, HEIGHT - 50, chip_w, 30)
                self.draw_panel(chip, (*col, 46), (*col, 215), radius=9)
                draw_text(self.screen, self.font_tiny, chip_labels.get(key, key.upper()),
                          (chip.x + 9, chip.y + 5), col, shadow=False)
                draw_text_right(self.screen, self.font_tiny, f"{remaining:.1f}s",
                                (chip.right - 9, chip.y + 5), C_TEXT, shadow=False)
                chip_x += chip_w + 8

        # ---------------- Wave modifier chip (sits in the gap between the two panels) ----------------
        if self.wave_mutator is not None:
            mut = self.wave_mutator
            chip_w = 264
            chip = pygame.Rect((left_panel.right + right_panel.x) // 2 - chip_w // 2, y_top + 4, chip_w, 42)
            self.draw_panel(chip, (*mut.color, 62), (*mut.color, 225), radius=10)
            draw_text(self.screen, self.font_small, mut.name, (chip.x + 12, chip.y + 5), mut.color, shadow=False)
            draw_text(self.screen, self.font_tiny, mut.desc, (chip.x + 12, chip.y + 23), C_TEXT_DIM, shadow=False)

        # ---------------- Auto-fire badge ----------------
        if who.auto_fire:
            badge = pygame.Rect(WIDTH - 148, HEIGHT - 46, 132, 30)
            self.draw_panel(badge, (*C_OK, 220), (*C_WALL_EDGE, 220), radius=12)
            rect_centered_text(self.screen, self.font_small, "AUTO FIRE", badge, (12, 26, 14), shadow=False)

        # ---------------- Wave / boss banner ----------------
        if self.wave_banner_timer > 0.0 and self.wave_banner_text:
            draw_text(self.screen, self.font_med, self.wave_banner_text, (WIDTH // 2, 236),
                      C_ACCENT_2 if "BOSS" in self.wave_banner_text else C_TEXT, center=True)

    def draw_boss_tracker(self):
        """Off-screen tracker: a subtle transparent line from the PLAYER toward the boss.
        Only draws when the boss is off-screen. Endpoint is true screen-edge intersection.
        """
        boss = self._get_boss()
        if boss is None:
            return

        cam = self.cam + self.shake_vec

        # Boss + player in screen space
        boss_s = Vector2(boss.pos.x - cam.x, boss.pos.y - cam.y)
        player_s = Vector2(self.player.pos.x - cam.x, self.player.pos.y - cam.y)

        # Only draw when boss is off-screen
        off_margin = 40
        if (-off_margin <= boss_s.x <= WIDTH + off_margin) and (-off_margin <= boss_s.y <= HEIGHT + off_margin):
            return

        d = boss_s - player_s
        if d.length_squared() < 1e-6:
            return
        dirn = d.normalize()

        # --- Find intersection of ray (player_s -> dirn) with screen rect, minus an inset margin ---
        inset = 26  # pull endpoint inside screen so label always fits
        left = inset
        right = WIDTH - inset
        top = inset
        bottom = HEIGHT - inset

        t_candidates = []

        # Vertical sides
        if abs(dirn.x) > 1e-8:
            t = (left - player_s.x) / dirn.x
            y = player_s.y + dirn.y * t
            if t > 0 and top <= y <= bottom:
                t_candidates.append(t)

            t = (right - player_s.x) / dirn.x
            y = player_s.y + dirn.y * t
            if t > 0 and top <= y <= bottom:
                t_candidates.append(t)

        # Horizontal sides
        if abs(dirn.y) > 1e-8:
            t = (top - player_s.y) / dirn.y
            x = player_s.x + dirn.x * t
            if t > 0 and left <= x <= right:
                t_candidates.append(t)

            t = (bottom - player_s.y) / dirn.y
            x = player_s.x + dirn.x * t
            if t > 0 and left <= x <= right:
                t_candidates.append(t)

        if not t_candidates:
            return

        t_edge = min(t_candidates)
        edge = player_s + dirn * t_edge

        # Nudge the whole marker up a few pixels so the distance text is always visible
        nudge_up = 10
        edge.y -= nudge_up

        # Final clamp (just in case)
        edge.x = clamp(edge.x, left, right)
        edge.y = clamp(edge.y, top, bottom)

        # --- Draw on a transparent overlay so it’s visible but not loud (reused every frame) ---
        overlay = self.fx_overlay
        overlay.fill((0, 0, 0, 0))

        # Softer, semi-transparent line
        LINE_COL = (*C_ACCENT_2, 95)     # low alpha so it’s not distracting
        OUTLINE_COL = (0, 0, 0, 70)      # faint outline for readability

        p1 = (int(player_s.x), int(player_s.y))
        p2 = (int(edge.x), int(edge.y))

        pygame.draw.line(overlay, OUTLINE_COL, p1, p2, 6)
        pygame.draw.line(overlay, LINE_COL, p1, p2, 3)

        # Small end-cap so you can see where it’s pointing
        pygame.draw.circle(overlay, OUTLINE_COL, p2, 9, 3)
        pygame.draw.circle(overlay, LINE_COL, p2, 9, 2)

        self.screen.blit(overlay, (0, 0))

        # Distance label: ABOVE the endpoint (so it never gets cut off at bottom)
        dist = (boss.pos - self.player.pos).length()
        draw_text(
            self.screen,
            self.font_tiny,
            f"{int(dist)}",
            (p2[0], p2[1] - 16),
            C_TEXT,
            center=True,
            shadow=False
        )

    def draw_overlay_dim(self, alpha=170):
        o = self.fx_overlay
        o.fill((0, 0, 0, alpha))
        self.screen.blit(o, (0, 0))
        o.fill((0, 0, 0, 0))
        
    # =========================================================
    # SCREENS
    # =========================================================
