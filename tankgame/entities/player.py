"""The player tank: stats, upgrade effects, lifesteal, homing and charm."""
from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

import pygame
from pygame.math import Vector2

from tankgame.config import *
from tankgame.util import *
from tankgame.art.tank_art import draw_tank
from tankgame.data.weapons import WEAPONS
from tankgame.data.traits import TRAITS, trait_of, TraitDef
from tankgame.data.upgrades import UPGRADES, UPGRADES_BY_ID, UpgradeDef
from tankgame.ui.text import circle_outline
from tankgame.art.glow import add_glow


class Player:
    def __init__(self, pos: Vector2, weapon_id: str = "pistol"):
        self.pos = Vector2(pos)
        self.vel = Vector2(0, 0)
        self.aim_dir = Vector2(1, 0)

        self.weapon_id = weapon_id
        self.weapon = WEAPONS.get(weapon_id, WEAPONS["pistol"])

        self.damage_mult = 1.0
        self.fire_rate_mult = 1.0
        self.bullet_speed_mult = 1.0
        self.bullet_life_add = 0.0
        self.move_speed_add = 0.0
        self.piercing = 0
        self.crit_chance = 0.05
        self.crit_mult = 1.75
        self.dash_time_bonus = 0.0
        self.knockback_mult = 1.0
        self.magnet_bonus = 0.0

        # Tank modifiers - level-up cards and traits write into these.
        self.extra_pellets = 0
        self.spread_add = 0.0
        self.splash_mult = 1.0
        self.chain_bonus = 0
        self.chain_mult_add = 0.0
        self.bounce_bonus = 0
        self.slow_add = 0.0
        self.slow_time_add = 0.0
        self.burn_dps_add = 0.0
        self.burn_time_mult = 1.0
        self.recoil_mult = 1.0
        self.spin_bonus = 0.0
        self.spin_timer = 0.0
        self.burst_bonus = 0
        self.lifesteal_frac = 0.0
        self.lifesteal_charge = 0.0
        # New tank mechanics (all start neutral).
        self.pull_add = 0.0
        self.pull_radius_add = 0.0
        self.split_add = 0
        self.split_mult = 1.0
        self.drones_add = 0
        self.drone_target_mode = DRONE_TARGET_MODE_DEFAULT
        self.overpen_add = 0.0
        self.charm_add = 0.0
        self.charm_damage_add = 0.0
        self.infinite_bounces = False
        self.pellet_mul = 1.0
        self.splash_add = 0.0
        self.spread_set = -1.0
        self.mine_trail = 0.0
        self.chain_all = False
        self.homing_add = 0.0
        self.homing_range_add = 0.0
        self.flat_damage: Optional[float] = None   # Glass Gauntlet pins damage to a flat 99

        # Second-wave ultra mechanics. Every one is a plain flag so an ultra card taken from another
        # tank in "Ultra Only" still works - nothing here is wired to a specific weapon.
        self.always_crit = False       # Pistol: every shot is a critical
        self.spin_instant = False      # Minigun: no spin-up, full rate immediately
        self.bullet_life_inf = False   # Shotgun: shots never expire
        self.meteor_shot = False       # Rocket: shots call down meteors
        self.aimbot = False            # Sniper/Homing: predictive auto-aim
        self.aimbot_mode = AIMBOT_TARGET_MODE_DEFAULT
        self.pellet_uncap = False      # Windscreen: x5 output ignores the normal pellet ceiling
        self.chain_double = False      # Electricity: every chain strikes twice
        self.instant_kill = False      # Tank: shots execute normal enemies outright
        self.pull_instant = False      # Gravity Well: enemies snap straight onto the orb
        self.split_recursive = False   # Prism: even split shards can split again
        self.drone_free_roam = False   # Nanite Swarm: drones leave the ring and hunt
        self.twin_shot = False         # Railgun: mirrored shot fired opposite your aim
        self.charm_forever = False     # Hypnosis: brainwashing never wears off
        self.bounce_enemies = False    # Ricochet: rounds rebound off enemies too
        self.mine_homing = False       # Mine Layer: armed mines creep toward enemies
        self.retribution = False       # Siphon: whoever hurts you is detonated
        self.pierce_splash = False     # Cannon: blast fires on every enemy pierced
        self.ground_fire = False       # Flamethrower: shots scorch the floor

        # Cards taken this run, in the order they were picked (pause screen build summary).
        self.upgrade_counts: Dict[str, int] = {}

        self.max_hp = PLAYER_MAX_HP_BASE
        self.hp = self.max_hp
        self.iframes = 0.0

        self.shoot_timer = 0.0
        self.trigger_held = False
        self.burst_remaining = 0
        self.burst_gap_timer = 0.0
        self.auto_fire = False

        self.dash_timer = 0.0
        self.dash_cd_timer = 0.0
        self.dash_dir = Vector2(0, 0)
        self.dash_momentum_timer = 0.0

        self.level = 1
        self.xp = 0
        self.xp_to_next = 60

        self.score = 0

        self.effects: Dict[str, float] = {
            "damage_boost": 0.0,
            "rapid_fire": 0.0,
            "speed_boost": 0.0,
            "shield": 0.0,
            "drone_range": 0.0,
        }

        self.meta_damage_mul = 1.0
        self.meta_move_mul = 1.0
        self.meta_xp_mul = 1.0
        self.meta_dash_mul = 1.0
        self.meta_armor_mul = 1.0
        self.meta_bulletspd_mul = 1.0
        self.outline_color = C_ACCENT

    def set_weapon(self, weapon_id: str):
        self.weapon_id = weapon_id
        self.weapon = WEAPONS.get(weapon_id, WEAPONS["pistol"])
        self.burst_remaining = 0
        self.burst_gap_timer = 0.0
        self.shoot_timer = min(self.shoot_timer, 0.1)

    def invulnerable(self):
        return self.iframes > 0 or self.is_dashing() or self.effects["shield"] > 0

    def is_dashing(self):
        return self.dash_timer > 0

    def apply_powerup(self, ptype: str):
        if ptype == "damage_boost":
            self.effects["damage_boost"] = max(self.effects["damage_boost"], POWERUP_DURATION_DAMAGE)
        elif ptype == "rapid_fire":
            self.effects["rapid_fire"] = max(self.effects["rapid_fire"], POWERUP_DURATION_RAPID)
        elif ptype == "speed_boost":
            self.effects["speed_boost"] = max(self.effects["speed_boost"], POWERUP_DURATION_SPEED)
        elif ptype == "shield":
            self.effects["shield"] = max(self.effects["shield"], POWERUP_DURATION_SHIELD)
        elif ptype == "drone_range":
            self.effects["drone_range"] = max(self.effects["drone_range"],
                                              POWERUP_DURATION_DRONE_RANGE)

    def _grant_score(self, amount: int):
        """Bank score through the engine's one funnel; the referee accepts exactly this much."""
        amount = int(amount)
        if amount > 0:
            self._ac_score_grant = getattr(self, "_ac_score_grant", 0) + amount
            self.score += amount

    def _grant_heal(self, amount: float):
        """Tell the referee the engine is about to heal by ``amount`` (it budgets exactly that)."""
        if amount > 0:
            self._ac_heal_amount = getattr(self, "_ac_heal_amount", 0.0) + float(amount)
            self._ac_hp = True

    def gain_xp(self, amount: int):
        gained = int(round(amount * self.meta_xp_mul))
        self.xp += gained
        # The referee budgets exactly this much XP; level-ups are then verified against the
        # engine's own threshold curve, so XP can neither appear nor be mis-spent.
        self._ac_xp_grant = getattr(self, "_ac_xp_grant", 0) + gained

    def try_level_up(self) -> int:
        """Returns how many levels were gained (more than 1 is possible with big XP pickups)."""
        gained = 0
        for _ in range(16):
            if self.xp < self.xp_to_next:
                break
            self.xp -= self.xp_to_next
            self.level += 1
            self.xp_to_next = int(self.xp_to_next * 1.18 + 18)
            gained += 1
        return gained

    def apply_upgrade(self, up_id: str):
        up = UPGRADES_BY_ID.get(up_id)
        if not up:
            return
        self.apply_effects(up.effects)
        # Tank kicker: this universal card pays extra while you drive its tank.
        self.apply_effects(up.bonus_for(self.weapon_id))
        self.upgrade_counts[up.id] = self.upgrade_counts.get(up.id, 0) + 1

    def get_lifesteal(self) -> float:
        """Fraction of dealt damage banked as HP (Vampiric trait + Siphon Rounds cards).

        Capped well below the old 0.30: stacking every Siphon card used to heal several HP per shot.
        """
        return clamp(self.trait_data().get("lifesteal", 0.0) + self.lifesteal_frac, 0.0, 0.12)

    def bank_lifesteal(self, damage: float) -> int:
        """Turn a slice of dealt damage into HP, returning how many pips it healed.

        The threshold carries an epsilon: summing "1 HP per 70 damage" in floating point lands a
        hair under 1.0, which would quietly rob the player of the heal the card promised.
        """
        frac = self.get_lifesteal()
        if frac <= 0.0 or damage <= 0.0 or self.hp >= self.max_hp:
            return 0
        self._ac_hp = True
        self.lifesteal_charge += damage * frac
        whole = int(self.lifesteal_charge + 1e-6)
        if whole <= 0:
            return 0
        self.lifesteal_charge = max(0.0, self.lifesteal_charge - whole)
        room = max(0, int(self.max_hp - self.hp))
        healed = min(whole, room)
        self._grant_heal(healed)
        self.hp = min(self.max_hp, self.hp + healed)
        if healed < whole:
            # No hoarding a banked burst heal while already topped up.
            self.lifesteal_charge = 0.0
        return healed

    def apply_effects(self, effects: Dict[str, float]):
        """Single place that turns an upgrade/trait effect dict into player stats."""
        before = {attr: getattr(self, attr, None) for attr in BUILD_STAT_ATTRS}
        for key, value in effects.items():
            if key == "damage_mul":
                self.damage_mult *= value
            elif key == "fire_rate_mul":
                self.fire_rate_mult *= value
            elif key == "bullet_speed_mul":
                self.bullet_speed_mult *= value
            elif key == "bullet_life_add":
                self.bullet_life_add += value
            elif key == "max_hp":
                # Trade-off cards can go negative (Glass Cannon), so never drop below 1 pip.
                gained = int(round(value))
                self.max_hp = max(1, self.max_hp + gained)
                self.hp = clamp(min(self.hp + gained, self.max_hp), 1.0, self.max_hp)
            elif key == "heal":
                gain = max(0, min(self.max_hp, self.hp + int(value)) - self.hp)
                self._grant_heal(gain)
                self.hp = min(self.max_hp, self.hp + int(value))
            elif key == "lifesteal":
                self.lifesteal_frac += value
            elif key == "move_add":
                self.move_speed_add += value
            elif key == "dash_cd_mul":
                self.meta_dash_mul = max(0.55, self.meta_dash_mul * value)
            elif key == "dash_time_add":
                self.dash_time_bonus = min(0.12, self.dash_time_bonus + value)
            elif key == "pierce":
                self.piercing += int(value)
            elif key == "crit_chance":
                self.crit_chance = min(0.30, self.crit_chance + value)
            elif key == "crit_mult":
                self.crit_mult += value
            elif key == "xp_mul":
                self.meta_xp_mul = min(2.0, self.meta_xp_mul * value)
            elif key == "magnet":
                self.magnet_bonus = min(120.0, self.magnet_bonus + value)
            elif key == "knockback_mul":
                self.knockback_mult = min(2.5, self.knockback_mult * value)
            elif key == "pellets":
                self.extra_pellets += int(value)
            elif key == "spread_add":
                self.spread_add += value
            elif key == "splash_mul":
                self.splash_mult *= value
            elif key == "chain":
                self.chain_bonus += int(value)
            elif key == "chain_mult_add":
                self.chain_mult_add += value
            elif key == "bounce":
                self.bounce_bonus += int(value)
            elif key == "slow_add":
                self.slow_add += value
            elif key == "slow_time_add":
                self.slow_time_add += value
            elif key == "burn_dps_add":
                self.burn_dps_add += value
            elif key == "burn_time_mul":
                self.burn_time_mult *= value
            elif key == "recoil_mul":
                self.recoil_mult *= value
            elif key == "spin_bonus":
                self.spin_bonus += value
            elif key == "burst_add":
                self.burst_bonus += int(value)
            elif key == "pull_add":
                self.pull_add += value
            elif key == "pull_radius_add":
                self.pull_radius_add += value
            elif key == "split_add":
                self.split_add += int(value)
            elif key == "split_mult_mul":
                self.split_mult *= value
            elif key == "drones_add":
                self.drones_add += int(value)
            elif key == "overpen_add":
                self.overpen_add += value
            elif key == "charm_add":
                self.charm_add += value
            elif key == "charm_damage_add":
                self.charm_damage_add += value
            elif key == "chain_all":
                self.chain_all = True
            elif key == "homing_add":
                self.homing_add += value
            elif key == "homing_range_add":
                self.homing_range_add += value
            elif key == "bounce_infinite":
                self.infinite_bounces = True
            elif key == "pellet_mul":
                self.pellet_mul *= value
            elif key == "splash_add":
                self.splash_add += value
            elif key == "spread_set":
                self.spread_set = value
            elif key == "mine_trail":
                self.mine_trail += value
            elif key == "always_crit":
                self.always_crit = True
            elif key == "spin_instant":
                self.spin_instant = True
            elif key == "bullet_life_inf":
                self.bullet_life_inf = True
            elif key == "meteor_shot":
                self.meteor_shot = True
            elif key == "aimbot":
                self.aimbot = True
            elif key == "pellet_uncap":
                self.pellet_uncap = True
            elif key == "chain_double":
                self.chain_double = True
            elif key == "instant_kill":
                self.instant_kill = True
            elif key == "pull_instant":
                self.pull_instant = True
            elif key == "split_recursive":
                self.split_recursive = True
            elif key == "drone_free_roam":
                self.drone_free_roam = True
            elif key == "twin_shot":
                self.twin_shot = True
            elif key == "charm_forever":
                self.charm_forever = True
            elif key == "bounce_enemies":
                self.bounce_enemies = True
            elif key == "mine_homing":
                self.mine_homing = True
            elif key == "retribution":
                self.retribution = True
            elif key == "pierce_splash":
                self.pierce_splash = True
            elif key == "ground_fire":
                self.ground_fire = True
        # Tell the anti-cheat exactly which stats this legitimate upgrade changed, so an
        # unrelated card can never re-baseline (and thus cement) a tampered value.
        changed = {attr for attr in BUILD_STAT_ATTRS
                   if getattr(self, attr, None) != before[attr]}
        if changed:
            self._ac_changed = getattr(self, "_ac_changed", set()) | changed
        self._ac_effects = bool(changed)
        self._ac_hp = True

    # ---------------- Tank trait helpers ----------------
    def trait(self) -> TraitDef:
        return trait_of(self.weapon_id)

    def trait_data(self) -> Dict[str, float]:
        return self.trait().data

    def get_crit_chance(self) -> float:
        return clamp(self.crit_chance + self.trait_data().get("crit_add", 0.0), 0.0, 0.60)

    def get_crit_mult(self) -> float:
        return self.crit_mult + self.trait_data().get("crit_mult_add", 0.0)

    def trait_damage_mult(self, dist: float, hp_frac: float) -> float:
        """Damage bonus from the tank trait for one specific target."""
        data = self.trait_data()
        mult = 1.0
        point_blank = data.get("point_blank", 0.0)
        if point_blank and dist <= POINT_BLANK_RANGE:
            mult *= point_blank
        executioner = data.get("executioner", 0.0)
        if executioner and hp_frac <= 0.40:
            mult *= executioner
        breach = data.get("damage_vs_high_hp", 0.0)
        if breach and hp_frac >= 0.80:
            mult *= breach
        return mult

    def get_splash_mult(self) -> float:
        return self.splash_mult * self.trait_data().get("splash_mul", 1.0)

    def get_pellets(self) -> int:
        base = int(round(self.weapon.bullets_per_shot * self.pellet_mul))
        # Hard ceiling: stacking every pellet card (and an ultra) must never flood the field. The
        # wiper/multiplier cards use pellet_mul instead of flat +N so the count stays proportional.
        # The Windscreen x5 ultra lifts that ceiling (to its own, still-bounded one) so "five times
        # the output" is actually five times the output.
        cap = MAX_PELLETS_ULTRA if self.pellet_uncap else MAX_PELLETS_PER_SHOT
        return max(1, min(cap, base + self.extra_pellets))

    def get_spread(self) -> float:
        if self.spread_set >= 0.0:
            return self.spread_set
        return max(0.0, self.weapon.spread_deg + self.spread_add)

    def get_burst_count(self) -> int:
        if self.weapon.burst_count <= 0:
            return 0
        return self.weapon.burst_count + self.burst_bonus

    def get_recoil(self) -> float:
        # Capped so a single tank shell can never fling the player across the arena.
        raw = self.weapon.recoil * self.recoil_mult * self.trait_data().get("recoil_mul", 1.0)
        return min(raw, RECOIL_MAX)

    def get_chain_count(self) -> int:
        if self.chain_all:
            return 999   # effectively unlimited: the chain stops when it runs out of targets
        return int(self.weapon.chain + self.chain_bonus + self.trait_data().get("chain_add", 0.0))

    def get_chain_range(self) -> float:
        if self.chain_all:
            return float("inf")   # unlimited range, not just unlimited jumps
        return self.weapon.chain_range + self.trait_data().get("chain_range_add", 0.0)

    def get_chain_mult(self) -> float:
        base = self.trait_data().get("chain_mult", self.weapon.chain_damage_mult)
        return base + self.chain_mult_add

    def eats_bullets(self) -> bool:
        return self.trait_data().get("eats_bullets", 0.0) > 0.0

    def get_slow(self) -> Tuple[float, float]:
        data = self.trait_data()
        frac = data.get("slow", 0.0) + self.slow_add
        return clamp(frac, 0.0, 0.85), data.get("slow_time", 0.0) + self.slow_time_add

    def get_burn(self) -> Tuple[float, float]:
        data = self.trait_data()
        return data.get("burn_dps", 0.0) + self.burn_dps_add, data.get("burn_time", 0.0) * self.burn_time_mult

    def get_bounces(self) -> int:
        if self.infinite_bounces:
            return -1   # -1 means "never stops bouncing"
        return int(self.trait_data().get("bounces", 0.0)) + self.bounce_bonus

    def get_pull(self) -> Tuple[float, float]:
        """Gravity Well: (strength, radius) for dragging enemies toward in-flight shots."""
        data = self.trait_data()
        strength = data.get("pull", 0.0) + self.pull_add
        radius = data.get("pull_radius", 0.0) + self.pull_radius_add
        return strength, radius

    def get_split(self) -> Tuple[int, float]:
        """Prism: (shard count, shard damage fraction) applied on first impact."""
        data = self.trait_data()
        count = int(data.get("split", 0.0)) + self.split_add
        mult = data.get("split_mult", 0.0) * self.split_mult
        return count, mult

    def get_drone_count(self) -> int:
        """Nanite Swarm: how many orbiting drones this tank should have alive.

        `drones_add` is honoured even without the tank trait, so a borrowed "Legion" /
        "Swarm Unleashed" ultra actually produces drones on any tank.
        """
        base = int(self.trait_data().get("drones", 0.0))
        if base <= 0 and self.drones_add <= 0:
            return 0
        cap = DRONE_MAX_ULTRA if self.drone_free_roam else DRONE_MAX
        return max(0, min(cap, base + self.drones_add))

    def get_drone_range(self) -> float:
        """How far drones will look for a target; widened for a while by the Drone Range pickup."""
        if self.effects.get("drone_range", 0.0) > 0.0:
            return DRONE_RANGE * DRONE_RANGE_BOOST_MUL
        return DRONE_RANGE

    def get_overpen(self) -> float:
        return self.trait_data().get("overpen", 0.0) + self.overpen_add

    def get_charm(self) -> float:
        """Hypnosis: seconds an enemy stays brainwashed when hit."""
        if self.charm_forever:
            return 1.0e9   # the "permanent hypnosis" ultra
        return self.trait_data().get("charm", 0.0) + self.charm_add

    def get_charm_damage_mult(self) -> float:
        return 1.0 + self.charm_damage_add

    def get_homing(self) -> Tuple[float, float]:
        """Homing tank: (steer strength, lock-on range)."""
        data = self.trait_data()
        strength = data.get("homing", 0.0) + self.homing_add
        rng = data.get("homing_range", 0.0) + self.homing_range_add
        return strength, rng

    def drops_mines(self) -> bool:
        # Mine ultra cards grant the mine behaviour to ANY tank, not just the Mine Layer, so a
        # borrowed "Mega Mines" / "Homing Mines" card still works as written.
        return (self.trait_data().get("mine", 0.0) > 0.0
                or self.mine_trail > 0.0
                or self.mine_homing)

    def get_damage(self) -> float:
        if self.flat_damage is not None:
            return float(self.flat_damage)
        dmg = float(self.weapon.base_damage) * self.damage_mult * self.meta_damage_mul
        if self.effects["damage_boost"] > 0:
            dmg *= 1.5
        # Keep the fraction: rounding here silently threw away every damage upgrade the
        # 1-damage-per-pellet flamethrower / windscreen wiper were given.
        return max(0.5, dmg)

    def get_fire_cooldown(self) -> float:
        cd = self.weapon.fire_cd / max(0.1, self.fire_rate_mult)
        if self.effects["rapid_fire"] > 0:
            cd *= 0.58
        data = self.trait_data()
        if "spin_min" in data:
            # Spin-up tanks start sluggish and wind up to full speed while the trigger is held.
            # The Minigun "zero spin-up" ultra skips the ramp entirely.
            ramp = 1.0 if self.spin_instant else clamp(self.spin_timer / max(0.01, data.get("spin_time", 1.5)), 0.0, 1.0)
            factor = lerp(data.get("spin_min", 0.80), data.get("spin_max", 1.20) + self.spin_bonus, ramp)
            cd /= max(0.2, factor)
        return max(0.045, cd)

    def get_bullet_speed(self) -> float:
        return self.weapon.bullet_speed * self.bullet_speed_mult * self.meta_bulletspd_mul

    def get_bullet_lifetime(self) -> float:
        if self.bullet_life_inf:
            return 1.0e9   # Shotgun ultra: rounds only ever die to a wall, a hit, or the arena edge
        return max(0.25, self.weapon.bullet_life + self.bullet_life_add)

    def get_move_speed(self) -> float:
        sp = (PLAYER_MAX_SPEED_BASE + self.move_speed_add) * self.meta_move_mul
        if self.effects["speed_boost"] > 0:
            sp *= 1.25
        return sp

    def get_dash_time(self) -> float:
        return DASH_TIME_BASE + self.dash_time_bonus

    def get_dash_cooldown(self) -> float:
        return max(0.35, DASH_COOLDOWN_BASE * self.meta_dash_mul)

    def update(self, dt, game, input_move: Vector2, mouse_world: Vector2, mouse_buttons, keys):
        # Defensive: keep the live weapon in lockstep with weapon_id so no card/ultra can ever
        # leave the tank firing a stale default gun.
        if self.weapon.id != self.weapon_id:
            self.weapon = WEAPONS.get(self.weapon_id, WEAPONS["pistol"])

        d = mouse_world - self.pos
        if d.length_squared() > 0.001:
            self.aim_dir = d.normalize()

        self.shoot_timer = max(0.0, self.shoot_timer - dt)
        self.iframes = max(0.0, self.iframes - dt)
        self.dash_cd_timer = max(0.0, self.dash_cd_timer - dt)
        self.dash_timer = max(0.0, self.dash_timer - dt)
        self.dash_momentum_timer = max(0.0, self.dash_momentum_timer - dt)
        self.burst_gap_timer = max(0.0, self.burst_gap_timer - dt)
        for k in list(self.effects.keys()):
            self.effects[k] = max(0.0, self.effects[k] - dt)

        if keys[pygame.K_SPACE] and self.dash_cd_timer <= 0 and not self.is_dashing():
            ac = getattr(game, "anticheat", None)
            if ac is None or ac.allow_dash(self):
                dirn = input_move if input_move.length_squared() > 0.01 else self.aim_dir
                self.dash_dir = dirn.normalize() if dirn.length_squared() > 0.01 else Vector2(1, 0)
                self.dash_timer = self.get_dash_time()
                self.dash_cd_timer = self.get_dash_cooldown()
                game.audio_play("dash")

        # "Dash Only": walking is disabled, so the dash is the sole source of movement.
        walk_input = Vector2(0, 0) if game.dash_only else input_move
        max_sp = self.get_move_speed()
        if self.is_dashing():
            self.vel = self.dash_dir * DASH_SPEED
            self.dash_momentum_timer = 0.14
        else:
            if walk_input.length_squared() > 0.001:
                wish = walk_input.normalize() * max_sp
                self.vel += (wish - self.vel) * (1.0 - math.exp(-dt * PLAYER_MOVE_ACCEL_RATE))
            else:
                self.vel *= math.exp(-dt * PLAYER_MOVE_STOP_RATE)
            # Hard cap on top speed, but let the dash keep its momentum for a beat.
            if self.dash_momentum_timer <= 0.0 and self.vel.length_squared() > max_sp * max_sp:
                self.vel = self.vel.normalize() * max_sp

        self.pos += self.vel * dt
        self.pos.x = clamp(self.pos.x, PLAYER_RADIUS, ARENA_W - PLAYER_RADIUS)
        self.pos.y = clamp(self.pos.y, PLAYER_RADIUS, ARENA_H - PLAYER_RADIUS)

        game.resolve_player_walls()

        self.trigger_held = mouse_buttons[0] or self.auto_fire

        spin = self.trait_data()
        if "spin_min" in spin:
            if self.trigger_held and not self.is_dashing():
                self.spin_timer = min(spin.get("spin_time", 1.5), self.spin_timer + dt)
            else:
                self.spin_timer = max(0.0, self.spin_timer - dt * 3.0)

        if self.burst_remaining > 0:
            if self.burst_gap_timer <= 0:
                self.burst_remaining -= 1
                self.burst_gap_timer = self.weapon.burst_gap
                game.spawn_player_shot(self)
        else:
            if self.trigger_held and self.shoot_timer <= 0:
                self.shoot_timer = self.get_fire_cooldown()
                burst = self.get_burst_count()
                if burst > 0:
                    game.spawn_player_shot(self)
                    self.burst_remaining = burst - 1
                    self.burst_gap_timer = self.weapon.burst_gap
                else:
                    game.spawn_player_shot(self)

    def draw(self, surf, cam):
        flashing = self.invulnerable() and (int(time.time() * 24) % 2 == 0)
        body = (44, 52, 66) if flashing else C_PLAYER
        p = Vector2(self.pos.x - cam.x, self.pos.y - cam.y)
        ip = (int(p.x), int(p.y))
        shield = self.effects["shield"] > 0
        if shield:
            add_glow(surf, ip, (110, 160, 255), PLAYER_RADIUS + 22, 0.35)
        if self.is_dashing():
            add_glow(surf, ip, C_ACCENT_2, PLAYER_RADIUS + 18, 0.35)
        draw_tank(surf, p, self.aim_dir, body, self.outline_color, self.outline_color, self.weapon_id)
        if shield:
            circle_outline(surf, (170, 210, 255), ip, PLAYER_RADIUS + 13, 2)
        if self.is_dashing():
            circle_outline(surf, C_ACCENT_2, ip, PLAYER_RADIUS + 11, 2)
