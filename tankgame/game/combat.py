"""Projectile handling: hits, damage, gravity/homing, charm and allies."""
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




class CombatMixin:

    def credit_player_damage(self, amount: float):
        """Single funnel for damage the player deals: run stats plus lifesteal.

        Every source (bullets, blast, chains, burn) goes through here, so a tank that drains HP back
        works with all of them instead of only the one the code happened to remember.
        """
        if amount <= 0.0:
            return
        self.run_stats["damage"] += amount
        healed = self.player.bank_lifesteal(amount)
        if healed:
            self.add_float_text(self.player.pos + Vector2(0, -30), f"+{healed} HP", C_OK, life=0.7)
            self.audio_play("powerup", 0.05)

    def credit_burn_damage(self, amount: float):
        """Burn ticks are fractional; bank them so challenges/score still count them."""
        self.credit_player_damage(amount)
        self.burn_credit += amount
        whole = int(self.burn_credit)
        if whole > 0:
            self.burn_credit -= whole
            self.update_challenges("damage", whole)

    def spawn_player_shot(self, player: Player):
        ac = getattr(self, "anticheat", None)
        if ac is not None and not ac.allow_shot(player):
            return
        # Immortal rounds (Endless Shells / Absolute Bounce) get a much larger allowance and are
        # recycled last, so they actually behave like they never die instead of quietly expiring
        # against the normal projectile cap.
        immortal = bool(player.bullet_life_inf)
        cap = MAX_PROJECTILES_IMMORTAL if immortal else MAX_PROJECTILES
        if len(self.projectiles) >= cap:
            # Heavy spray tanks used to go completely silent the moment the field hit the cap,
            # which read as the gun "not firing". Recycle the oldest plain round instead, so the
            # stream stays continuous (mines are kept - they are the point of their tank).
            recycled = False
            for i, old in enumerate(self.projectiles):
                if old.mine or old.life > 1.0e8:
                    continue
                del self.projectiles[i]
                recycled = True
                break
            if not recycled:
                for i, old in enumerate(self.projectiles):
                    if not old.mine:
                        del self.projectiles[i]
                        recycled = True
                        break
            if not recycled:
                return
        w = player.weapon
        dmg = player.get_damage()
        # Mines park where they land, whichever tank borrowed the mine card.
        mine = player.drops_mines()
        bspd = 0.0 if mine else player.get_bullet_speed()
        life = player.get_bullet_lifetime()

        is_crit = False
        if player.always_crit:
            # Pistol ultra: every single shot crits, no roll.
            dmg = dmg * player.get_crit_mult()
            is_crit = True
        else:
            crit_chance = player.get_crit_chance()
            if crit_chance > 0 and random.random() < crit_chance:
                dmg = dmg * player.get_crit_mult()
                is_crit = True

        base_dir = Vector2(player.aim_dir)
        if base_dir.length_squared() < 1e-6:
            base_dir = Vector2(1, 0)

        # Aimbot (Sniper/Homing ultra): fire at where the target *will be*, not where it is.
        # Mines have no barrel to aim, so they are left alone.
        if player.aimbot and not mine:
            tgt = self.aimbot_target(player)
            if tgt is not None:
                lead = self.predict_intercept(player.pos, tgt, bspd)
                if lead.length_squared() > 1e-6:
                    base_dir = lead.normalize()

        # Mirror shot (Railgun "Twin Lance"): the same volley fired the opposite way too.
        dirs = [base_dir]
        if player.twin_shot and not mine:
            dirs.append(-base_dir)

        # recoil (tank traits and cards can scale it)
        player.vel -= base_dir * player.get_recoil() * RECOIL_MULT

        # angles / firing pattern
        if w.radial > 0:
            # Radial volley: an even ring of shots around the compass.
            count = max(1, w.radial)
            step = 360.0 / count
            angles = [i * step for i in range(count)]
        else:
            n = player.get_pellets()
            spread = player.get_spread()
            if n <= 1 or spread <= 0.0:
                angles = [0.0]
            else:
                angles = [lerp(-spread * 0.5, spread * 0.5, i / (n - 1)) for i in range(n)]

        slow, slow_time = player.get_slow()
        burn_dps, burn_time = player.get_burn()
        bounces = player.get_bounces()
        splash = w.splash_radius * player.get_splash_mult() + player.splash_add
        if player.pierce_splash and splash <= 0.0:
            # Cannon "Siege Breaker" borrowed by a splash-less tank still detonates on each pierce.
            splash = PIERCE_SPLASH_FALLBACK_RADIUS
        if splash < 1.0:
            splash = 0.0
        pull, pull_radius = player.get_pull()
        if player.pull_instant and pull <= 0.0:
            # Gravity Well "Collapse" borrowed by a tank with no innate pull still drags targets in.
            pull, pull_radius = 1.0, max(pull_radius, 175.0)
        split_count, split_mult = player.get_split()
        charm = player.get_charm()
        overpen = player.get_overpen()
        homing, homing_range = player.get_homing()
        no_walls = bool(getattr(w, "pierces_walls", False))
        beam = float(getattr(w, "beam", 0.0))
        pierce_total = 0 if mine else max(0, player.piercing + int(getattr(w, "base_pierce", 0)))
        base_col = self.get_bullet_color()
        ground_fire = bool(player.ground_fire) and not mine
        pierce_splash = bool(player.pierce_splash) and not mine
        bounce_enemies = bool(player.bounce_enemies) and not mine
        # Mines are not bullets: none of the bullet payloads (split/charm/pull) apply to them.
        # Homing mines keep their homing so they can drift once armed.
        if mine:
            split_count, charm, pull, pull_radius, overpen = 0, 0.0, 0.0, 0.0, 0.0
            no_walls, beam = False, 0.0
            if not player.mine_homing:
                homing = 0.0

        for d0 in dirs:
            for ang in angles:
                if len(self.projectiles) >= cap:
                    break
                dirn = d0.rotate(ang)
                col = base_col if not is_crit else (255, 240, 120)
                b = Projectile(
                    player.pos + dirn * (PLAYER_RADIUS + 7),
                    dirn * bspd,
                    dmg,
                    owner="player",
                    color=col,
                    radius=w.bullet_radius,
                    lifetime=life,
                    pierce=pierce_total,
                    splash_radius=splash,
                    slow=slow,
                    slow_time=slow_time,
                    burn_dps=burn_dps,
                    burn_time=burn_time,
                    bounces=bounces,
                    mine=mine,
                    pull=pull,
                    pull_radius=pull_radius,
                    split=split_count,
                    split_mult=split_mult,
                    charm=charm,
                    overpen_frac=overpen,
                    homing=homing,
                    homing_range=homing_range,
                    no_walls=no_walls,
                    beam=beam,
                    split_recursive=bool(player.split_recursive),
                    bounce_enemies=bounce_enemies,
                    ground_fire=ground_fire,
                )
                b.pierce_splash = pierce_splash
                self.projectiles.append(b)
                self.run_stats["shots"] += 1

        # Mega Mines: leave a live mine behind you so you can kite and carpet the arena.
        if mine and player.mine_trail > 0.0 and len(self.projectiles) < cap:
            self.projectiles.append(Projectile(
                player.pos - base_dir * 22.0, Vector2(0, 0), dmg, owner="player",
                color=base_col, radius=w.bullet_radius, lifetime=life,
                splash_radius=splash, mine=True,
            ))
            self.run_stats["shots"] += 1

        # Meteor Barrage (Rocket ultra): every shot also calls a rock down on the aim point.
        if player.meteor_shot and not mine:
            self._call_meteor(player.pos + base_dir * 360.0)

        self.audio_play("shoot")

    def aimbot_target(self, player):
        """Pick the enemy an aimbot shot should lead, using the player's chosen target mode."""
        mode = player.aimbot_mode
        mouse = getattr(self, "mouse_world", None)
        aim = player.aim_dir
        best = None
        best_score = None
        for e in self.enemies:
            if (not e.alive()) or e.is_charmed():
                continue
            if mode == "mouse" and mouse is not None:
                score = -(e.pos - mouse).length_squared()
            elif mode == "angle":
                to = e.pos - player.pos
                if to.length_squared() < 1e-6 or aim.length_squared() < 1e-6:
                    score = 1.0
                else:
                    score = aim.normalize().dot(to.normalize())
            elif mode == "health":
                score = -e.hp
            elif mode == "threat":
                score = e.hp
            else:
                score = -(e.pos - player.pos).length_squared()
            if best is None or score > best_score:
                best, best_score = e, score
        return best

    def predict_intercept(self, origin: Vector2, target, proj_speed: float) -> Vector2:
        """Lead a moving target: where to aim so the round meets it, not follows it."""
        rel = target.pos - origin
        if proj_speed <= 1e-6:
            return rel
        rel_vel = getattr(target, "vel", Vector2(0, 0))
        t = rel.length() / proj_speed
        for _ in range(4):
            predicted = target.pos + rel_vel * t
            t = (predicted - origin).length() / proj_speed
        return (target.pos + rel_vel * t) - origin

    def _call_meteor(self, pos: Vector2):
        """Meteor Barrage: a player-owned meteor with a short telegraph and huge damage."""
        pos = Vector2(pos)
        pos.x = clamp(pos.x, 60, ARENA_W - 60)
        pos.y = clamp(pos.y, 60, ARENA_H - 60)
        self.meteors.append(Meteor(pos, METEOR_SHOT_TELEGRAPH, radius=METEOR_SHOT_RADIUS,
                                   friendly=True, damage=METEOR_SHOT_DAMAGE))

    def tesla_chain(self, start_enemy: EnemyBase, base_damage: float, chains: int, chain_range: float):
        hit = {start_enemy}
        current = start_enemy
        for _ in range(chains):
            best = None
            best_d2 = (chain_range * chain_range)
            for e in self.enemies:
                if e in hit or (not e.alive()) or e.is_charmed():
                    continue
                d2 = (e.pos - current.pos).length_squared()
                if d2 < best_d2:
                    best_d2 = d2
                    best = e
            if best is None:
                break

            hit.add(best)
            dmg = max(3, int(round(base_damage * self.player.get_chain_mult())))
            dirn = (best.pos - current.pos)
            if dirn.length_squared() > 0.001:
                dirn = dirn.normalize()
            else:
                dirn = Vector2(1, 0)
            best.take_damage(dmg, dirn, 70.0, weapon_id=self.player.weapon_id, from_player=True)
            self.run_stats["hits"] += 1
            self.credit_player_damage(dmg)
            self.update_mastery(self.player.weapon_id, hits=1)
            self.update_challenges("damage", dmg)
            self.add_float_text(best.pos + Vector2(0, -10), str(dmg), C_ACCENT, damage=True)
            self._spawn_hit_particles(best.pos, (200, 220, 255))
            current = best

    # ---------------- Spawning ----------------

    def _rocket_explode(self, b: Projectile):
        if b.splash_radius <= 0:
            return
        center = Vector2(b.pos)
        rad2 = b.splash_radius * b.splash_radius
        for e in self.enemies:
            if (not e.alive()) or e.is_charmed():
                continue
            d2 = (e.pos - center).length_squared()
            if d2 <= rad2:
                t = 1.0 - math.sqrt(max(0.0, d2)) / max(1.0, b.splash_radius)
                dmg = max(2, int(b.damage * (0.55 + 0.45 * t)))
                # Tank "Executioner" ultra: the blast executes anything that is not a boss.
                if self.player.instant_kill and not isinstance(e, Boss):
                    dmg = max(dmg, int(math.ceil(e.hp)))
                knock_dir = (e.pos - center)
                if knock_dir.length_squared() > 0.001:
                    knock_dir = knock_dir.normalize()
                else:
                    knock_dir = Vector2(1, 0)
                e.take_damage(dmg, knock_dir, 110.0, weapon_id=self.player.weapon_id, from_player=True)
                self.run_stats["hits"] += 1
                self.credit_player_damage(dmg)
                self.update_mastery(self.player.weapon_id, hits=1)
                self.update_challenges("damage", dmg)
                self.add_float_text(e.pos + Vector2(0, -10), str(dmg), C_WARN, damage=True)
        self._spawn_hit_particles(center, self.get_explosion_color())
        self.shake = max(self.shake, 6.0)

    def _update_drones(self, dt):
        """Keeps the Nanite Swarm drones in sync with the tank's (upgradeable) drone count.

        Every drone is re-indexed against the *current* count each frame, so taking "+1 Drone"
        spaces the new ring evenly instead of stacking a drone on top of an existing one.
        """
        want = self.player.get_drone_count()
        if want <= 0:
            if self.drones:
                self.drones.clear()
            return
        while len(self.drones) < want:
            self.drones.append(Drone(len(self.drones), want, self.player.pos))
        while len(self.drones) > want:
            self.drones.pop()
        self.drone_phase = (self.drone_phase + 2.1 * dt) % math.tau
        total = len(self.drones)
        for i, d in enumerate(self.drones):
            d.index = i
            d.total = total
            d.update(dt, self)

    def _apply_gravity_pull(self, dt):
        """Gravity Well orbs haul enemies in while they fly, clumping crowds for the blast.

        This moves the enemy's *position*, not just its velocity. Enemies overwrite their own velocity
        every frame, so the old velocity-only pull was almost completely damped out and the orbs
        felt like they did nothing.
        """
        for b in self.projectiles:
            if b.owner != "player" or b.pull <= 0.0 or b.pull_radius <= 0.0:
                continue
            r2 = b.pull_radius * b.pull_radius
            for e in self.enemies:
                if not e.alive() or e.is_charmed():
                    continue
                d = b.pos - e.pos
                d2 = d.length_squared()
                if 1e-6 < d2 < r2:
                    dist = math.sqrt(d2)
                    if self.player.pull_instant:
                        # Gravity Well "Collapse" ultra: the enemy is yanked straight onto the orb.
                        e.pos = Vector2(b.pos)
                    else:
                        falloff = 0.35 + 0.65 * (1.0 - dist / b.pull_radius)
                        speed = b.pull * GRAVITY_PULL_SPEED * falloff
                        e.pos += (d / dist) * speed * dt
                    e.pos.x = clamp(e.pos.x, e.radius, ARENA_W - e.radius)
                    e.pos.y = clamp(e.pos.y, e.radius, ARENA_H - e.radius)

    def _drift_mines(self, dt):
        """Mine Layer "Homing Mines" ultra: armed mines creep toward the nearest enemy."""
        if not self.player.mine_homing:
            return
        for b in self.projectiles:
            if not b.mine or not b.settled:
                continue
            best = None
            best_d2 = float("inf")
            for e in self.enemies:
                if not e.alive() or e.is_charmed():
                    continue
                d2 = (e.pos - b.pos).length_squared()
                if d2 < best_d2:
                    best_d2, best = d2, e
            if best is None:
                continue
            d = best.pos - b.pos
            if d.length_squared() > 1e-6:
                b.pos += d.normalize() * DRONE_FREE_ROAM_SPEED * dt

    def _spawn_ground_fire(self, pos: Vector2):
        """Flamethrower "Ashen Ground" ultra: leave a lingering burn patch on the floor."""
        if len(self.hazards) >= HAZARD_MAX:
            self.hazards.pop(0)
        self.hazards.append({
            "pos": Vector2(pos),
            "radius": GROUND_FIRE_RADIUS,
            "dps": GROUND_FIRE_DPS * self.player.damage_mult,
            "life": GROUND_FIRE_LIFE,
            "life_max": GROUND_FIRE_LIFE,
        })

    def _update_hazards(self, dt):
        """Tick scorched ground: anything standing in it keeps burning."""
        if not self.hazards:
            return
        for h in self.hazards:
            h["life"] -= dt
            r2 = h["radius"] * h["radius"]
            for e in self.enemies:
                if (not e.alive()) or e.is_charmed():
                    continue
                if (e.pos - h["pos"]).length_squared() <= r2:
                    tick = h["dps"] * dt
                    e.hp -= tick
                    e._ac_dmg += tick
                    e.last_hit_by_player = True
                    e.last_hit_weapon_id = self.player.weapon_id
                    self.credit_burn_damage(tick)
                    e.apply_burn(h["dps"] * 0.5, 0.6)
        self.hazards = [h for h in self.hazards if h["life"] > 0.0]

    def _apply_homing(self, dt):
        """Homing rounds curve toward the nearest enemy; better cards = a harder turn."""
        for b in self.projectiles:
            if b.homing <= 0.0 or b.homing_range <= 0.0:
                continue
            speed = b.vel.length()
            if speed < 1e-6:
                continue
            target = None
            best_d2 = b.homing_range * b.homing_range
            for e in self.enemies:
                if not e.alive() or e.is_charmed():
                    continue
                d2 = (e.pos - b.pos).length_squared()
                if d2 < best_d2:
                    best_d2 = d2
                    target = e
            if target is None:
                continue
            want = target.pos - b.pos
            if want.length_squared() < 1e-6:
                continue
            want = want.normalize() * speed
            # Capped per frame so even a stacked ultra bends the round instead of snapping to it.
            turn = clamp(HOMING_TURN_RATE * b.homing * dt, 0.0, HOMING_TURN_CAP)
            b.vel = b.vel.lerp(want, turn)

    def _spawn_prism_shards(self, b: Projectile, at: Vector2):
        """Prism rounds burst into a fan of weaker shards the first time they connect."""
        from_angle = math.atan2(b.vel.y, b.vel.x)
        spread = math.radians(150.0)
        speed = b.vel.length() * 0.9
        for i in range(b.split):
            if len(self.projectiles) >= MAX_PROJECTILES:
                break
            t = 0.0 if b.split <= 1 else (i / (b.split - 1) - 0.5)
            ang = from_angle + t * spread
            dirn = Vector2(math.cos(ang), math.sin(ang))
            shard = Projectile(
                Vector2(at), dirn * speed, damage=b.damage * b.split_mult,
                owner="player", color=b.color, radius=3, lifetime=0.55, pierce=1,
            )
            # Prism "Fractal Shards" ultra: the shards themselves can split again (depth-bounded so
            # one impact can never spiral into an unbounded spray).
            if b.split_recursive and b.split_depth < 2:
                shard.split = max(1, b.split)
                shard.split_mult = b.split_mult * 0.8
                shard.split_recursive = True
                shard.split_depth = b.split_depth + 1
            self.projectiles.append(shard)

    def nearest_uncharmed(self, e: EnemyBase) -> Optional[EnemyBase]:
        best = None
        best_d2 = float("inf")
        for o in self.enemies:
            if o is e or (not o.alive()) or o.is_charmed():
                continue
            d2 = (o.pos - e.pos).length_squared()
            if d2 < best_d2:
                best_d2 = d2
                best = o
        return best

    def enemy_target(self, e: EnemyBase):
        """Who this enemy should chase and shoot at.

        Normally the player. When brainwashed: the nearest real enemy - and crucially the enemy keeps
        its own behaviour, so a hypnotised ranged shooter still shoots from range (at its former
        friends) instead of charging in like a melee unit.
        """
        if e.is_charmed():
            return self.nearest_uncharmed(e)
        return self.player

    def _enforce_charm_cap(self):
        """Keep the brainwashed herd bounded: beyond the cap the oldest charm is released, so a
        permanent-charm build can never fill the arena with allies you cannot kill."""
        charmed = [e for e in self.enemies if e.is_charmed()]
        excess = len(charmed) - CHARM_MAX_ACTIVE
        if excess <= 0:
            return
        charmed.sort(key=lambda e: e.charm_timer)
        for e in charmed[:excess]:
            e.charm_timer = 0.0

    def _handle_ally_contact(self):
        """Brainwashed enemies maul whatever they bump into; their own AI does the chasing."""
        for e in self.enemies:
            if (not e.is_charmed()) or e.charm_hit_cd > 0.0:
                continue
            for o in self.enemies:
                if o is e or (not o.alive()) or o.is_charmed():
                    continue
                rr = (e.radius + o.radius) ** 2
                if (e.pos - o.pos).length_squared() <= rr:
                    dmg = max(3, int(e.damage_contact * 4 * self.player.get_charm_damage_mult()))
                    d = o.pos - e.pos
                    dirn = d.normalize() if d.length_squared() > 1e-6 else Vector2(1, 0)
                    o.take_damage(dmg, dirn, 130.0, weapon_id=self.player.weapon_id, from_player=True)
                    # Charmed allies' kills are still your kills: credit them (stats, lifesteal).
                    self.credit_player_damage(dmg)
                    self.add_float_text(o.pos + Vector2(0, -10), str(dmg), C_CHARM, damage=True)
                    self._spawn_hit_particles(o.pos, C_CHARM)
                    e.charm_hit_cd = 0.45
                    break

    def _handle_bullet_enemy_collisions(self):
        for b in list(self.projectiles):
            # "ally" rounds are fired by brainwashed enemies; they hit the same things you do.
            if b.owner not in ("player", "ally"):
                continue
            for e in self.enemies:
                # Dead-but-not-yet-reaped enemies used to swallow bullets (and reuse of freed
                # id() values could make a fresh enemy immune). Object identity fixes both.
                # Charmed enemies are temporary allies: friendly fire is switched off for them.
                if (not e.alive()) or e.is_charmed() or (e in b.hit_set):
                    continue
                if not b.swept_hit(e.pos, e.radius):
                    continue
                b.hit_set.add(e)

                knock_dir = (e.pos - b.pos)
                if knock_dir.length_squared() > 0.001:
                    knock_dir = knock_dir.normalize()
                else:
                    knock_dir = Vector2(1, 0).rotate(random.uniform(0, 360))

                base_knock = 95.0
                weapon_knock = {
                    "cannon": 1.55,
                    "minigun": 0.75,
                    "shotgun": 1.30,
                    "rocket": 1.60,
                    "sniper": 1.15,
                    "flamethrower": 0.35,
                    "windscreen_wiper": 0.20,
                }.get(self.player.weapon_id, 1.0)

                trait_mul = self.player.trait_damage_mult((self.player.pos - e.pos).length(),
                                                          e.hp / max(1.0, e.hp_max))
                hit_dmg = b.damage * trait_mul
                # Railgun: damage builds with each enemy this round has already punched through.
                if b.overpen_frac > 0.0:
                    hit_dmg *= (1.0 + b.overpen_frac * b.hit_count)
                b.hit_count += 1
                # Tank "Executioner" ultra: anything that is not a boss dies on contact.
                own_round = b.owner == "player"
                if own_round and self.player.instant_kill and not isinstance(e, Boss):
                    hit_dmg = max(hit_dmg, e.hp)
                knockback = (base_knock * weapon_knock * self.player.knockback_mult
                             * self.player.trait_data().get("knockback_mul", 1.0))
                e.take_damage(hit_dmg, knock_dir, knockback, weapon_id=self.player.weapon_id, from_player=True)
                if b.slow > 0.0:
                    e.apply_slow(b.slow, b.slow_time)
                if b.burn_dps > 0.0:
                    e.apply_burn(b.burn_dps, b.burn_time)
                if b.charm > 0.0:
                    e.apply_charm(b.charm)
                    self._enforce_charm_cap()
                self.run_stats["hits"] += 1
                self.credit_player_damage(hit_dmg)
                self.update_mastery(self.player.weapon_id, hits=1)
                self.update_challenges("damage", int(round(hit_dmg)))
                self.add_float_text(e.pos + Vector2(random.uniform(-6, 6), -10),
                                    fmt_amount(hit_dmg), C_WARN, damage=True)
                self.audio_play("hit")
                self._spawn_hit_particles(e.pos, C_ACCENT_2)

                # Prism: the round shatters into a fan of shards the first time it connects.
                if b.split > 0 and not b.split_done:
                    b.split_done = True
                    self._spawn_prism_shards(b, e.pos)

                # Chain lightning for any tank that has it (electricity, traits, cards)
                chains = self.player.get_chain_count()
                chain_range = self.player.get_chain_range()
                if self.player.chain_double and chains <= 0:
                    # Electricity "Overload" borrowed by a chain-less tank still arcs.
                    chains, chain_range = 3, max(chain_range, 220.0)
                if own_round and chains > 0 and chain_range > 0.0:
                    self.tesla_chain(e, base_damage=hit_dmg, chains=chains, chain_range=chain_range)
                    # Electricity "Overload" ultra: every chain strikes the arc a second time.
                    if self.player.chain_double:
                        self.tesla_chain(e, base_damage=hit_dmg, chains=chains, chain_range=chain_range)

                # Ricochet "Absolute Bounce": rebound off the enemy instead of stopping dead.
                if b.bounce_enemies:
                    away = b.pos - e.pos
                    n = away.normalize() if away.length_squared() > 1e-6 else Vector2(1, 0)
                    b.vel = b.vel.reflect(n)
                    b.pos += n * (e.radius + b.radius + 2.0)
                    if b.pierce > 0:
                        b.pierce -= 1
                    if b.splash_radius > 0:
                        self._rocket_explode(b)
                    break

                # --- Pierce must be spent BEFORE splash would end the bullet ---
                if b.pierce > 0:
                    b.pierce -= 1
                    # While piercing, do NOT explode (rockets/tank would become absurd) - unless the
                    # Cannon "Siege Breaker" ultra deliberately fires the blast on every pass-through.
                    if b.pierce_splash and b.splash_radius > 0:
                        self._rocket_explode(b)
                else:
                    if b.splash_radius > 0:
                        self._rocket_explode(b)
                    if b.ground_fire:
                        self._spawn_ground_fire(b.pos)
                    b.life = 0
                break

    def _handle_enemy_bullet_player_collisions(self):
        # "Clean Sweep" tanks (windscreen wiper) swat enemy shots out of the air around you.
        if self.player.eats_bullets():
            eat_r = BARREL_EAT_RADIUS
            for b in list(self.enemy_projectiles):
                if (b.pos - self.player.pos).length_squared() <= eat_r * eat_r:
                    b.life = 0
                    self._spawn_hit_particles(b.pos, (255, 200, 210))
        if self.player.invulnerable():
            return
        for b in list(self.enemy_projectiles):
            if b.swept_hit(self.player.pos, PLAYER_RADIUS):
                b.life = 0
                self.damage_player(b.damage, source=getattr(b, "source_enemy", None))
                break

    def _handle_enemy_contact_player(self):
        if self.player.invulnerable():
            return
        for e in self.enemies:
            if e.is_charmed():
                continue   # a brainwashed ally does not hurt you
            rr = (PLAYER_RADIUS + e.radius) ** 2
            if (self.player.pos - e.pos).length_squared() <= rr:
                self.damage_player(e.damage_contact, source=e)
                d = (self.player.pos - e.pos)
                if d.length_squared() > 0.001:
                    self.player.vel += d.normalize() * 220
                break

    def damage_player(self, amount: float, source=None):
        if self.player.invulnerable():
            return
        # ceil() so armour never reduces a hit below 1 - it must not grant free invulnerability.
        dmg = max(1, int(math.ceil(float(amount) * self.player.meta_armor_mul)))
        self.run_stats["dmg_taken"] += dmg
        self.player.hp -= dmg
        self.player.iframes = PLAYER_IFRAMES
        self.shake = max(self.shake, SHAKE_HIT)
        self._spawn_hit_particles(self.player.pos, C_HEALTH)
        self.audio_play("hit")
        # Siphon "Blood Price" ultra: whoever hurt you is detonated, tank-shell style.
        if self.player.retribution and source is not None:
            self._detonate_attacker(source)

    def _detonate_attacker(self, source):
        """Blow up the enemy that just damaged the player (contact or a bullet's owner)."""
        if not getattr(source, "alive", None) or not source.alive():
            return
        center = Vector2(source.pos)
        blast_r = max(120.0, self.player.weapon.splash_radius) * 1.2
        rad2 = blast_r * blast_r
        for e in self.enemies:
            if (not e.alive()) or e.is_charmed():
                continue
            d2 = (e.pos - center).length_squared()
            if d2 <= rad2:
                t = 1.0 - math.sqrt(max(0.0, d2)) / blast_r
                dmg = max(6, int(56 * (0.55 + 0.45 * t) * self.player.damage_mult))
                d = e.pos - center
                dirn = d.normalize() if d.length_squared() > 1e-6 else Vector2(1, 0)
                e.take_damage(dmg, dirn, 200.0, weapon_id=self.player.weapon_id, from_player=True)
                self.credit_player_damage(dmg)
                self.add_float_text(e.pos + Vector2(0, -10), str(dmg), C_WARN, damage=True)
        self._spawn_hit_particles(center, self.get_explosion_color())
        self.shake = max(self.shake, 8.0)

    def add_float_text(self, pos, text: str, color=C_WARN, life: float = 0.65, damage: bool = False):
        if damage and not bool(self.save.settings.get("damage_numbers", True)):
            return
        if len(self.float_texts) >= MAX_FLOAT_TEXTS:
            return
        self.float_texts.append(FloatingText(Vector2(pos), text, color, life=life))

    def _spawn_hit_particles(self, pos: Vector2, color):
        if len(self.particles) >= MAX_PARTICLES:
            return
        for _ in range(HIT_PARTICLE_COUNT):
            ang = random.uniform(0, math.tau)
            sp = random.uniform(120, 320)
            vel = Vector2(math.cos(ang), math.sin(ang)) * sp
            self.particles.append(Particle(pos, vel, color, life=PARTICLE_LIFE, radius=random.randint(1, 3)))

    # =========================================================
    # DRAWING
    # =========================================================
