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
from tankgame.ui import glass




class RenderMixin:

    def draw_background(self):
        cam = self.cam + self.shake_vec
        bg = getattr(self, "_arena_bg", None)
        if bg is None or bg.get_size() != (WIDTH, HEIGHT):
            bg = pygame.Surface((WIDTH, HEIGHT)).convert()
            bg.blit(glass._vgrad((WIDTH, HEIGHT), (*C_BG_2, 255), (*C_BG, 255)), (0, 0))
            self._arena_bg = bg
        self.screen.blit(bg, (0, 0))

        start_x = int(cam.x // BG_GRID_SIZE) * BG_GRID_SIZE
        start_y = int(cam.y // BG_GRID_SIZE) * BG_GRID_SIZE
        major = BG_GRID_SIZE * 4
        major_col = (31, 37, 50)
        for gx in range(start_x, int(cam.x) + WIDTH + BG_GRID_SIZE, BG_GRID_SIZE):
            sx = int(gx - cam.x)
            pygame.draw.line(self.screen, major_col if gx % major == 0 else C_GRID, (sx, 0), (sx, HEIGHT), 1)
        for gy in range(start_y, int(cam.y) + HEIGHT + BG_GRID_SIZE, BG_GRID_SIZE):
            sy = int(gy - cam.y)
            pygame.draw.line(self.screen, major_col if gy % major == 0 else C_GRID, (0, sy), (WIDTH, sy), 1)

        border = pygame.Rect(int(-cam.x), int(-cam.y), ARENA_W, ARENA_H)
        pygame.draw.rect(self.screen, (40, 74, 82), border.inflate(6, 6), 3, border_radius=10)
        pygame.draw.rect(self.screen, glass.GL_ACCENT, border, 1, border_radius=8)

    def _obstacle_surface(self, w: int, h: int) -> pygame.Surface:
        cache = getattr(self, "_obstacle_cache", None)
        if cache is None:
            cache = self._obstacle_cache = {}
        surf = cache.get((w, h))
        if surf is None:
            rad = min(10, w // 4, h // 4)
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            body = glass._vgrad((w, h), (34, 40, 54, 255), (19, 22, 30, 255))
            body.blit(glass._round_mask((w, h), rad), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(body, (0, 0))
            # Armoured plate: diagonal hazard hatching, an inset bevel and corner bolts, so cover
            # reads as solid world geometry and never as a floating UI panel.
            hatch = pygame.Surface((w, h), pygame.SRCALPHA)
            for k in range(-h, w, 14):
                pygame.draw.line(hatch, (255, 255, 255, 9), (k, h), (k + h, 0), 3)
            hatch.blit(glass._round_mask((w, h), rad), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(hatch, (0, 0))
            pygame.draw.rect(surf, (12, 14, 20, 255), surf.get_rect(), 2, border_radius=rad)
            if w > 24 and h > 24:
                inset = pygame.Rect(5, 5, w - 10, h - 10)
                pygame.draw.rect(surf, (64, 76, 100, 255), inset, 1, border_radius=max(2, rad - 4))
                pygame.draw.line(surf, (110, 126, 158, 200), (inset.x + 4, inset.y), (inset.right - 5, inset.y), 1)
            if w >= 48 and h >= 48:
                for bx, by in ((10, 10), (w - 11, 10), (10, h - 11), (w - 11, h - 11)):
                    pygame.draw.circle(surf, (78, 90, 116), (bx, by), 3)
                    pygame.draw.circle(surf, (20, 24, 32), (bx, by), 3, 1)
            cache[(w, h)] = surf
        return surf

    def _obstacle_shadow(self, w: int, h: int) -> pygame.Surface:
        cache = getattr(self, "_obstacle_cache", None)
        if cache is None:
            cache = self._obstacle_cache = {}
        key = ("shadow", w, h)
        sh = cache.get(key)
        if sh is None:
            sh = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(sh, (0, 0, 0, 70), sh.get_rect(), border_radius=10)
            cache[key] = sh
        return sh

    def draw_obstacles(self):
        cam = self.cam + self.shake_vec
        view = pygame.Rect(int(cam.x) - 20, int(cam.y) - 20, WIDTH + 40, HEIGHT + 40)
        for r in self.obstacles:
            if not r.colliderect(view):
                continue
            sx, sy = int(r.x - cam.x), int(r.y - cam.y)
            self.screen.blit(self._obstacle_shadow(r.w, r.h), (sx + 5, sy + 7))
            self.screen.blit(self._obstacle_surface(r.w, r.h), (sx, sy))

    def draw_pickup_indicators(self, t_seconds: float):
        cam = self.cam + self.shake_vec

        # where the line "comes from" on screen (player)
        origin = Vector2(self.player.pos.x - cam.x, self.player.pos.y - cam.y)

        # pull markers inward so they don't clip
        inset = 22
        left = inset
        right = WIDTH - inset
        top = max(inset, getattr(self, "_hud_safe_top", 150))
        bottom = min(HEIGHT - inset, getattr(self, "_hud_safe_bottom", HEIGHT - 60))

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
        """Rounded panel that honours alpha (kept for any caller that passes explicit colours)."""
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(s, fill, s.get_rect(), border_radius=radius)
        if edge is not None:
            pygame.draw.rect(s, edge, s.get_rect(), border, border_radius=radius)
        self.screen.blit(s, rect.topleft)

    def hud_panel(self, rect: pygame.Rect, accent=None, radius: int = 14):
        """Frosted-glass HUD panel (no drop shadow - it sits over the live arena)."""
        glass.panel(self.screen, rect, radius=radius, alpha=58, accent=accent,
                    glow=accent is not None, shadow=False)

    def hud_layout(self):
        """Width-aware HUD geometry shared by the HUD and anything that must sit below it."""
        avail = WIDTH - 2 * UI_PAD
        left_w = int(clamp(avail * 0.40, 318, 446))
        right_w = int(clamp(avail * 0.31, 270, 336))
        return left_w, right_w

    def draw_hud(self):
        who = self.player
        x = UI_PAD
        y_top = UI_PAD - 6
        left_w, right_w = self.hud_layout()

        # ---------------- Left panel: vitals ----------------
        mhp = max(1, int(who.max_hp))
        hp = max(0, int(math.ceil(who.hp - 1e-6)))
        pr = 7
        step = 2 * pr + 6
        per_row = max(6, (left_w - 96 - 52) // step)
        rows = max(1, int(math.ceil(mhp / per_row)))
        hp_row_y = y_top + 22
        xp_y = hp_row_y + 16 + (rows - 1) * 20
        dash_y = xp_y + 24
        weapon_y = dash_y + 26
        panel_h = max(124, weapon_y + 22 - y_top)
        left_panel = pygame.Rect(x - 6, y_top, left_w, panel_h)
        self.hud_panel(left_panel)

        bar_x = x + 66
        bar_w = left_panel.right - 18 - bar_x
        low = hp <= max(1, int(mhp * 0.34))
        hp_col = glass.GL_BAD if not low else glass.lerp_color(glass.GL_WARN, glass.GL_BAD, glass.pulse(2.2))
        glass.text(self.screen, "HP", 20, (x + 8, hp_row_y - 9), glass.GL_TEXT, bold=True)
        glass.text(self.screen, f"{hp}/{mhp}", 16, (left_panel.right - 14, hp_row_y),
                   hp_col, align="midright", bold=True)
        for i in range(mhp):
            px = x + 66 + pr + (i % per_row) * step
            py = hp_row_y + (i // per_row) * 20
            if i < hp:
                pygame.draw.circle(self.screen, hp_col, (px, py), pr)
                pygame.draw.circle(self.screen, glass.lerp_color(hp_col, (255, 255, 255), 0.55),
                                   (px - 2, py - 2), 2)
            else:
                pygame.draw.circle(self.screen, (70, 80, 104), (px, py), pr, 2)

        xp_frac = clamp(who.xp / max(1, who.xp_to_next), 0, 1)
        glass.text(self.screen, f"LV {who.level}", 16, (x + 8, xp_y), glass.GL_TEXT_DIM, bold=True)
        glass.progress_bar(self.screen, pygame.Rect(bar_x, xp_y + 1, bar_w, 13), xp_frac, color=glass.GL_GOOD)
        glass.text(self.screen, f"{int(who.xp)}/{who.xp_to_next} XP", 15,
                   (bar_x + bar_w - 8, xp_y + 8), glass.GL_TEXT, align="midright")

        dash_ready = who.dash_cd_timer <= 0.0
        dash_frac = 1.0 if dash_ready else clamp(1.0 - who.dash_cd_timer / max(0.01, who.get_dash_cooldown()), 0, 1)
        glass.text(self.screen, "DASH", 16, (x + 8, dash_y), glass.GL_TEXT_DIM, bold=True)
        glass.progress_bar(self.screen, pygame.Rect(bar_x, dash_y + 1, bar_w, 13), dash_frac,
                           color=glass.GL_ACCENT if dash_ready else (110, 130, 176))
        glass.text(self.screen, "READY" if dash_ready else f"{who.dash_cd_timer:.1f}s", 15,
                   (bar_x + bar_w - 8, dash_y + 8), (10, 22, 22) if dash_ready else glass.GL_TEXT,
                   align="midright", bold=dash_ready)

        glass.text(self.screen, who.weapon.name, 20, (x + 8, weapon_y - 4), glass.GL_ACCENT, bold=True)
        glass.text(self.screen, f"{fmt_amount(who.get_damage())} DMG / SHOT", 15,
                   (left_panel.right - 14, weapon_y - 1), glass.GL_TEXT_DIM, align="right")

        # ---------------- Right panel: run stats ----------------
        right_panel = pygame.Rect(WIDTH - UI_PAD + 6 - right_w, y_top, right_w, panel_h)
        self.hud_panel(right_panel)
        glass.text(self.screen, "SCORE", 15, (right_panel.x + 16, y_top + 12), glass.GL_TEXT_FAINT, bold=True)
        glass.text(self.screen, f"{who.score:,}", 30, (right_panel.right - 16, y_top + 7),
                   glass.GL_TEXT, align="right", bold=True)
        stats = (("WAVE", str(self.wave), glass.GL_ACCENT),
                 ("TIME", f"{int(self.survival_time)}s", glass.GL_TEXT),
                 ("COINS", f"{self.save.coins:,}", glass.GL_COIN))
        col_w = (right_panel.w - 32) // 3
        for i, (label, val, col) in enumerate(stats):
            sx = right_panel.x + 16 + i * col_w
            glass.text(self.screen, label, 14, (sx, y_top + 38), glass.GL_TEXT_FAINT, bold=True)
            glass.text(self.screen, glass.clip_text(val, 22, col_w - 6, bold=True), 22,
                       (sx, y_top + 53), col, bold=True)

        if self.in_boss_fight:
            wave_frac, wave_col, wave_label = 1.0, glass.GL_ACCENT_3, "BOSS FIGHT"
        elif self.boss_grace_timer > 0.0:
            wave_frac = clamp(self.boss_grace_timer / max(0.1, BOSS_GRACE_AFTER_DEATH), 0, 1)
            wave_col, wave_label = glass.GL_GOOD, "FIELD CLEAR"
        else:
            wave_frac = clamp(1.0 - self.wave_timer / max(0.01, self.wave_time), 0, 1)
            wave_col = glass.GL_ACCENT
            wave_label = f"NEXT WAVE  {max(0.0, self.wave_timer):.1f}s"
        wave_bar = pygame.Rect(right_panel.x + 16, y_top + 96, right_panel.w - 32, 10)
        glass.text(self.screen, wave_label, 14, (wave_bar.x, wave_bar.y - 16), glass.GL_TEXT_DIM, bold=True)
        glass.progress_bar(self.screen, wave_bar, wave_frac, color=wave_col)
        map_line = f"MAP  {self.current_map.name.upper()}"
        if self.drones:
            map_line += f"   ·   DRONES {len(self.drones)}"
        if wave_bar.bottom + 22 <= right_panel.bottom:
            glass.text(self.screen, glass.clip_text(map_line, 14, right_panel.w - 32), 14,
                       (right_panel.x + 16, wave_bar.bottom + 8), glass.GL_TEXT_FAINT)

        hud_bottom = max(left_panel.bottom, right_panel.bottom)

        # ---------------- Wave modifier chip: between the panels if it fits, else below ----------------
        below_y = hud_bottom + 8
        if self.wave_mutator is not None:
            mut = self.wave_mutator
            gap = right_panel.x - left_panel.right
            chip_w = min(300, max(220, gap - 24))
            if gap >= chip_w + 24:
                chip = pygame.Rect((left_panel.right + right_panel.x) // 2 - chip_w // 2, y_top + 4, chip_w, 46)
            else:
                chip_w = min(320, WIDTH - 2 * UI_PAD)
                chip = pygame.Rect(WIDTH // 2 - chip_w // 2, below_y, chip_w, 46)
                below_y = chip.bottom + 8
            glass.panel(self.screen, chip, radius=14, tint=mut.color, alpha=44,
                        accent=mut.color, glow=True, shadow=False)
            glass.text(self.screen, mut.name, 19, (chip.x + 14, chip.y + 6), mut.color, bold=True)
            glass.text(self.screen, glass.clip_text(mut.desc, 15, chip.w - 28), 15,
                       (chip.x + 14, chip.y + 26), glass.GL_TEXT_DIM)

        # ---------------- Minigame objective strip ----------------
        if self.minigame is not None:
            mg = self.minigame
            if mg.duration > 0.0:
                mg_txt = f"{mg.name.upper()}   ·   {max(0.0, mg.duration - self.minigame_time):0.1f}s"
            else:
                mg_txt = f"{mg.name.upper()}   ·   SURVIVE"
            strip_w = min(420, WIDTH - 2 * UI_PAD)
            strip = pygame.Rect(WIDTH // 2 - strip_w // 2, below_y, strip_w, 30)
            glass.panel(self.screen, strip, radius=15, alpha=44, accent=mg.accent, shadow=False)
            glass.text(self.screen, mg_txt, 18, strip.center, mg.accent, align="center", bold=True)
            below_y = strip.bottom + 8

        # ---------------- Boss bar ----------------
        boss = self._get_boss()
        if boss is not None:
            bw = min(560, WIDTH - 2 * UI_PAD - 28)
            boss_panel = pygame.Rect(WIDTH // 2 - bw // 2 - 14, below_y, bw + 28, 52)
            edge = glass.GL_ACCENT_3 if not boss.enraged else glass.GL_WARN
            glass.panel(self.screen, boss_panel, radius=14, alpha=52, accent=edge, glow=True, shadow=False)
            frac = clamp(boss.hp / max(1.0, boss.hp_max), 0, 1)
            glass.text(self.screen, "BOSS — ENRAGED" if boss.enraged else "BOSS", 18,
                       (boss_panel.x + 14, boss_panel.y + 7), edge, bold=True)
            glass.text(self.screen, f"{int(frac * 100)}%", 18, (boss_panel.right - 14, boss_panel.y + 7),
                       glass.GL_TEXT, align="right", bold=True)
            glass.progress_bar(self.screen, pygame.Rect(boss_panel.x + 14, boss_panel.y + 30, bw, 12),
                               frac, color=(255, 120, 140) if not boss.enraged else (255, 190, 80))
            below_y = boss_panel.bottom + 8

        # ---------------- Active power-up chips ----------------
        chip_labels = {"damage_boost": "DAMAGE", "rapid_fire": "RAPID", "speed_boost": "SPEED",
                       "shield": "SHIELD", "drone_range": "DRONE RANGE"}
        chip_cols = {"damage_boost": (255, 120, 220), "rapid_fire": (120, 255, 240),
                     "speed_boost": (140, 255, 160), "shield": (200, 200, 255),
                     "drone_range": (170, 255, 215)}
        active = [(k, v) for k, v in who.effects.items() if v > 0]
        if active:
            reserve = 148 if who.auto_fire else 0
            lane_l, lane_r = UI_PAD, WIDTH - UI_PAD - reserve
            chip_w = min(140, (lane_r - lane_l - 8 * (len(active) - 1)) // len(active))
            total = len(active) * chip_w + (len(active) - 1) * 8
            centre = WIDTH // 2 if (WIDTH // 2 + total // 2) <= lane_r else (lane_l + lane_r) // 2
            chip_x = centre - total // 2
            for key, remaining in active:
                col = chip_cols.get(key, glass.GL_ACCENT)
                chip = pygame.Rect(chip_x, HEIGHT - 52, chip_w, 34)
                glass.panel(self.screen, chip, radius=12, tint=col, alpha=40, accent=col, shadow=False)
                glass.text(self.screen, glass.clip_text(chip_labels.get(key, key.upper()), 15, chip_w - 56),
                           15, (chip.x + 10, chip.centery), col, align="midleft", bold=True)
                glass.text(self.screen, f"{remaining:.1f}s", 15, (chip.right - 10, chip.centery),
                           glass.GL_TEXT, align="midright")
                chip_x += chip_w + 8

        # ---------------- Auto-fire badge ----------------
        if who.auto_fire:
            badge = pygame.Rect(WIDTH - UI_PAD - 136, HEIGHT - 52, 136, 34)
            glass.badge(self.screen, badge, "AUTO FIRE", color=glass.GL_GOOD, size=17)

        # ---------------- Wave / boss banner ----------------
        # Keep world-space markers (boss tracker, power-up arrows) clear of the HUD next frame.
        self._hud_safe_top = below_y
        self._hud_safe_bottom = HEIGHT - 60 if (active or who.auto_fire) else HEIGHT - 26

        if self.wave_banner_timer > 0.0 and self.wave_banner_text:
            fade = clamp(self.wave_banner_timer / 0.35, 0.0, 1.0)
            col = glass.GL_ACCENT_3 if "BOSS" in self.wave_banner_text else glass.GL_TEXT
            size = 40 if below_y + 28 <= HEIGHT // 2 - 44 else 30
            banner_y = max(int(HEIGHT * 0.36), below_y + (28 if size == 40 else 22))
            glass.text(self.screen, self.wave_banner_text, size, (WIDTH // 2, banner_y),
                       col, align="center", bold=True, glow=True, alpha=int(255 * fade))

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
        top = max(inset, getattr(self, "_hud_safe_top", 150) + 18)
        bottom = min(HEIGHT - inset, getattr(self, "_hud_safe_bottom", HEIGHT - 60))

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
