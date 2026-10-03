"""Obstacle generation, spawn placement and wall collisions."""
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




class WorldMixin:

    def _generate_obstacles(self):
        """Build the arena for the current map. Layouts are data (MAPS); each pattern is a small
        generator so adding a brand new map is a one-line data change, not new game code."""
        self.obstacles.clear()
        m = getattr(self, "current_map", None) or map_of(MAP_DEFAULT_ID)
        safe = pygame.Rect(int(ARENA_W / 2 - 260), int(ARENA_H / 2 - 200), 520, 400)

        if m.pattern == "pillars":
            self._gen_pillars(safe, m)
        elif m.pattern == "maze":
            self._gen_maze(safe, m)
        elif m.pattern == "fortress":
            self._gen_fortress(safe, m)
        else:
            self._gen_scatter(safe, m)

        self._ac_obstacles = True

    def _rect_blocked(self, r: pygame.Rect, safe: pygame.Rect) -> bool:
        if r.colliderect(safe):
            return True
        return any(r.inflate(40, 40).colliderect(o) for o in self.obstacles)

    def _gen_scatter(self, safe: pygame.Rect, m: MapDef):
        for _ in range(m.count * 4):
            if len(self.obstacles) >= m.count:
                break
            w = random.randint(m.size_min[0], m.size_max[0])
            h = random.randint(m.size_min[1], m.size_max[1])
            x = random.randint(80, ARENA_W - w - 80)
            y = random.randint(80, ARENA_H - h - 80)
            r = pygame.Rect(x, y, w, h)
            if not self._rect_blocked(r, safe):
                self.obstacles.append(r)

    def _gen_pillars(self, safe: pygame.Rect, m: MapDef):
        step = 360
        size = m.size_max[0]
        for gx in range(2, ARENA_W // step - 1):
            for gy in range(2, ARENA_H // step - 1):
                r = pygame.Rect(gx * step, gy * step, size, size)
                if not self._rect_blocked(r, safe):
                    self.obstacles.append(r)

    def _gen_maze(self, safe: pygame.Rect, m: MapDef):
        """Long horizontal walls with offset doorway columns, so it plays as corridors not clutter."""
        wall_len = random.randint(420, 620)
        thickness = 58
        y = 210
        row = 0
        while y < ARENA_H - 240:
            for i in range(0, ARENA_W - 180, wall_len + 150):
                w = min(wall_len, ARENA_W - i - 90)
                if w < 180:
                    continue
                r = pygame.Rect(i + 60, y, w, thickness)
                if not self._rect_blocked(r, safe):
                    self.obstacles.append(r)
            dx = 60 if row % 2 == 0 else ARENA_W - 200
            r = pygame.Rect(dx, y - 150, thickness, 330)
            if not self._rect_blocked(r, safe):
                self.obstacles.append(r)
            y += 380
            row += 1

    def _gen_fortress(self, safe: pygame.Rect, m: MapDef):
        cx, cy = ARENA_W / 2, ARENA_H / 2
        radius = 430
        blocks = 18
        for i in range(blocks):
            if i in (4, 13):
                continue   # two gates through the ring
            ang = i / blocks * math.tau
            r = pygame.Rect(int(cx + math.cos(ang) * radius - 45),
                            int(cy + math.sin(ang) * radius - 45), 90, 90)
            if not self._rect_blocked(r, safe):
                self.obstacles.append(r)
        for _ in range(m.count):
            w = random.randint(m.size_min[0], m.size_max[0])
            h = random.randint(m.size_min[1], m.size_max[1])
            x = random.randint(80, ARENA_W - w - 80)
            y = random.randint(80, ARENA_H - h - 80)
            r = pygame.Rect(x, y, w, h)
            if not self._rect_blocked(r, safe):
                self.obstacles.append(r)

    # ---------------- UI build ----------------

    def is_world_pos_onscreen(self, world_pos: Vector2, margin: int = 0) -> bool:
        cam = self.cam + self.shake_vec
        x = world_pos.x - cam.x
        y = world_pos.y - cam.y
        return (-margin <= x <= WIDTH + margin) and (-margin <= y <= HEIGHT + margin)

    def has_line_of_sight(self, a: Vector2, b: Vector2) -> bool:
        ax, ay = int(a.x), int(a.y)
        bx, by = int(b.x), int(b.y)
        for r in self.obstacles:
            if r.clipline(ax, ay, bx, by):
                return False
        return True

    # ---------------- Collisions ----------------

    def resolve_player_walls(self):
        for r in self.obstacles:
            self._resolve_circle_rect(self.player.pos, PLAYER_RADIUS, r)

    def resolve_circle_walls(self, enemy: EnemyBase, damping=0.25):
        before = Vector2(enemy.pos)
        for r in self.obstacles:
            self._resolve_circle_rect(enemy.pos, enemy.radius, r)
        moved = enemy.pos - before
        if moved.length_squared() > 0.0001:
            # Slide along the wall: cancel only the velocity heading into it. The old code scaled the
            # whole velocity by (1 - damping), which made enemies stutter and stall on every corner.
            n = moved.normalize()
            into = enemy.vel.dot(n)
            if into < 0:
                enemy.vel -= n * into
            if damping > 0:
                enemy.vel *= (1.0 - damping * 0.05)

    def _resolve_circle_rect(self, cpos: Vector2, radius: float, rect: pygame.Rect):
        closest_x = clamp(cpos.x, rect.left, rect.right)
        closest_y = clamp(cpos.y, rect.top, rect.bottom)
        closest = Vector2(closest_x, closest_y)
        d = cpos - closest
        dist2 = d.length_squared()

        if dist2 < radius * radius:
            dist = math.sqrt(dist2) if dist2 > 1e-6 else 0.0
            if dist == 0.0:
                dx_left = abs(cpos.x - rect.left)
                dx_right = abs(rect.right - cpos.x)
                dy_top = abs(cpos.y - rect.top)
                dy_bottom = abs(rect.bottom - cpos.y)
                m = min(dx_left, dx_right, dy_top, dy_bottom)
                if m == dx_left:
                    cpos.x = rect.left - radius
                elif m == dx_right:
                    cpos.x = rect.right + radius
                elif m == dy_top:
                    cpos.y = rect.top - radius
                else:
                    cpos.y = rect.bottom + radius
            else:
                push = d / dist * (radius - dist)
                cpos += push

        cpos.x = clamp(cpos.x, radius, ARENA_W - radius)
        cpos.y = clamp(cpos.y, radius, ARENA_H - radius)

    def _bullet_seg_bbox(self, bullet: Projectile) -> pygame.Rect:
        """Tight bbox around a bullet's swept segment, used to prune far-away walls."""
        a = bullet.prev_pos
        b = bullet.pos
        pad = bullet.radius + 2
        # Floor/ceil so the box can only ever be too big, never too small - a too-small box would
        # prune a wall the round genuinely touched.
        x0 = math.floor(min(a.x, b.x) - pad)
        y0 = math.floor(min(a.y, b.y) - pad)
        x1 = math.ceil(max(a.x, b.x) + pad)
        y1 = math.ceil(max(a.y, b.y) + pad)
        return pygame.Rect(x0, y0, x1 - x0, y1 - y0)

    def bullet_hits_wall(self, bullet: Projectile) -> bool:
        a = bullet.prev_pos
        b = bullet.pos
        # Broadphase: walls far from this frame's flight path can't be hit, and skipping them keeps
        # a screen-filling spray tank smooth even on dense maps.
        if bullet.no_walls:
            return False   # the Railgun laser goes through cover
        bbox = self._bullet_seg_bbox(bullet)
        for r in self.obstacles:
            if not r.colliderect(bbox):
                continue
            if r.collidepoint(b.x, b.y):
                return True
            if r.clipline((a.x, a.y), (b.x, b.y)):
                return True
        return False

    def _wall_normal(self, pos: Vector2, rect: pygame.Rect) -> Vector2:
        cx = clamp(pos.x, rect.left, rect.right)
        cy = clamp(pos.y, rect.top, rect.bottom)
        d = Vector2(pos.x - cx, pos.y - cy)
        if d.length_squared() > 1e-6:
            return d.normalize()
        # dead centre: bounce off the nearest face
        dxl, dxr = abs(pos.x - rect.left), abs(rect.right - pos.x)
        dyt, dyb = abs(pos.y - rect.top), abs(rect.bottom - pos.y)
        m = min(dxl, dxr, dyt, dyb)
        if m == dxl:
            return Vector2(-1, 0)
        if m == dxr:
            return Vector2(1, 0)
        if m == dyt:
            return Vector2(0, -1)
        return Vector2(0, 1)

    def _reflect_off_wall(self, bullet: Projectile) -> bool:
        """Bank a ricochet round off the wall it just hit."""
        bbox = self._bullet_seg_bbox(bullet)
        for r in self.obstacles:
            if not r.colliderect(bbox):
                continue
            hit = r.collidepoint(bullet.pos.x, bullet.pos.y) or r.clipline(
                (bullet.prev_pos.x, bullet.prev_pos.y), (bullet.pos.x, bullet.pos.y))
            if not hit:
                continue
            # Take the normal from the last position that was *outside* the wall. Reflecting off a
            # point already inside the rect can pick the far face and hurl the round back through
            # the wall, and the round then eats a bounce every frame until it dies.
            ref = bullet.prev_pos if not r.collidepoint(bullet.prev_pos.x, bullet.prev_pos.y) else bullet.pos
            n = self._wall_normal(ref, r)
            bullet.vel = bullet.vel.reflect(n)
            pad = bullet.radius + 2.0
            # Step fully clear of the wall so the same face can't re-trigger next frame.
            if abs(n.x) > abs(n.y):
                bullet.pos.x = r.right + pad if n.x > 0 else r.left - pad
            elif abs(n.y) > 1e-6:
                bullet.pos.y = r.bottom + pad if n.y > 0 else r.top - pad
            if r.collidepoint(bullet.pos.x, bullet.pos.y):
                # Corner graze: still overlapping, so pop out on both axes.
                bullet.pos.x = r.right + pad if (bullet.pos.x - r.right) > (r.left - bullet.pos.x) else r.left - pad
                bullet.pos.y = r.bottom + pad if (bullet.pos.y - r.bottom) > (r.top - bullet.pos.y) else r.top - pad
            # bounces < 0 means "infinite" (the Infinite Bank ultra): never spend the count down.
            if bullet.bounces > 0:
                bullet.bounces -= 1
            return True
        return False

    def _reflect_off_arena(self, bullet: Projectile) -> bool:
        """Bank a round off the arena shell.

        The four arena edges are drawn and felt as walls, so a bank shot has to rebound off them
        too - otherwise a ricochet that runs wide is quietly deleted for leaving the playfield.
        """
        pad = bullet.radius + 2.0
        n: Optional[Vector2] = None
        if bullet.pos.x <= pad:
            n, bullet.pos.x = Vector2(1, 0), pad
        elif bullet.pos.x >= ARENA_W - pad:
            n, bullet.pos.x = Vector2(-1, 0), ARENA_W - pad
        if bullet.pos.y <= pad:
            n, bullet.pos.y = Vector2(0, 1), pad
        elif bullet.pos.y >= ARENA_H - pad:
            n, bullet.pos.y = Vector2(0, -1), ARENA_H - pad
        if n is None:
            return False
        bullet.vel = bullet.vel.reflect(n)
        if bullet.bounces > 0:      # negative = infinite
            bullet.bounces -= 1
        return True

    def _cull_projectiles(self, bullets: List[Projectile],
                          keep_expired: bool = False) -> List[Projectile]:
        """Drop bullets that die, hit a wall, or leave the arena.

        ``keep_expired`` gives a round that just ran out of life one more frame in the list so
        it still gets a collision pass first - otherwise a shot that reaches its target on its
        final frame is deleted instead of connecting.
        """
        kept: List[Projectile] = []
        for b in bullets:
            if not b.alive():
                if keep_expired:
                    kept.append(b)
                elif b.ground_fire:
                    self._spawn_ground_fire(b.pos)
                continue
            if self.bullet_hits_wall(b):
                # Mines park against whatever they touch and keep waiting for a victim.
                if b.mine:
                    if not b.settled:
                        b.settle()
                    kept.append(b)
                    continue
                # bounces != 0 covers both a finite count and the infinite (-1) ultra case.
                if b.bounces != 0 and self._reflect_off_wall(b):
                    kept.append(b)
                    continue
                if b.ground_fire:
                    self._spawn_ground_fire(b.pos)
                continue
            if not (0.0 <= b.pos.x <= ARENA_W and 0.0 <= b.pos.y <= ARENA_H):
                if b.bounces != 0 and self._reflect_off_arena(b):
                    kept.append(b)
                    continue
                continue
            kept.append(b)
        return kept

    def valid_pickup_spawn(self, pos: Vector2, min_player_dist: float = 120.0) -> bool:
        if (pos - self.player.pos).length() < min_player_dist:
            return False
        for r in self.obstacles:
            if r.inflate(22, 22).collidepoint(pos.x, pos.y):
                return False
        return True

    def _find_spawn_point(self, origin: Vector2, distance: float) -> Vector2:
        """A spawn spot that is off-screen and clear of obstacles.

        The old code clamped the candidate into the arena *after* picking an angle, so hugging a
        wall could spawn enemies inside the view - or on top of the player.
        """
        margin = ENEMY_SPAWN_EDGE_MARGIN
        min_offscreen = math.hypot(WIDTH * 0.5, HEIGHT * 0.5) + 90.0
        best: Optional[Vector2] = None
        best_d = -1.0
        for _ in range(ENEMY_SPAWN_ATTEMPTS):
            ang = random.uniform(0, math.tau)
            p = origin + Vector2(math.cos(ang), math.sin(ang)) * distance
            p.x = clamp(p.x, margin, ARENA_W - margin)
            p.y = clamp(p.y, margin, ARENA_H - margin)
            if any(r.inflate(40, 40).collidepoint(p.x, p.y) for r in self.obstacles):
                continue
            d = (p - origin).length()
            if d >= min_offscreen:
                return p
            if d > best_d:
                best_d = d
                best = p
        if best is not None:
            return best
        # Everything was inside an obstacle: fall back to a clamped ring position.
        ang = random.uniform(0, math.tau)
        p = origin + Vector2(math.cos(ang), math.sin(ang)) * distance
        p.x = clamp(p.x, margin, ARENA_W - margin)
        p.y = clamp(p.y, margin, ARENA_H - margin)
        return p

    def resolve_enemy_player_overlap(self, enemy: EnemyBase):
        p = self.player.pos
        d = enemy.pos - p
        min_dist = PLAYER_RADIUS + enemy.radius - PLAYER_ENEMY_MIN_DIST_EPS
        dist2 = d.length_squared()

        if dist2 < (min_dist * min_dist):
            if dist2 < 1e-8:
                ang = ((int(enemy.pos.x) * 73856093) ^ (int(enemy.pos.y) * 19349663)) % 360
                n = Vector2(1, 0).rotate(ang)
                dist = 0.0
            else:
                dist = math.sqrt(dist2)
                n = d / dist

            penetration = (min_dist - dist) if dist > 0 else min_dist
            enemy.pos += n * penetration * PLAYER_ENEMY_PUSH_STRENGTH

            into = enemy.vel.dot(n)
            if into < 0:
                enemy.vel -= n * into * 0.85

            dd = enemy.pos - p
            if dd.length_squared() < (min_dist * min_dist):
                enemy.pos = p + (dd.normalize() if dd.length_squared() > 1e-8 else n) * min_dist

            enemy.pos.x = clamp(enemy.pos.x, enemy.radius, ARENA_W - enemy.radius)
            enemy.pos.y = clamp(enemy.pos.y, enemy.radius, ARENA_H - enemy.radius)

    # ---------------- Shooting + special weapon mechanics ----------------

    def roll_map(self) -> MapDef:
        """Every run rolls one of the maps you have unlocked, so layouts keep changing."""
        owned = [m for m in MAPS if self.save.map_unlocks.get(m.id, False)]
        if not owned:
            owned = [map_of(MAP_DEFAULT_ID)]
        return random.choice(owned)

    # =====================================================
    # MINIGAMES
    # =====================================================
