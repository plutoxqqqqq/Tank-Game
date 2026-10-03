"""Tank Game Rebirth - live in-game cheat menu.

This module is *not* part of the game. Start the legit game first::

    python main.py

then, while it is running, inject the menu from a second terminal::

    python inject.py

The injector finds the running game process and hands it this module's ``install``
function, which hooks the live ``Game``/``Player`` classes and paints the menu onto
the existing pygame frame. RightShift (or F1) toggles it from any screen.

Because nothing is written to the game's source, closing and reopening ``main.py``
always gives you the untouched, legit game again until you inject once more.

The injector uses ``CreateRemoteThread`` + ``WriteProcessMemory`` to queue a call in the
game's interpreter (via ``Py_AddPendingCall``). That is real process injection, so some
antivirus products may flag it - allow ``python.exe`` if the injection is blocked.
"""
from __future__ import annotations

import ctypes
import json
import math
import os
import random
import struct
import sys
import time
import traceback

import pygame
from pygame.math import Vector2

import tankgame.config as tkcfg
from tankgame.config import (
    ARENA_W, ARENA_H, XP_ORB_VALUE_BASE, HEALTH_PACK_AMOUNT, BULLET_RADIUS_ENEMY,
    RANGED_BULLET_LIFETIME, C_EBULLET, C_XP, C_HEALTH,
    CHASER_SPEED_BASE, RANGED_SPEED_BASE, TANK_SPEED_BASE, SPRINTER_SPEED_BASE,
    DASHER_SPEED_BASE, PINK_HP_BASE, PINK_SPEED_BASE,
)
from tankgame.entities.pickup import Pickup
from tankgame.entities.projectile import Projectile
from tankgame.entities.enemies import (
    Chaser, Ranged, Tank as EnemyTank, Sprinter, Dasher, Pink, Boss,
)

_MENU = None
_CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".inject_cfg")

ACCENT = (86, 226, 200)
ACCENT_2 = (255, 104, 168)
TEXT = (236, 242, 252)
DIM = (150, 162, 184)
FAINT = (104, 116, 138)
OK = (110, 232, 150)
PANEL = (15, 19, 27, 246)
PANEL_EDGE = (62, 76, 100, 255)
HEADER = (20, 26, 36, 255)
CARD = (24, 30, 40, 234)
CARD_HOVER = (34, 43, 57, 246)
CARD_EDGE = (48, 61, 81, 255)
CHILD = (20, 25, 34, 224)
TRACK = (48, 58, 74)
LIST = (22, 28, 38, 250)

CATEGORIES = ["Combat", "Movement", "States", "Tanks"]

SPAWN_OPTIONS = [
    "XP Orb", "Health Pack", "Damage Boost", "Rapid Fire", "Speed Boost", "Shield",
    "Drone Range", "Chaser", "Ranged", "Tank", "Sprinter", "Dasher", "Pink", "Boss",
    "Obstacle", "Player Shot", "Enemy Shot",
]

META_KEYS = ["meta_damage", "meta_move", "meta_hp", "meta_xp", "meta_dash",
             "meta_armor", "meta_bulletspeed"]


class _FalseKeys:
    def __getitem__(self, _k):
        return False

    def __len__(self):
        return 0

    def __iter__(self):
        return iter(())


class _DashProxy:
    """Wraps the real key array but pretends SPACE is held."""

    def __init__(self, real):
        self._real = real

    def __getitem__(self, k):
        if k == pygame.K_SPACE:
            return True
        return self._real[k]


_FALSE_KEYS = _FalseKeys()


def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


# ---------------------------------------------------------------------------
# Module definitions
# ---------------------------------------------------------------------------

def _toggle(mid, cat, name, desc, default=False, indent=False):
    return dict(id=mid, cat=cat, kind="toggle", name=name, desc=desc,
                value=default, indent=indent)


def _slider(mid, cat, name, desc, lo, hi, default, step=0.1, fmt="{:.1f}",
            suffix="", indent=False):
    return dict(id=mid, cat=cat, kind="slider", name=name, desc=desc, value=default,
                min=lo, max=hi, step=step, fmt=fmt, suffix=suffix, indent=indent)


def _action(mid, cat, name, desc, indent=False):
    return dict(id=mid, cat=cat, kind="action", name=name, desc=desc,
                value=False, indent=indent)


def _dropdown(mid, cat, name, desc, options, default, indent=False):
    return dict(id=mid, cat=cat, kind="dropdown", name=name, desc=desc,
                value=default, options=options, indent=indent)


def _slider_action(mid, cat, name, desc, lo, hi, default, step, fmt, suffix=""):
    return dict(id=mid, cat=cat, kind="slider_action", name=name, desc=desc,
                value=default, min=lo, max=hi, step=step, fmt=fmt, suffix=suffix,
                indent=False)


def _base_modules():
    return [
        # Combat ------------------------------------------------------------
        _toggle("projectileaura", "Combat", "ProjectileAura",
                "Automatically shoots enemies around you"),
        _slider("projectile_range", "Combat", "Range", "Aura targeting range",
                80, 1400, 420, 10, "{:.0f}", "px", indent=True),
        _dropdown("projectile_sort", "Combat", "Target Sorting",
                  "How the aura picks its target",
                  ["Distance", "Mouse", "Angle", "Health", "Threat"], "Distance", indent=True),
        _toggle("godmode", "Combat", "GodMode", "You cannot take damage or die"),
        _toggle("onetap", "Combat", "OneTap", "One hit kills normal enemies"),
        _toggle("alwayscrit", "Combat", "AlwaysCrit", "Every shot is a critical hit"),
        _toggle("aimassist", "Combat", "AimAssist", "Aimbot - snaps your aim onto the best target"),
        _toggle("aura", "Combat", "Aura", "Constantly damages enemies around you"),
        _slider("aura_range", "Combat", "Range", "How far the Aura reaches",
                60, 800, 200, 10, "{:.0f}", "px", indent=True),
        _slider("aura_damage", "Combat", "Damage", "Aura damage per second",
                5, 5000, 350, 5, "{:.0f}", "dps", indent=True),
        _toggle("autowin", "Combat", "AutoWin", "Aims, shoots, moves and levels up for you"),

        # Movement ----------------------------------------------------------
        _slider("speed", "Movement", "Speed", "Walk speed multiplier",
                0.5, 8, 1.0, 0.1, "{:.1f}", "x"),
        _toggle("dashexploit", "Movement", "DashExploit", "Hold SPACE to dash endlessly"),
        _slider("dashtime", "Movement", "DashExtender", "Seconds added to each dash",
                0, 2.0, 0.0, 0.05, "{:.2f}", "s", indent=True),
        _toggle("velocity", "Movement", "Velocity", "Removes recoil and knockback"),

        # States ------------------------------------------------------------
        _action("upgrade", "States", "Upgrade", "Grant enough XP to level up once"),
        _action("wave", "States", "Wave", "Advance to the next wave"),
        _dropdown("spawn", "States", "Spawn", "Spawn an entity, pickup or object",
                  SPAWN_OPTIONS, "XP Orb"),
        _slider_action("coins", "States", "Coins", "Add coins to your save",
                       0, 1000000, 10000, 1000, "{:.0f}"),
        _action("unlockall", "States", "UnlockEverything", "Unlock all tanks, maps and cosmetics"),
        _action("saveeditor", "States", "SaveEditor", "Edit coins and meta upgrades"),
        _action("uninject", "States", "Uninject", "Remove every cheat and trace from the game"),
    ]


TANK_MODULES = {
    "pistol": ("Deadeye Protocol", "Every shot is a guaranteed critical"),
    "cannon": ("Siege Breaker", "The blast fires on every enemy pierced"),
    "minigun": ("Gatling God", "No spin-up, full fire rate instantly"),
    "shotgun": ("Endless Shells", "Pellets never expire"),
    "rocket": ("Meteor Barrage", "Every shot calls down a meteor"),
    "sniper": ("Dead Reckoning", "Shots auto-aim with lead"),
    "flamethrower": ("Ashen Ground", "Shots scorch the floor"),
    "windscreen_wiper": ("Cyclone", "Five times the pellet output"),
    "electricity": ("Overload", "Every chain strikes twice"),
    "tank": ("Executioner", "Shots execute non-boss enemies"),
    "gravity_well": ("Collapse", "Enemies snap straight onto the orb"),
    "prism": ("Fractal Shards", "Shards split again on impact"),
    "nanite_swarm": ("Swarm Unleashed", "Drones roam free and you gain +10 drones"),
    "railgun": ("Twin Lance", "A mirrored shot fires backwards too"),
    "homing": ("Ghost Tracker", "Shots auto-aim with lead"),
    "hypnosis": ("Total Control", "Brainwashing never wears off"),
    "ricochet": ("Absolute Bounce", "Rebounds off walls, edges and enemies"),
    "mine_layer": ("Homing Mines", "Armed mines creep toward enemies"),
    "siphon": ("Blood Price", "Whoever damages you is detonated"),
}


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

class InjectMenu:
    def __init__(self, game):
        global _MENU
        _MENU = self
        self.game = game
        self.visible = False
        self.cat = "Combat"
        self.scroll = 0.0
        self.hover = None
        self.dragging = None
        self._mouse_down = False
        self._aim_target = None
        self._t = 0.0
        self._fps = 60.0
        self.offset = [0, 0]
        self._dragging_panel = False
        self._drag_grab = (0, 0)
        self.dropdown_open = None
        self.modal = None
        self._dd_rect = None
        self._dd_option_rects = []
        self._modal_items = []
        self._rows = []
        self._tab_rects = []
        self._fonts = {}
        self._panel_cache = None
        self._panel_key = None

        self.modules = {}
        self.order = []
        for m in _base_modules():
            self.modules[m["id"]] = m
            self.order.append(m["id"])
        for tank_id, (name, desc) in TANK_MODULES.items():
            mid = "tank_" + tank_id
            m = _toggle(mid, "Tanks", name, desc)
            m["tank"] = tank_id
            self.modules[mid] = m
        self._load_cfg()

    # -------------------------------------------------------------- config
    def _load_cfg(self):
        try:
            with open(_CFG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return
        if not isinstance(data, dict):
            return
        for mid, value in data.items():
            m = self.modules.get(mid)
            if not m:
                continue
            if m["kind"] in ("slider", "slider_action"):
                try:
                    m["value"] = _clamp(float(value), m["min"], m["max"])
                except (TypeError, ValueError):
                    pass
            elif m["kind"] == "toggle":
                m["value"] = bool(value)
            elif m["kind"] == "dropdown":
                if value in m["options"]:
                    m["value"] = value

    def _save_cfg(self):
        try:
            data = {m["id"]: m["value"] for m in self.modules.values()
                    if m["kind"] in ("toggle", "slider", "slider_action", "dropdown")}
            with open(_CFG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except OSError:
            pass

    def get(self, mid):
        m = self.modules.get(mid)
        return bool(m["value"]) if m else False

    def value(self, mid):
        m = self.modules.get(mid)
        return float(m["value"]) if m and m["kind"] in ("slider", "slider_action") else 1.0

    def dvalue(self, mid):
        m = self.modules.get(mid)
        return str(m["value"]) if m and m["kind"] == "dropdown" else ""

    # -------------------------------------------------------------- helpers
    def _flag_any(self, player, attr, mids):
        base_attr = "_tinj_base_" + attr
        if not hasattr(player, base_attr):
            setattr(player, base_attr, bool(getattr(player, attr, False)))
        base = getattr(player, base_attr)
        setattr(player, attr, base or any(self.get(m) for m in mids))

    def _scalar(self, player, attr, apply_fn):
        base_attr = "_tinj_base_" + attr
        if not hasattr(player, base_attr):
            setattr(player, base_attr, getattr(player, attr, 0.0))
        setattr(player, attr, apply_fn(getattr(player, base_attr)))

    def _pick_target(self, g, sort, max_range=0.0):
        player = g.player
        best, best_score = None, None
        for e in g.enemies:
            try:
                if (not e.alive()) or e.is_charmed():
                    continue
                delta = e.pos - player.pos
                dist = delta.length()
                if max_range > 0.0 and dist > max_range:
                    continue
                if sort == "Mouse":
                    score = -(e.pos - g.mouse_world).length()
                elif sort == "Angle":
                    score = player.aim_dir.dot(delta.normalize()) if dist > 1e-6 else 1.0
                elif sort == "Health":
                    score = -e.hp
                elif sort == "Threat":
                    score = e.hp
                else:
                    score = -dist
                if best_score is None or score > best_score:
                    best, best_score = e, score
            except Exception:
                continue
        return best

    def aim_point(self, g, player, target):
        try:
            lead = g.predict_intercept(player.pos, target, max(60.0, player.get_bullet_speed()))
        except Exception:
            lead = target.pos - player.pos
        if lead.length_squared() < 1e-6:
            return Vector2(target.pos)
        return player.pos + lead

    def auto_move(self, g, player):
        target = self._aim_target
        if target is None:
            best, best_d = None, None
            for p in g.pickups:
                d = (p.pos - player.pos).length_squared()
                if best_d is None or d < best_d:
                    best_d, best = d, p
            if best is None:
                return Vector2(0, 0)
            v = best.pos - player.pos
            return v.normalize() if v.length_squared() > 1e-6 else Vector2(0, 0)
        delta = target.pos - player.pos
        dist = delta.length()
        if dist > 280:
            v = delta
        elif dist < 180:
            v = -delta
        else:
            v = Vector2(-delta.y, delta.x) * (1 if math.sin(self._t * 3.0) > 0 else -1)
        return v.normalize() if v.length_squared() > 1e-6 else Vector2(0, 0)

    def dash_keys(self, keys, player):
        if self._aim_target is not None and (self._aim_target.pos - player.pos).length() < 250:
            return _DashProxy(keys)
        if player.hp < player.max_hp * 0.5:
            return _DashProxy(keys)
        return keys

    # -------------------------------------------------------------- frame
    def handle_frame(self, dt, events):
        self._t += dt
        self._fps += ((1.0 / dt if dt > 0 else 60.0) - self._fps) * 0.1

        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_RSHIFT, pygame.K_F1):
                    self.visible = not self.visible
                    self.dropdown_open = None
                    if self.visible:
                        self.scroll = 0.0
                elif e.key == pygame.K_ESCAPE and self.visible:
                    if self.modal is not None:
                        self.modal = None
                    elif self.dropdown_open is not None:
                        self.dropdown_open = None
                    else:
                        self.visible = False
            elif e.type == pygame.MOUSEWHEEL and self.visible and self.modal is None and self.dropdown_open is None:
                self.scroll -= e.y * 46.0
                self.scroll = max(0.0, self.scroll)

        self._layout()

        mx, my = pygame.mouse.get_pos()
        down = bool(pygame.mouse.get_pressed(3)[0])
        clicked = down and not self._mouse_down
        released = (not down) and self._mouse_down
        self._mouse_down = down
        self.hover = None

        if self.visible:
            if self.modal is not None:
                self._modal_input(mx, my, clicked)
            elif self.dropdown_open is not None:
                self._dropdown_input(mx, my, clicked)
            else:
                self._main_input(mx, my, clicked, down, released, dt)

        if released:
            self.dragging = None
            self._dragging_panel = False

        self._apply(self.game, dt)

    # -------------------------------------------------------------- input
    def _main_input(self, mx, my, clicked, down, released, dt):
        rect = self.rect
        if clicked and self.close_rect.collidepoint(mx, my):
            self.visible = False
            return
        if clicked and rect.collidepoint(mx, my) and my < rect.y + 54:
            self._dragging_panel = True
            self._drag_grab = (mx - rect.x, my - rect.y)
            return
        if self._dragging_panel and down:
            base_x = (tkcfg.WIDTH - rect.width) // 2
            base_y = (tkcfg.HEIGHT - rect.height) // 2
            self.offset[0] = _clamp(mx - self._drag_grab[0] - base_x,
                                    -base_x + 8, tkcfg.WIDTH - rect.width - base_x - 8)
            self.offset[1] = _clamp(my - self._drag_grab[1] - base_y,
                                    -base_y + 8, tkcfg.HEIGHT - rect.height - base_y - 8)
            return

        for cat, r in self._tab_rects:
            if r.collidepoint(mx, my):
                self.hover = ("tab", cat)
                if clicked:
                    self.cat = cat
                    self.scroll = 0.0
                return

        if not self.content_rect.collidepoint(mx, my):
            return
        for m, r in self._rows:
            if not r.collidepoint(mx, my):
                continue
            self.hover = ("row", m["id"])
            if m["kind"] in ("slider", "slider_action"):
                if clicked:
                    self.dragging = m["id"]
                if self.dragging == m["id"]:
                    self._set_slider(m, r, mx)
                if m["kind"] == "slider_action" and clicked and self._run_rect(m, r).collidepoint(mx, my):
                    self.dragging = None
                    self._run(m["id"])
                return
            if clicked:
                if m["kind"] == "toggle":
                    m["value"] = not m["value"]
                    self._save_cfg()
                elif m["kind"] == "action":
                    self._run(m["id"])
                elif m["kind"] == "dropdown":
                    self.dropdown_open = None if self.dropdown_open == m["id"] else m["id"]
            return
        if self.dragging is not None and down:
            for m, r in self._rows:
                if m["id"] == self.dragging:
                    self._set_slider(m, r, mx)
                    break

    def _dropdown_input(self, mx, my, clicked):
        if not clicked:
            return
        for opt, r in self._dd_option_rects:
            if r.collidepoint(mx, my):
                m = self.modules[self.dropdown_open]
                m["value"] = opt
                self._save_cfg()
                if m["id"] == "spawn":
                    self._spawn(self.game, opt)
                self.dropdown_open = None
                return
        self.dropdown_open = None

    def _modal_input(self, mx, my, clicked):
        if not clicked:
            return
        for kind, key, minus, plus, _value in self._modal_items:
            if minus.collidepoint(mx, my):
                self._edit_save(key, -1)
                return
            if plus.collidepoint(mx, my):
                self._edit_save(key, +1)
                return
        if self._modal_max_rect.collidepoint(mx, my):
            for key in META_KEYS:
                self.game.save.shop_levels[key] = 50
            self.game.save.save()
            return
        if self._modal_reset_rect.collidepoint(mx, my):
            self.game.save.coins = 0
            for key in META_KEYS:
                self.game.save.shop_levels[key] = 0
            self.game.save.save()
            return
        if self._modal_close_rect.collidepoint(mx, my):
            self.modal = None
            return

    def _edit_save(self, key, direction):
        save = self.game.save
        if key == "coins":
            save.coins = max(0, save.coins + direction * 1000)
        else:
            level = max(0, min(50, int(save.shop_levels.get(key, 0)) + direction))
            save.shop_levels[key] = level
        save.save()

    def _set_slider(self, m, r, mx):
        x0, x1 = self._track(m, r)
        frac = _clamp((mx - x0) / max(1, (x1 - x0)), 0.0, 1.0)
        value = m["min"] + frac * (m["max"] - m["min"])
        step = m.get("step", 0.1)
        value = round(value / step) * step
        value = _clamp(value, m["min"], m["max"])
        if abs(value - m["value"]) > 1e-9:
            m["value"] = value
            self._save_cfg()

    def _run(self, mid):
        g = self.game
        if mid == "upgrade":
            g.player.xp += g.player.xp_to_next
        elif mid == "wave":
            g.wave += 1
        elif mid == "coins":
            g.save.coins += int(self.value("coins"))
            g.save.save()
        elif mid == "unlockall":
            for key in list(g.save.weapon_unlocks):
                g.save.weapon_unlocks[key] = True
            for key in list(g.save.map_unlocks):
                g.save.map_unlocks[key] = True
            for key in list(g.save.cosmetics_unlocked):
                g.save.cosmetics_unlocked[key] = True
            g.save.save()
        elif mid == "saveeditor":
            self.modal = "save"
            self._layout_modal()
        elif mid == "uninject":
            uninstall()

    # -------------------------------------------------------------- spawning
    def _spawn(self, g, option):
        player = g.player
        pos = player.pos + Vector2(random.uniform(-90, 90), random.uniform(-90, 90))
        pos.x = _clamp(pos.x, 40, ARENA_W - 40)
        pos.y = _clamp(pos.y, 40, ARENA_H - 40)
        try:
            if option == "XP Orb":
                g.pickups.append(Pickup(pos, "xp", XP_ORB_VALUE_BASE * 3))
            elif option == "Health Pack":
                g.pickups.append(Pickup(pos, "health", HEALTH_PACK_AMOUNT + 2))
            elif option in ("Damage Boost", "Rapid Fire", "Speed Boost", "Shield", "Drone Range"):
                kind = option.lower().replace(" ", "_")
                g.pickups.append(Pickup(pos, "power", 0, kind))
            elif option == "Chaser":
                g.enemies.append(Chaser(pos, hp=42, speed=CHASER_SPEED_BASE))
            elif option == "Ranged":
                g.enemies.append(Ranged(pos, hp=58, speed=RANGED_SPEED_BASE))
            elif option == "Tank":
                g.enemies.append(EnemyTank(pos, hp=125, speed=TANK_SPEED_BASE))
            elif option == "Sprinter":
                g.enemies.append(Sprinter(pos, hp=28, speed=SPRINTER_SPEED_BASE))
            elif option == "Dasher":
                g.enemies.append(Dasher(pos, hp=72, speed=DASHER_SPEED_BASE))
            elif option == "Pink":
                g.enemies.append(Pink(pos, hp=PINK_HP_BASE, speed=PINK_SPEED_BASE))
            elif option == "Boss":
                g.enemies.append(Boss(pos, hp=1400, speed=74.0, wave_index=g.wave))
            elif option == "Obstacle":
                size = random.randint(90, 180)
                g.obstacles.append(pygame.Rect(int(pos.x - size / 2), int(pos.y - size / 2),
                                               size, size))
            elif option == "Player Shot":
                g.spawn_player_shot(player)
            elif option == "Enemy Shot":
                away = Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
                if away.length_squared() < 1e-6:
                    away = Vector2(1, 0)
                aim = (player.pos - pos)
                if aim.length_squared() < 1e-6:
                    aim = Vector2(1, 0)
                for i in range(5):
                    off = pos + away.normalize() * (i * 26)
                    g.enemy_projectiles.append(Projectile(
                        off, aim.normalize() * 320.0, damage=1, owner="enemy",
                        color=C_EBULLET, radius=BULLET_RADIUS_ENEMY,
                        lifetime=RANGED_BULLET_LIFETIME))
        except Exception:
            pass

    # -------------------------------------------------------------- apply
    def _apply(self, g, dt):
        player = getattr(g, "player", None)
        if player is None:
            return
        playing = getattr(g, "state", "") == "playing"

        self._flag_any(player, "always_crit", ("alwayscrit", "tank_pistol"))
        self._flag_any(player, "instant_kill", ("onetap", "tank_tank"))
        self._flag_any(player, "aimbot", ("tank_sniper", "tank_homing"))
        self._flag_any(player, "bullet_life_inf", ("tank_shotgun",))
        self._flag_any(player, "spin_instant", ("tank_minigun",))
        self._flag_any(player, "meteor_shot", ("tank_rocket",))
        self._flag_any(player, "ground_fire", ("tank_flamethrower",))
        self._flag_any(player, "chain_double", ("tank_electricity",))
        self._flag_any(player, "pull_instant", ("tank_gravity_well",))
        self._flag_any(player, "split_recursive", ("tank_prism",))
        self._flag_any(player, "drone_free_roam", ("tank_nanite_swarm",))
        self._flag_any(player, "twin_shot", ("tank_railgun",))
        self._flag_any(player, "charm_forever", ("tank_hypnosis",))
        self._flag_any(player, "bounce_enemies", ("tank_ricochet",))
        self._flag_any(player, "infinite_bounces", ("tank_ricochet",))
        self._flag_any(player, "mine_homing", ("tank_mine_layer",))
        self._flag_any(player, "retribution", ("tank_siphon",))
        self._flag_any(player, "pierce_splash", ("tank_cannon",))
        self._flag_any(player, "pellet_uncap", ("tank_windscreen_wiper",))

        self._scalar(player, "recoil_mult",
                     lambda base: 0.0 if self.get("velocity") else base)
        self._scalar(player, "dash_time_bonus",
                     lambda base: base + self.value("dashtime"))
        self._scalar(player, "pellet_mul",
                     lambda base: base * 5.0 if self.get("tank_windscreen_wiper") else base)
        self._scalar(player, "drones_add",
                     lambda base: int(base) + 10 if self.get("tank_nanite_swarm") else int(base))

        if self.get("autowin"):
            player.hp = player.max_hp
            if g.state == "levelup" and g.level_choices:
                g.pick_upgrade(g.level_choices[0])
            if g.state == "gameover":
                g.start_run()

        aim = None
        if self.get("aimassist") or self.get("autowin"):
            aim = self._pick_target(g, "Distance", 0.0)
        self._aim_target = aim

        if not playing:
            return

        if self.get("projectileaura"):
            target = self._pick_target(g, self.dvalue("projectile_sort"),
                                       self.value("projectile_range"))
            if target is not None and player.shoot_timer <= 0.0:
                point = self.aim_point(g, player, target)
                direction = point - player.pos
                if direction.length_squared() > 1e-6:
                    player.aim_dir = direction.normalize()
                g.spawn_player_shot(player)
                player.shoot_timer = player.get_fire_cooldown()

        if self.get("aura"):
            radius = self.value("aura_range")
            dps = self.value("aura_damage")
            if dps > 0:
                r2 = radius * radius
                for enemy in list(g.enemies):
                    if enemy.alive() and (enemy.pos - player.pos).length_squared() <= r2:
                        enemy.take_damage(dps * dt, Vector2(0, 0), 0.0,
                                          weapon_id=player.weapon_id, from_player=True)

        if self.get("dashexploit"):
            player.dash_cd_timer = 0.0

    # -------------------------------------------------------------- layout
    def _layout(self):
        W, H = tkcfg.WIDTH, tkcfg.HEIGHT
        pw = min(880, W - 40)
        ph = min(620, H - 40)
        px = (W - pw) // 2 + self.offset[0]
        py = (H - ph) // 2 + self.offset[1]
        self.rect = pygame.Rect(int(px), int(py), pw, ph)
        self.close_rect = pygame.Rect(self.rect.right - 44, self.rect.y + 12, 30, 30)

        tab_w, tab_h, gap = 132, 38, 8
        total = len(CATEGORIES) * tab_w + (len(CATEGORIES) - 1) * gap
        tx = self.rect.centerx - total // 2
        self._tab_rects = []
        for cat in CATEGORIES:
            self._tab_rects.append((cat, pygame.Rect(tx, self.rect.y + 58, tab_w, tab_h)))
            tx += tab_w + gap

        self.content_rect = pygame.Rect(self.rect.x + 14, self.rect.y + 106,
                                        pw - 28, ph - 106 - 38)

        current = self._current_modules()
        y = self.content_rect.y + 4 - self.scroll
        total_h = 0
        self._rows = []
        for m in current:
            h = self._row_height(m)
            x = self.content_rect.x + (22 if m.get("indent") else 0)
            w = self.content_rect.width - (22 if m.get("indent") else 0)
            self._rows.append((m, pygame.Rect(x, int(y), w, h)))
            y += h + 8
            total_h += h + 8
        self.max_scroll = max(0.0, total_h - self.content_rect.height + 8)
        if self.scroll > self.max_scroll:
            self.scroll = self.max_scroll

        self._layout_dropdown()
        if self.modal is not None:
            self._layout_modal()

    def _current_modules(self):
        if self.cat != "Tanks":
            return [self.modules[mid] for mid in self.order
                    if self.modules[mid]["cat"] == self.cat]
        tank_id = getattr(self.game.player, "weapon_id", "pistol")
        mid = "tank_" + tank_id
        if tank_id in TANK_MODULES and mid in self.modules:
            return [self.modules[mid]]
        return []

    def _layout_dropdown(self):
        self._dd_rect = None
        self._dd_option_rects = []
        if self.dropdown_open is None:
            return
        for m, r in self._rows:
            if m["id"] != self.dropdown_open:
                continue
            opts = m["options"]
            cols = 3 if len(opts) > 8 else 1
            rows = (len(opts) + cols - 1) // cols
            cell_w = (r.width - 28 - (cols - 1) * 4) // cols
            height = rows * 30 + 8
            top = r.bottom + 4
            if top + height > self.rect.bottom - 44:
                top = r.y - 4 - height
            top = _clamp(top, self.rect.y + 58, self.rect.bottom - 44 - height)
            self._dd_rect = pygame.Rect(r.x + 10, top, r.width - 20, height)
            for i, opt in enumerate(opts):
                cx, cy = i % cols, i // cols
                self._dd_option_rects.append((
                    opt,
                    pygame.Rect(self._dd_rect.x + 4 + cx * (cell_w + 4),
                                self._dd_rect.y + 4 + cy * 30, cell_w, 28)))
            return

    def _layout_modal(self):
        self._modal_items = []
        m = self.rect.inflate(-80, -70)
        self._modal_rect = pygame.Rect(m.x, m.y, m.width, m.height)
        self._modal_close_rect = pygame.Rect(self._modal_rect.right - 118,
                                             self._modal_rect.bottom - 48, 100, 32)
        self._modal_max_rect = pygame.Rect(self._modal_rect.x + 24,
                                           self._modal_rect.bottom - 48, 120, 32)
        self._modal_reset_rect = pygame.Rect(self._modal_rect.x + 154,
                                             self._modal_rect.bottom - 48, 120, 32)
        y = self._modal_rect.y + 58
        save = self.game.save
        rows = [("coins", "Coins", f"{save.coins:,}")]
        for key in META_KEYS:
            label = key.replace("meta_", "").replace("_", " ").title()
            rows.append((key, label, str(int(save.shop_levels.get(key, 0)))))
        for key, label, value in rows:
            minus = pygame.Rect(self._modal_rect.right - 128, y, 30, 28)
            plus = pygame.Rect(self._modal_rect.right - 50, y, 30, 28)
            self._modal_items.append((None, key, minus, plus, (label, value)))
            y += 36

    def _row_height(self, m):
        return {"toggle": 54, "dropdown": 54, "action": 52,
                "slider": 64, "slider_action": 74}[m["kind"]]

    @staticmethod
    def _track(m, r):
        return r.x + 16, r.right - 96

    def _run_rect(self, m, r):
        return pygame.Rect(r.right - 92, r.y + 12, 76, 28)

    # -------------------------------------------------------------- drawing
    def _font(self, size, bold=False):
        key = (size, bold)
        f = self._fonts.get(key)
        if f is None:
            f = pygame.font.Font(None, size)
            f.set_bold(bold)
            self._fonts[key] = f
        return f

    def _text(self, surf, text, size, pos, color, align="left", bold=False):
        img = self._font(size, bold).render(text, True, color)
        r = img.get_rect()
        if align == "right":
            r.topright = pos
        elif align == "center":
            r.center = pos
        else:
            r.topleft = pos
        surf.blit(img, r)
        return r

    @staticmethod
    def _round(target, rect, color, radius=12, border=None, width=1):
        rect = pygame.Rect(rect)
        if rect.width <= 0 or rect.height <= 0:
            return
        surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(surf, color, surf.get_rect(), border_radius=radius)
        if border is not None:
            pygame.draw.rect(surf, border, surf.get_rect(), width, border_radius=radius)
        target.blit(surf, rect.topleft)

    def draw(self, screen):
        if not self.visible:
            return
        if self._panel_key != (self.rect.width, self.rect.height):
            self._panel_cache = self._build_panel(self.rect.width, self.rect.height)
            self._panel_key = (self.rect.width, self.rect.height)

        W, H = tkcfg.WIDTH, tkcfg.HEIGHT
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((4, 6, 10, 158))
        screen.blit(overlay, (0, 0))

        screen.blit(self._panel_cache, self.rect.topleft)
        self._draw_header(screen)
        self._draw_tabs(screen)

        screen.set_clip(self.content_rect)
        for m, r in self._rows:
            if r.bottom < self.content_rect.y or r.top > self.content_rect.bottom:
                continue
            self._draw_row(screen, m, r)
        screen.set_clip(None)

        if self.dropdown_open is not None:
            self._draw_dropdown(screen)

        self._draw_footer(screen)
        if self.modal is not None:
            self._draw_modal(screen)

    def _build_panel(self, w, h):
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(panel, PANEL, panel.get_rect(), border_radius=18)
        pygame.draw.rect(panel, PANEL_EDGE, panel.get_rect(), 1, border_radius=18)
        glow = pygame.Surface((w - 4, 3), pygame.SRCALPHA)
        for i in range(glow.get_width()):
            t = i / max(1, glow.get_width() - 1)
            glow.set_at((i, 0), (int(ACCENT[0] * (1 - t) + ACCENT_2[0] * t),
                                 int(ACCENT[1] * (1 - t) + ACCENT_2[1] * t),
                                 int(ACCENT[2] * (1 - t) + ACCENT_2[2] * t), 210))
            glow.set_at((i, 1), (int(ACCENT[0] * (1 - t) + ACCENT_2[0] * t),
                                 int(ACCENT[1] * (1 - t) + ACCENT_2[1] * t),
                                 int(ACCENT[2] * (1 - t) + ACCENT_2[2] * t), 90))
        panel.blit(glow, (2, 2))
        return panel

    def _draw_header(self, screen):
        r = self.rect
        self._text(screen, "TANK // INJECT", 26, (r.x + 22, r.y + 13), TEXT, bold=True)
        active = sum(1 for m in self.modules.values()
                     if m["kind"] == "toggle" and m.get("value"))
        self._text(screen, f"{active} active", 16, (r.right - 60, r.y + 20),
                   OK if active else DIM, align="right")
        hot = self.close_rect.collidepoint(pygame.mouse.get_pos())
        self._round(screen, self.close_rect,
                    (64, 32, 38, 240) if hot else (36, 24, 30, 220),
                    8, (210, 96, 116, 255) if hot else (90, 60, 70, 255))
        pygame.draw.line(screen, TEXT if hot else DIM,
                         (self.close_rect.x + 10, self.close_rect.y + 10),
                         (self.close_rect.right - 10, self.close_rect.bottom - 10), 2)
        pygame.draw.line(screen, TEXT if hot else DIM,
                         (self.close_rect.right - 10, self.close_rect.y + 10),
                         (self.close_rect.x + 10, self.close_rect.bottom - 10), 2)

    def _draw_tabs(self, screen):
        for cat, r in self._tab_rects:
            selected = cat == self.cat
            hot = self.hover == ("tab", cat)
            if selected:
                self._round(screen, r, (26, 48, 48, 244), 11, ACCENT)
            else:
                self._round(screen, r, CARD_HOVER if hot else HEADER, 11,
                            CARD_EDGE if hot else None)
            self._text(screen, cat, 19, r.center, TEXT if (selected or hot) else DIM,
                       align="center", bold=selected)

    def _draw_row(self, screen, m, r):
        hot = self.hover == ("row", m["id"])
        base = CHILD if m.get("indent") else CARD
        hover = CARD_HOVER
        bg, edge = (hover, CARD_EDGE) if hot else (base, CARD_EDGE if not m.get("indent") else None)
        if m["kind"] == "action" and m.get("_flash"):
            bg, edge = (34, 62, 56, 250), ACCENT
        self._round(screen, r, bg, 12, edge)

        self._text(screen, m["name"], 20 if not m.get("indent") else 18,
                   (r.x + 16, r.y + 9), TEXT, bold=True)
        desc_color = FAINT if not m.get("indent") else (86, 98, 118)
        self._text(screen, m["desc"], 14, (r.x + 16, r.y + 30), desc_color)

        if m["kind"] == "toggle":
            self._draw_toggle(screen, m, r)
        elif m["kind"] == "slider":
            self._draw_slider(screen, m, r, with_run=False)
        elif m["kind"] == "slider_action":
            self._draw_slider(screen, m, r, with_run=True)
        elif m["kind"] == "action":
            btn = self._run_rect(m, r)
            self._round(screen, btn, (30, 66, 58, 252), 8, ACCENT)
            self._text(screen, "RUN", 17, btn.center, ACCENT, align="center", bold=True)
        elif m["kind"] == "dropdown":
            value = str(m["value"])
            self._text(screen, value, 17, (r.right - 34, r.centery - 9), ACCENT, align="right")
            cy = r.centery
            pygame.draw.polygon(screen, DIM, [
                (r.right - 26, cy - 3), (r.right - 12, cy - 3), (r.right - 19, cy + 4)])

    def _draw_toggle(self, screen, m, r):
        track = pygame.Rect(r.right - 72, r.centery - 13, 52, 26)
        on = bool(m["value"])
        pygame.draw.rect(screen, ACCENT if on else TRACK, track, border_radius=13)
        cx = track.x + (39 if on else 13)
        pygame.draw.circle(screen, (244, 250, 255), (cx, track.centery), 9)
        pygame.draw.circle(screen, (20, 30, 34), (cx, track.centery), 9, 1)

    def _draw_slider(self, screen, m, r, with_run):
        x0, x1 = self._track(m, r)
        ty = r.bottom - 18
        pygame.draw.rect(screen, TRACK, pygame.Rect(x0, ty - 3, x1 - x0, 6), border_radius=3)
        frac = (m["value"] - m["min"]) / max(1e-9, (m["max"] - m["min"]))
        fx = int(x0 + frac * (x1 - x0))
        pygame.draw.rect(screen, ACCENT, pygame.Rect(x0, ty - 3, max(2, fx - x0), 6), border_radius=3)
        pygame.draw.circle(screen, (244, 250, 255), (fx, ty), 7)
        pygame.draw.circle(screen, ACCENT, (fx, ty), 7, 2)
        text = m["fmt"].format(m["value"]) + m.get("suffix", "")
        value_x = r.right - (104 if with_run else 16)
        self._text(screen, text, 18, (value_x, r.y + 12), ACCENT, align="right")
        if with_run:
            btn = self._run_rect(m, r)
            self._round(screen, btn, (30, 66, 58, 252), 8, ACCENT)
            self._text(screen, "RUN", 17, btn.center, ACCENT, align="center", bold=True)

    def _draw_dropdown(self, screen):
        if self._dd_rect is None:
            return
        self._round(screen, self._dd_rect, LIST, 12, CARD_EDGE)
        mouse = pygame.mouse.get_pos()
        m = self.modules[self.dropdown_open]
        for opt, r in self._dd_option_rects:
            hot = r.collidepoint(mouse)
            if opt == m["value"]:
                self._round(screen, r, (26, 48, 48, 240), 8, ACCENT)
            elif hot:
                self._round(screen, r, (34, 43, 57, 240), 8)
            self._text(screen, opt, 17, (r.x + 12, r.centery - 8),
                       ACCENT if opt == m["value"] else (TEXT if hot else DIM))

    def _draw_footer(self, screen):
        r = self.rect
        self._text(screen, "RightShift / F1 close   -   ESC hides", 15,
                   (r.x + 22, r.bottom - 26), FAINT)
        self._text(screen, f"{self._fps:4.0f} FPS", 15, (r.right - 22, r.bottom - 26),
                   FAINT, align="right")

    def _draw_modal(self, screen):
        self._round(screen, self._modal_rect, (18, 23, 32, 252), 16, PANEL_EDGE)
        self._text(screen, "SAVE EDITOR", 24, (self._modal_rect.x + 24, self._modal_rect.y + 18),
                   TEXT, bold=True)
        self._text(screen, "coins and permanent meta upgrades", 14,
                   (self._modal_rect.x + 26, self._modal_rect.y + 40), FAINT)
        for _kind, key, minus, plus, info in self._modal_items:
            label, value = info
            self._text(screen, label, 19, (minus.x - 12, minus.y + 4), DIM, align="right")
            self._text(screen, value, 19, ((minus.right + plus.x) // 2, minus.y + 4),
                       TEXT, align="center", bold=True)
            self._round(screen, minus, (36, 26, 30, 240), 7, (120, 70, 80, 255))
            self._text(screen, "-", 20, minus.center, (255, 150, 150), align="center", bold=True)
            self._round(screen, plus, (26, 50, 46, 240), 7, ACCENT)
            self._text(screen, "+", 20, plus.center, ACCENT, align="center", bold=True)
        self._round(screen, self._modal_max_rect, (30, 66, 58, 250), 8, ACCENT)
        self._text(screen, "MAX ALL", 17, self._modal_max_rect.center, ACCENT,
                   align="center", bold=True)
        self._round(screen, self._modal_reset_rect, (36, 26, 30, 240), 8, (120, 70, 80, 255))
        self._text(screen, "RESET", 17, self._modal_reset_rect.center, (255, 150, 150),
                   align="center", bold=True)
        self._round(screen, self._modal_close_rect, CARD_HOVER, 8, CARD_EDGE)
        self._text(screen, "CLOSE", 17, self._modal_close_rect.center, TEXT,
                   align="center", bold=True)


# ---------------------------------------------------------------------------
# Live installation / removal (runs inside the game process)
# ---------------------------------------------------------------------------

_INSTALLED = False
_ORIG = {}


def _ensure_menu(game):
    """Return this game's menu, building it on first use."""
    menu = getattr(game, "_tinj_menu", None)
    if menu is None:
        try:
            menu = InjectMenu(game)
        except Exception:
            traceback.print_exc()
            menu = False
        game._tinj_menu = menu
    return None if menu is False else menu


def _frame_dt(game):
    now = time.perf_counter()
    last = getattr(game, "_tinj_last_frame", None)
    game._tinj_last_frame = now
    if last is None:
        return 1.0 / 60.0
    return _clamp(now - last, 0.0, 0.05)


def install():
    """Hook the running game so the cheat menu is driven from its own loop.

    Called inside the game process (see the injector in ``_main``). Idempotent.
    """
    global _INSTALLED
    if _INSTALLED:
        return
    try:
        from tankgame.game import Game
        from tankgame.entities.player import Player
    except Exception:
        traceback.print_exc()
        return

    orig = {
        "handle_events": Game.handle_events,
        "update_playing": Game.update_playing,
        "damage_player": Game.damage_player,
        "contact": Game._handle_enemy_contact_player,
        "player_update": Player.update,
        "move_speed": Player.get_move_speed,
        "event_get": pygame.event.get,
        "flip": pygame.display.flip,
    }

    def handle_events(g):
        menu = _ensure_menu(g)
        if menu is None:
            return orig["handle_events"](g)
        events = orig["event_get"]()
        menu.handle_frame(_frame_dt(g), events)
        if menu.visible:
            return events   # the menu owns input while it is open
        real_get = orig["event_get"]
        pygame.event.get = lambda *a, **k: events
        try:
            return orig["handle_events"](g)
        finally:
            pygame.event.get = real_get

    def update_playing(g, dt, events):
        menu = _ensure_menu(g)
        if menu is not None and menu.visible:
            real_key = pygame.key.get_pressed
            real_mouse = pygame.mouse.get_pressed
            pygame.key.get_pressed = lambda: _FALSE_KEYS
            pygame.mouse.get_pressed = lambda *a, **k: (False, False, False)
            try:
                return orig["update_playing"](g, dt, events)
            finally:
                pygame.key.get_pressed = real_key
                pygame.mouse.get_pressed = real_mouse
        return orig["update_playing"](g, dt, events)

    def damage_player(g, amount, source=None):
        if _MENU is not None and _MENU.get("godmode"):
            return
        return orig["damage_player"](g, amount, source)

    def handle_contact(g):
        menu = _MENU
        if menu is not None and menu.get("godmode"):
            return
        if menu is not None and menu.get("velocity"):
            keep = Vector2(g.player.vel)
            result = orig["contact"](g)
            g.player.vel = keep
            return result
        return orig["contact"](g)

    def player_update(p, dt, game, move, mouse_world, mouse_buttons, keys):
        menu = _MENU
        if menu is not None:
            if menu._aim_target is not None and (menu.get("aimassist") or menu.get("autowin")):
                mouse_world = menu.aim_point(game, p, menu._aim_target)
            if menu.get("autowin"):
                move = menu.auto_move(game, p)
                mouse_buttons = (True, False, False)
                keys = menu.dash_keys(keys, p)
        return orig["player_update"](p, dt, game, move, mouse_world, mouse_buttons, keys)

    def move_speed(p):
        base = orig["move_speed"](p)
        return base * (_MENU.value("speed") if _MENU is not None else 1.0)

    def flip(*a, **k):
        menu = _MENU
        if menu is not None:
            try:
                menu.draw(menu.game.screen)
            except Exception:
                traceback.print_exc()
        return orig["flip"](*a, **k)

    Game.handle_events = handle_events
    Game.update_playing = update_playing
    Game.damage_player = damage_player
    Game._handle_enemy_contact_player = handle_contact
    Player.update = player_update
    Player.get_move_speed = move_speed
    pygame.display.flip = flip

    _ORIG.clear()
    _ORIG.update(orig)
    _ORIG["Game"] = Game
    _ORIG["Player"] = Player
    _INSTALLED = True
    print("[inject] cheat installed - press RightShift (or F1) in-game")


def uninstall():
    """Restore every hooked method and player field, and scrub the cheat's files."""
    global _MENU, _INSTALLED
    Game = _ORIG.get("Game")
    Player = _ORIG.get("Player")
    if Game is not None:
        Game.handle_events = _ORIG["handle_events"]
        Game.update_playing = _ORIG["update_playing"]
        Game.damage_player = _ORIG["damage_player"]
        Game._handle_enemy_contact_player = _ORIG["contact"]
    if Player is not None:
        Player.update = _ORIG["player_update"]
        Player.get_move_speed = _ORIG["move_speed"]
    pygame.event.get = _ORIG.get("event_get", pygame.event.get)
    pygame.display.flip = _ORIG.get("flip", pygame.display.flip)

    game = getattr(_MENU, "game", None)
    player = getattr(game, "player", None) if game is not None else None
    if player is not None:
        for attr in ("always_crit", "instant_kill", "aimbot", "bullet_life_inf",
                     "spin_instant", "meteor_shot", "ground_fire", "chain_double",
                     "pull_instant", "split_recursive", "drone_free_roam", "twin_shot",
                     "charm_forever", "bounce_enemies", "infinite_bounces", "mine_homing",
                     "retribution", "pierce_splash", "pellet_uncap", "recoil_mult",
                     "dash_time_bonus", "pellet_mul", "drones_add"):
            base_attr = "_tinj_base_" + attr
            if hasattr(player, base_attr):
                try:
                    setattr(player, attr, getattr(player, base_attr))
                except Exception:
                    pass
                try:
                    delattr(player, base_attr)
                except Exception:
                    pass

    if game is not None:
        try:
            game.add_float_text(game.player.pos + Vector2(0, -40), "UNINJECTED", OK, life=1.2)
        except Exception:
            pass
        game._tinj_menu = None

    _MENU = None
    _INSTALLED = False

    try:
        if os.path.exists(_CFG_PATH):
            os.remove(_CFG_PATH)
    except OSError:
        pass
    try:
        import glob as _glob
        cache_dir = os.path.join(os.path.dirname(_CFG_PATH), "__pycache__")
        for path in _glob.glob(os.path.join(cache_dir, "inject.*.pyc")):
            os.remove(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Process injector (runs in the *separate* terminal that launched inject.py)
# ---------------------------------------------------------------------------

def _find_target_pid(explicit=None):
    if explicit is not None:
        return int(explicit)
    import psutil
    me = os.getpid()
    root = os.path.dirname(os.path.abspath(__file__)).lower()
    best = None
    best_score = -1
    for proc in psutil.process_iter(["pid", "name", "cmdline", "cwd"]):
        try:
            if proc.info["pid"] == me:
                continue
            name = (proc.info.get("name") or "").lower()
            if not name.startswith("python"):
                continue
            cmdline = " ".join(str(a) for a in (proc.info.get("cmdline") or []))
            if "main.py" not in cmdline or "inject.py" in cmdline:
                continue
            score = 0
            if root in cmdline.lower():
                score += 2
            cwd = proc.info.get("cwd") or ""
            if cwd.lower() == root:
                score += 2
            if score > best_score:
                best, best_score = proc.info["pid"], score
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return best


def _inject_code(pid, code):
    """Queue ``code`` to run on the main thread of ``pid`` via Py_AddPendingCall."""
    import win32process

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    k32.VirtualAllocEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                   ctypes.c_uint32, ctypes.c_uint32]
    k32.VirtualAllocEx.restype = ctypes.c_void_p
    k32.WriteProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    k32.CreateRemoteThread.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                                       ctypes.POINTER(ctypes.c_uint32)]
    k32.CreateRemoteThread.restype = ctypes.c_void_p
    k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    k32.GetExitCodeThread.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    k32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
    k32.GetModuleHandleW.restype = ctypes.c_void_p
    k32.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    k32.GetProcAddress.restype = ctypes.c_void_p

    process_all = 0x1F0FFF
    mem_commit_reserve = 0x3000
    page_execute_readwrite = 0x40

    dll_name = f"python{sys.version_info.major}{sys.version_info.minor}.dll"
    hproc = k32.OpenProcess(process_all, False, pid)
    if not hproc:
        raise OSError(f"OpenProcess failed ({ctypes.get_last_error()}). Try running as admin.")
    try:
        remote_base = None
        for module in win32process.EnumProcessModules(hproc):
            try:
                path = win32process.GetModuleFileNameEx(hproc, module)
            except Exception:
                continue
            if os.path.basename(path).lower() == dll_name:
                remote_base = int(module)
                break
        if remote_base is None:
            raise OSError(f"{dll_name} is not loaded in PID {pid}; is that the game?")

        local_base = int(k32.GetModuleHandleW(dll_name))
        run = int(k32.GetProcAddress(local_base, b"PyRun_SimpleString") or 0)
        add = int(k32.GetProcAddress(local_base, b"Py_AddPendingCall") or 0)
        if not run or not add:
            raise OSError("this Python build does not expose the injection entry points")

        remote_run = remote_base + (run - local_base)
        remote_add = remote_base + (add - local_base)

        address = k32.VirtualAllocEx(hproc, None, 0x1000, mem_commit_reserve,
                                     page_execute_readwrite)
        if not address:
            raise OSError(f"VirtualAllocEx failed ({ctypes.get_last_error()})")
        code_addr = address + 0x200
        payload = code.encode("utf-8") + b"\x00"

        # mov rcx, PyRun_SimpleString ; mov rdx, code ; mov rax, Py_AddPendingCall ; jmp rax
        shell = (
            b"\x48\xB9" + struct.pack("<Q", remote_run)
            + b"\x48\xBA" + struct.pack("<Q", code_addr)
            + b"\x48\xB8" + struct.pack("<Q", remote_add)
            + b"\xFF\xE0"
        )

        written = ctypes.c_size_t(0)
        if not k32.WriteProcessMemory(hproc, address, shell, len(shell), ctypes.byref(written)):
            raise OSError(f"WriteProcessMemory (stub) failed ({ctypes.get_last_error()})")
        if not k32.WriteProcessMemory(hproc, code_addr, payload, len(payload),
                                      ctypes.byref(written)):
            raise OSError(f"WriteProcessMemory (code) failed ({ctypes.get_last_error()})")

        tid = ctypes.c_uint32(0)
        thread = k32.CreateRemoteThread(hproc, None, 0, address, None, 0, ctypes.byref(tid))
        if not thread:
            raise OSError(f"CreateRemoteThread failed ({ctypes.get_last_error()})")
        try:
            k32.WaitForSingleObject(thread, 5000)
            result = ctypes.c_uint32(0)
            k32.GetExitCodeThread(thread, ctypes.byref(result))
            if result.value != 0:
                raise OSError("Py_AddPendingCall refused the request")
        finally:
            k32.CloseHandle(thread)
    finally:
        k32.CloseHandle(hproc)


def _main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    explicit = None
    if "--pid" in argv:
        try:
            explicit = int(argv[argv.index("--pid") + 1])
        except (IndexError, ValueError):
            print("Usage: python inject.py [--pid N]")
            return 2

    if sys.platform != "win32":
        print("Live injection currently supports Windows only.")
        return 1
    if sys.maxsize <= 2 ** 32:
        print("Live injection requires 64-bit Python.")
        return 1
    try:
        import psutil  # noqa: F401
        import win32process  # noqa: F401
    except Exception:
        print("Missing dependency. Install it with:  pip install psutil pywin32")
        return 1

    pid = _find_target_pid(explicit)
    if pid is None:
        print("Tank Game is not running.")
        print("Start it first:              python main.py")
        print("Then, in a second terminal:  python inject.py")
        return 1

    root = os.path.dirname(os.path.abspath(__file__))
    bootstrap = (
        "import sys\n"
        f"sys.path.insert(0, {root!r})\n"
        "import inject as _tinj\n"
        "_tinj.install()\n"
    )
    try:
        _inject_code(pid, bootstrap)
    except Exception as exc:  # noqa: BLE001
        print(f"Injection failed: {exc}")
        return 1
    print(f"Injected into Tank Game (PID {pid}).")
    print("Press RightShift (or F1) in the game to open the menu.")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
