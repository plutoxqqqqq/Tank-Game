"""Pause screen (liquid-glass style): build summary, live stats, target-mode pickers."""
from __future__ import annotations

import pygame
from pygame.math import Vector2

from tankgame.config import *
from tankgame.util import *
from tankgame.ui import glass
from tankgame.data.upgrades import UPGRADES_BY_ID


class PausedScreenMixin:

    def draw_paused(self, events):
        self.draw_background()
        self.draw_obstacles()
        self.draw_entities()
        self.draw_minigame_view()
        glass.frost_backdrop(self.screen, dim=160)
        cx = WIDTH // 2

        glass.text(self.screen, "PAUSED", 72, (cx, 116), glass.GL_TEXT, align="center", bold=True, glow=True)
        glass.text(self.screen, f"Wave {self.wave}   ·   Score {self.player.score:,}   ·   {int(self.survival_time)}s survived",
                   22, (cx, 164), glass.GL_TEXT_DIM, align="center")
        trait = self.player.trait()
        if trait.name:
            glass.text(self.screen, f"{self.player.weapon.name} — {trait.name}: {trait.desc}",
                       20, (cx, 194), glass.GL_ACCENT_2, align="center")

        gap = 18
        btn_w = int(clamp(WIDTH * 0.30, 220, 336))
        side_w = int(min(302, (WIDTH - btn_w - gap * 4) // 2))
        for i, b in enumerate(self.pause_buttons):
            b.rect.width = btn_w
            b.rect.x = cx - btn_w // 2
        panel_y, panel_h = 232, 222
        self.draw_pause_build_summary(pygame.Rect(cx - btn_w // 2 - gap - side_w, panel_y, side_w, panel_h))
        self.draw_pause_stats(pygame.Rect(cx + btn_w // 2 + gap, panel_y, side_w, panel_h))

        mouse_pos = pygame.mouse.get_pos()
        mouse_down = any(e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 for e in events)
        for b in self.pause_buttons:
            b.update(1 / 60, mouse_pos, mouse_down, events)
            b.draw(self.screen, self.font_med)

        picker_y = 456
        if self.player.weapon_id == "nanite_swarm":
            self.draw_mode_picker("DRONE TARGET MODE", DRONE_TARGET_MODES, self.player.drone_target_mode,
                                  lambda m: setattr(self.player, "drone_target_mode", m),
                                  f"{self.player.get_drone_count()} drones", picker_y, mouse_pos, mouse_down)
            picker_y += 74
        if self.player.aimbot:
            self.draw_mode_picker("AIMBOT LEAD MODE", DRONE_TARGET_MODES, self.player.aimbot_mode,
                                  lambda m: setattr(self.player, "aimbot_mode", m),
                                  "shots lead the chosen target", picker_y, mouse_pos, mouse_down)

        glass.text(self.screen, "ESC resumes the run", 18, (cx, HEIGHT - 26),
                   glass.GL_TEXT_FAINT, align="center")

    def draw_mode_picker(self, title, modes, current, apply_mode, note, top, mouse_pos, mouse_down):
        cx = WIDTH // 2
        glass.text(self.screen, title, 20, (cx, top), glass.GL_ACCENT, align="center", bold=True)
        gap = 10
        bw = min(150, (WIDTH - 80 - gap * (len(modes) - 1)) // len(modes))
        bh = 40
        total = len(modes) * bw + (len(modes) - 1) * gap
        x0 = cx - total // 2
        hover_desc = ""
        for i, (mid, name, desc) in enumerate(modes):
            rect = pygame.Rect(x0 + i * (bw + gap), top + 24, bw, bh)
            active = current == mid
            hover = rect.collidepoint(mouse_pos)
            glass.panel(self.screen, rect, radius=12,
                        alpha=50 if active else (40 if hover else 28),
                        accent=glass.GL_GOLD if active else (glass.GL_ACCENT if hover else None),
                        shadow=False)
            glass.text(self.screen, name.upper(), 17, rect.center,
                       glass.GL_GOLD if active else glass.GL_TEXT, align="center", bold=active)
            if hover:
                hover_desc = desc
                if mouse_down and not active:
                    apply_mode(mid)
                    self.audio_play("buy")
        desc_now = next((d for m_id, _n, d in modes if m_id == current), "")
        glass.text(self.screen, f"{note}  ·  {hover_desc or desc_now}", 17,
                   (cx, top + 70), glass.GL_TEXT_DIM, align="center")

    def draw_pause_build_summary(self, box: pygame.Rect):
        glass.panel(self.screen, box, alpha=86, accent=glass.GL_ACCENT, glow=True)
        glass.text(self.screen, "BUILD", 22, (box.x + 16, box.y + 12), glass.GL_ACCENT, bold=True)
        taken = [(up_id, n) for up_id, n in self.player.upgrade_counts.items() if n > 0]
        if not taken:
            glass.text(self.screen, "No upgrades yet.", 18, (box.x + 16, box.y + 44), glass.GL_TEXT_DIM)
            glass.text(self.screen, "Level up to start a build.", 18, (box.x + 16, box.y + 66), glass.GL_TEXT_FAINT)
            return
        rows = box.h // 24 - 2
        for i, (up_id, n) in enumerate(taken[:rows]):
            up = UPGRADES_BY_ID.get(up_id)
            is_ultra = bool(up and up.ultra)
            name = up.name if up else up_id
            y = box.y + 44 + i * 22
            name_x = box.x + 16
            if is_ultra:
                glass.icon_star(self.screen, (box.x + 22, y + 7), 6, glass.GL_GOLD)
                name_x += 16
            glass.text(self.screen, glass.clip_text(name, 18, box.right - 56 - name_x), 18, (name_x, y),
                       glass.GL_GOLD if is_ultra else glass.GL_TEXT)
            if n > 1:
                glass.text(self.screen, f"×{n}", 18, (box.right - 16, y),
                           glass.GL_GOLD if is_ultra else glass.GL_ACCENT, align="right", bold=True)
        if len(taken) > rows:
            glass.text(self.screen, f"+{len(taken) - rows} more", 17, (box.x + 16, box.bottom - 24),
                       glass.GL_TEXT_FAINT)

    def draw_pause_stats(self, box: pygame.Rect):
        glass.panel(self.screen, box, alpha=86, accent=glass.GL_ACCENT, glow=True)
        glass.text(self.screen, "STATS", 22, (box.x + 16, box.y + 12), glass.GL_ACCENT, bold=True)
        who = self.player
        pierce = who.piercing + int(getattr(who.weapon, "base_pierce", 0))
        rows = [
            ("Damage", f"{fmt_amount(who.get_damage())}/shot"),
            ("Fire rate", f"{1.0 / max(0.01, who.get_fire_cooldown()):.1f}/s"),
            ("Crit", f"{who.get_crit_chance() * 100:.0f}%  ×{who.get_crit_mult():.1f}"),
            ("Move speed", f"{who.get_move_speed():.0f}"),
            ("Pierce", str(pierce)),
        ]
        leech = who.get_lifesteal()
        if leech > 0.0:
            rows.append(("Lifesteal", f"1HP/{int(round(1.0 / leech))}dmg"))
        for i, (label, value) in enumerate(rows):
            y = box.y + 44 + i * 22
            glass.text(self.screen, label, 17, (box.x + 16, y), glass.GL_TEXT_DIM)
            glass.text(self.screen, value, 17, (box.right - 16, y), glass.GL_TEXT, align="right", bold=True)
        info_y = box.y + 44 + len(rows) * 22 + 6
        glass.text(self.screen, f"MAP: {self.current_map.name.upper()}", 17,
                   (box.x + 16, info_y), glass.GL_TEXT_FAINT)
        info_y += 20
        if self.wave_mutator is not None:
            glass.text(self.screen, glass.clip_text(f"WAVE: {self.wave_mutator.name}", 17, box.w - 32),
                       17, (box.x + 16, info_y), self.wave_mutator.color)
            info_y += 20
        active = [k for k, v in who.effects.items() if v > 0]
        if active:
            glass.text(self.screen, glass.clip_text("BUFFS: " + ", ".join(k.replace("_", " ").upper() for k in active), 17, box.w - 32),
                       17, (box.x + 16, info_y), glass.GL_GOOD)
