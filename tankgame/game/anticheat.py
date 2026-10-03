"""Base-game anti-cheat.

A referee that watches the *live* game for states the engine itself could never produce.
It is deliberately cheat-agnostic: it knows nothing about how a cheat is delivered (no
menu/module/file assumptions), only the rules the engine guarantees, so a clean run can
never trip a check and any client that breaks a rule is caught. It **only prevents** -
it reverts the abnormal state, it never kills the player.

Checks (all cheap, O(1) or O(obstacles)/frame):

1. **Rule integrity** - the engine never replaces its own combat/movement/stat methods.
   A swapped ``damage_player`` / ``spawn_player_shot`` / ``Player.update`` /
   ``get_move_speed`` / ``get_damage`` / ``get_fire_cooldown`` / ... is restored on sight.
2. **Stat baseline** - every build flag/scalar is snapshotted whenever the engine changes
   it through its own upgrade funnel; any other change is reverted.
3. **Bounds** - values the engine caps (iframes, dash duration, power-up timers) are
   clamped back to their legal ceiling.
4. **Movement** - displacement can never exceed the tank's legal top speed.
5. **Dash/fire** - dashes and shots before their cooldown, or shots with no trigger, are
   blocked; dash duration is capped.
6. **Damage accounting** - a player-sourced hit with zero knockback (a damage aura) is
   refused.
7. **Vitals** - HP never exceeds max and only rises through the engine's heal funnels.
8. **World** - wall-clipping, injected obstacles and projectile floods are undone.
9. **Provenance** - XP, level, score, wave and save fields only move through the engine's
   own funnels.
"""
from __future__ import annotations

import time

from pygame.math import Vector2

from tankgame.config import (
    PLAYER_MAX_SPEED_BASE, DASH_SPEED, MAX_PROJECTILES_IMMORTAL,
    PLAYER_IFRAMES, PLAYER_RADIUS, DASH_TIME_BASE,
    POWERUP_DURATION_DAMAGE, POWERUP_DURATION_RAPID, POWERUP_DURATION_SPEED,
    POWERUP_DURATION_SHIELD, POWERUP_DURATION_DRONE_RANGE, BUILD_STAT_ATTRS,
)

MAX_DASH_BONUS = 0.12   # apply_effects clamps dash_time_bonus to this

# Player flags/scalars that may only change through Player.apply_effects / run setup.
_GUARDED_ATTRS = BUILD_STAT_ATTRS
_FLAG_LABELS = {
    "always_crit": "always-crit", "instant_kill": "instant-kill", "aimbot": "auto-aim",
    "bullet_life_inf": "immortal bullets", "spin_instant": "instant spin-up",
    "meteor_shot": "meteor-on-shot", "ground_fire": "ground fire",
    "chain_double": "double chains", "pull_instant": "instant pull",
    "split_recursive": "recursive splits", "drone_free_roam": "free-roam drones",
    "twin_shot": "twin shot", "charm_forever": "permanent charm",
    "bounce_enemies": "enemy bounces", "infinite_bounces": "infinite bounces",
    "mine_homing": "homing mines", "retribution": "retribution",
    "pierce_splash": "pierce splash", "pellet_uncap": "pellet uncap",
    "max_hp": "max HP", "flat_damage": "flat damage", "dash_time_bonus": "dash time",
}

# Engine methods that enforce rules. Presentation/loop methods are intentionally excluded
# so a normal overlay is not treated as a rule violation.
_GAME_METHODS = (
    "damage_player", "_handle_enemy_contact_player",
    "_handle_enemy_bullet_player_collisions", "spawn_player_shot",
    "credit_player_damage", "credit_burn_damage",
)
_PLAYER_METHODS = (
    "update", "get_move_speed", "get_dash_time", "get_dash_cooldown", "get_damage",
    "get_fire_cooldown", "get_pellets", "get_spread", "get_recoil", "get_bullet_speed",
    "get_bullet_lifetime", "get_crit_chance", "get_crit_mult", "get_burst_count",
    "get_chain_count", "get_chain_range", "get_chain_mult", "get_bounces", "get_pull",
    "get_split", "get_drone_count", "get_drone_range", "get_overpen", "get_charm",
    "get_charm_damage_mult", "get_homing", "drops_mines", "eats_bullets", "invulnerable",
)

_EFFECT_CAPS = (
    ("damage_boost", POWERUP_DURATION_DAMAGE),
    ("rapid_fire", POWERUP_DURATION_RAPID),
    ("speed_boost", POWERUP_DURATION_SPEED),
    ("shield", POWERUP_DURATION_SHIELD),
    ("drone_range", POWERUP_DURATION_DRONE_RANGE),
)

# Active anticheat for the damage hook (one game per process in normal play).
_ACTIVE = None
_ORIG_TAKE_DAMAGE = None
_TAKE_DAMAGE_HOOKED = False


def _install_damage_hook():
    global _ORIG_TAKE_DAMAGE, _TAKE_DAMAGE_HOOKED
    if _TAKE_DAMAGE_HOOKED:
        return
    from tankgame.entities.enemies import EnemyBase
    _ORIG_TAKE_DAMAGE = EnemyBase.take_damage

    def take_damage(self, dmg, knock_dir, knockback=0.0, weapon_id=None, from_player=False):
        # Every genuine player hit applies knockback; a zero-knockback player hit is a
        # damage aura and is refused outright.
        if from_player and knockback <= 0.0:
            if _ACTIVE is not None:
                _ACTIVE._bad_hits += 1
            return
        return _ORIG_TAKE_DAMAGE(self, dmg, knock_dir, knockback, weapon_id, from_player)

    EnemyBase.take_damage = take_damage
    _TAKE_DAMAGE_HOOKED = True


class AntiCheat:
    SPEED_TOLERANCE = 1.15
    DASH_SPEED_TOLERANCE = 1.10
    MIN_SHOT_GAP = 0.03   # the engine can never legitimately fire twice inside this window
    EPISODE_GAP = 1.0   # seconds of silence before the same violation counts again

    def __init__(self, game):
        self.game = game
        self._cls = type(game)
        self._pcls = type(game.player)
        self._game_hooks = tuple(
            (name, getattr(self._cls, name)) for name in _GAME_METHODS
        )
        self._player_hooks = tuple(
            (name, getattr(self._pcls, name)) for name in _PLAYER_METHODS
        )
        _install_damage_hook()
        self.reset()

    # ---------------------------------------------------------------- lifecycle
    def reset(self):
        player = getattr(self.game, "player", None)
        self._player = player
        self.last_pos = Vector2(player.pos) if player is not None else Vector2(0, 0)
        self._last_shot_at = -1.0e9
        self._weapon_id = getattr(player, "weapon_id", None)
        self.dash_ready_at = 0.0
        self._dash_authorized = False
        self._was_dashing = False
        self._save_legit = False
        self._bad_hits = 0
        self._hp = player.hp if player is not None else 0.0
        self._xp = player.xp if player is not None else 0
        self._level = player.level if player is not None else 1
        self._xp_next = player.xp_to_next if player is not None else 0
        self._score = player.score if player is not None else 0
        self._wave = getattr(self.game, "wave", 1)
        self._time = getattr(self.game, "survival_time", 0.0)
        self._obstacles = list(getattr(self.game, "obstacles", ()))
        self.violations = 0
        self._last_seen = {}
        self._snapshot_save()
        self._rebaseline()

    def _sync_player(self):
        player = getattr(self.game, "player", None)
        if player is not self._player:
            if not getattr(self.game, "_ac_new_run", False):
                self._raise("Player object replaced")
            self.game._ac_new_run = False
            self.reset()

    def _rebaseline(self):
        player = self._player
        if player is None:
            self._baseline = {}
            return
        self._baseline = {attr: getattr(player, attr, None) for attr in _GUARDED_ATTRS}

    # ----------------------------------------------------------------- reporting
    def _warn(self, label, detail=""):
        player = self._player
        if player is None:
            return
        text = "ANTI-CHEAT: " + label
        if detail:
            text += " [" + detail + "]"
        try:
            self.game.add_float_text(player.pos + Vector2(0, -58), text, (255, 150, 90), life=1.4)
        except Exception:
            pass

    def _raise(self, label, detail=""):
        """Report a violation once per episode (a quiet gap starts a new one). Never kills."""
        now = time.perf_counter()
        last = self._last_seen.get(label)
        if last is None or now - last > self.EPISODE_GAP:
            self.violations += 1
            self._warn(label, detail)
        self._last_seen[label] = now

    # -------------------------------------------------------------- rule integrity
    def _check_methods(self):
        for name, func in self._game_hooks:
            if getattr(self._cls, name) is not func:
                setattr(self._cls, name, func)
                self._raise("Rule method replaced: " + name)
        for name, func in self._player_hooks:
            if getattr(self._pcls, name) is not func:
                setattr(self._pcls, name, func)
                self._raise("Rule method replaced: Player." + name)

    # ---------------------------------------------------------------- stat baseline
    def _check_attrs(self):
        player = self._player
        if player is None:
            return
        # A legitimate upgrade re-baselines ONLY the stats it actually changed. Anything else
        # this frame is a tamper even if an unrelated card was picked at the same time, so a
        # cheat cannot bury a wiped stat under a real upgrade.
        changed = getattr(player, "_ac_changed", None)
        if changed:
            player._ac_changed = set()
            base = self._baseline
            for attr in changed:
                if attr in base:
                    base[attr] = getattr(player, attr, None)
        base = self._baseline
        for attr in _GUARDED_ATTRS:
            want = base.get(attr)
            if getattr(player, attr, None) != want:
                try:
                    setattr(player, attr, want)
                except Exception:
                    pass
                self._raise("Stat tamper: " + _FLAG_LABELS.get(attr, attr))

    # -------------------------------------------------------------------- bounds
    def _check_bounds(self):
        player = self._player
        if player is None:
            return
        if player.iframes > PLAYER_IFRAMES + 1e-6:
            player.iframes = PLAYER_IFRAMES
            self._raise("Invulnerability overflow")
        if player.dash_timer > DASH_TIME_BASE + MAX_DASH_BONUS + 1e-6:
            player.dash_timer = DASH_TIME_BASE + MAX_DASH_BONUS
            self._raise("Dash duration overflow")
        effects = player.effects
        for key, cap in _EFFECT_CAPS:
            value = effects.get(key, 0.0)
            if value > cap + 1e-6:
                effects[key] = cap
                self._raise("Power-up overflow")
        # Velocity is capped by the engine; recoil/knockback never approach this ceiling.
        vmax = DASH_SPEED * 1.5
        if player.vel.length_squared() > vmax * vmax:
            player.vel = player.vel.normalize() * vmax
            self._raise("Velocity overflow")

    # -------------------------------------------------------------------- time
    def _check_time(self):
        # survival_time only ever advances with the clamped frame dt.
        now = getattr(self.game, "survival_time", 0.0)
        if now < self._time - 1e-6 or now > self._time + 0.25:
            self.game.survival_time = self._time
            now = self._time
            self._raise("Time manipulation")
        self._time = now

    # ---------------------------------------------------------------------- vitals
    def _check_hp(self):
        player = self._player
        if player is None:
            return
        legit = getattr(player, "_ac_hp", False)
        if legit:
            player._ac_hp = False
        if player.hp > player.max_hp + 0.01:
            player.hp = player.max_hp
            self._raise("HP overflow")
        elif player.hp > self._hp + 0.001 and not legit:
            player.hp = self._hp
            self._raise("Unexplained heal")
        self._hp = player.hp

    # ---------------------------------------------------------------------- world
    def _check_walls(self):
        player = self._player
        if player is None:
            return
        x, y = int(player.pos.x), int(player.pos.y)
        for r in self.game.obstacles:
            if r.collidepoint(x, y):
                self.game.resolve_player_walls()
                self._raise("Wall phase")
                return

    def _check_obstacles(self):
        if getattr(self.game, "_ac_obstacles", False):
            self.game._ac_obstacles = False
            self._obstacles = list(self.game.obstacles)
            return
        if len(self.game.obstacles) != len(self._obstacles):
            self.game.obstacles = list(self._obstacles)
            self._raise("Obstacle injection")

    def _check_projectiles(self):
        cap = MAX_PROJECTILES_IMMORTAL
        extra = len(self.game.projectiles) - cap
        if extra > 0:
            del self.game.projectiles[:extra]
            self._raise("Projectile flood")

    def _check_enemies(self):
        # Values the engine never produces: a unit above its own max HP, or slowed past the
        # hard 0.9 cap (i.e. frozen in place).
        for e in self.game.enemies:
            if e.hp > e.hp_max + 0.01:
                e.hp = e.hp_max
                self._raise("Enemy HP overflow")
            if e.slow_frac > 0.9 + 1e-6:
                e.slow_frac = 0.9
                self._raise("Enemy perma-slow")

    # ---------------------------------------------------------------------- damage
    def _check_aura(self):
        if self._bad_hits:
            self._bad_hits = 0
            self._raise("Uncredited player damage")

    # ------------------------------------------------------------------- progression
    def _check_progress(self):
        player = self._player
        if player is None:
            return
        xp_ok = getattr(player, "_ac_xp", False)
        if xp_ok:
            player._ac_xp = False
        if (player.xp != self._xp or player.level != self._level
                or player.xp_to_next != self._xp_next):
            if not xp_ok:
                player.xp = self._xp
                player.level = self._level
                player.xp_to_next = self._xp_next
                self._raise("XP/level injection")
        self._xp, self._level, self._xp_next = player.xp, player.level, player.xp_to_next

        score_ok = getattr(player, "_ac_score", False)
        if score_ok:
            player._ac_score = False
        if player.score != self._score:
            if not score_ok:
                player.score = self._score
                self._raise("Score injection")
        self._score = player.score

        wave_ok = getattr(self.game, "_ac_wave", False)
        if wave_ok:
            self.game._ac_wave = False
        if self.game.wave != self._wave:
            if not wave_ok:
                self.game.wave = self._wave
                self._raise("Wave injection")
        self._wave = self.game.wave

    # ------------------------------------------------------------------- save guard
    def note_save(self):
        """The engine is about to change the save through a legitimate funnel."""
        self._save_legit = True

    def _snapshot_save(self):
        save = self.game.save
        self._save_snap = (
            save.coins,
            dict(save.weapon_unlocks),
            dict(save.map_unlocks),
            dict(save.cosmetics_unlocked),
            dict(save.shop_levels),
        )

    def _check_save(self):
        save = self.game.save
        current = (save.coins, save.weapon_unlocks, save.map_unlocks,
                   save.cosmetics_unlocked, save.shop_levels)
        if current == self._save_snap:
            self._save_legit = False
            return
        if self._save_legit:
            self._save_legit = False
            self._snapshot_save()
            return
        coins, wu, mu, cu, sl = self._save_snap
        save.coins = coins
        save.weapon_unlocks = dict(wu)
        save.map_unlocks = dict(mu)
        save.cosmetics_unlocked = dict(cu)
        save.shop_levels = dict(sl)
        try:
            save.save()
        except Exception:
            pass
        self._raise("Save edit (coins/unlocks/meta)")

    # -------------------------------------------------------------------- frame
    def guard(self):
        """Full check. Called from ``Game.handle_events`` and the top of ``update_playing``."""
        global _ACTIVE
        _ACTIVE = self
        self._dash_authorized = False
        self._sync_player()
        self._check_methods()
        self._check_attrs()
        self._check_bounds()
        self._check_hp()
        self._check_obstacles()
        self._check_walls()
        self._check_progress()
        self._check_save()
        self._check_time()

    def tick(self, dt):
        """Playing-state checks. Called at the end of ``update_playing``."""
        global _ACTIVE
        _ACTIVE = self
        self._sync_player()
        player = self._player
        if player is not None:
            self._check_hp()
            self._check_speed(player, dt)
            self._check_dash(player)
        self._check_aura()
        self._check_projectiles()
        self._check_enemies()
        self._check_progress()
        self._check_save()
        self._check_time()

    def _check_speed(self, player, dt):
        if dt <= 0.0:
            return
        speed = (player.pos - self.last_pos).length() / dt
        limit = self._legit_speed(player) * self.SPEED_TOLERANCE
        if player.is_dashing() or player.dash_momentum_timer > 0.0:
            limit = max(limit, DASH_SPEED * self.DASH_SPEED_TOLERANCE)
        if speed > limit:
            # Wall push-out can add a few px to a dash into cover; that is geometry, not speed.
            pad = PLAYER_RADIUS + 6
            for r in self.game.obstacles:
                if r.inflate(pad, pad).collidepoint(player.pos.x, player.pos.y):
                    self.last_pos = Vector2(player.pos)
                    return
            player.pos = Vector2(self.last_pos)
            player.vel = Vector2(0, 0)
            self._raise("Speed hack", f"{speed:.0f}px/s")
            return
        self.last_pos = Vector2(player.pos)

    def _check_dash(self, player):
        # Any dash that started without the engine's own allow_dash is abnormal. The
        # engine path is covered by allow_dash; this catches a client that starts one
        # by other means.
        dashing = player.is_dashing()
        if dashing and not self._was_dashing and not self._dash_authorized:
            player.dash_timer = 0.0
            player.dash_cd_timer = player.get_dash_cooldown()
            self._raise("Dash without cooldown")
        self._was_dashing = dashing

    # ------------------------------------------------------------- cooldown gates
    def allow_dash(self, player) -> bool:
        now = self._now()
        if now + 0.06 < self.dash_ready_at:
            player.dash_cd_timer = player.get_dash_cooldown()
            self._raise("Dash before cooldown")
            return False
        self.dash_ready_at = now + player.get_dash_cooldown()
        self._dash_authorized = True
        return True

    def allow_shot(self, player) -> bool:
        now = self._now()
        if player.weapon_id != self._weapon_id:
            # A weapon swap resets the engine's own shot timer, so restart our window too.
            self._weapon_id = player.weapon_id
            self._last_shot_at = -1.0e9
        if player.burst_remaining > 0 or player.burst_gap_timer > 0.0:
            self._last_shot_at = now
            return True
        if not (player.trigger_held or player.auto_fire):
            self._raise("Shot without trigger")
            return False
        if now - self._last_shot_at < self.MIN_SHOT_GAP:
            self._raise("Shot before cooldown")
            return False
        self._last_shot_at = now
        return True

    def _now(self):
        return getattr(self.game, "survival_time", 0.0)

    def _legit_speed(self, player):
        sp = (PLAYER_MAX_SPEED_BASE + getattr(player, "move_speed_add", 0.0)) * player.meta_move_mul
        if player.effects.get("speed_boost", 0.0) > 0.0:
            sp *= 1.25
        return sp


# ---------------------------------------------------------------------------
# Tamper-resistant entry points
#
# ``Game`` calls these instead of the bound methods directly. They re-install the canonical
# implementations if a client has monkey-patched them, so patching ``AntiCheat.guard`` /
# ``tick`` / any of the checks out of the way simply gets healed on the next call.
# ---------------------------------------------------------------------------

_CANONICAL = {name: getattr(AntiCheat, name) for name in dir(AntiCheat)
              if not name.startswith("__")}
_CANON_GUARD = _CANONICAL["guard"]
_CANON_TICK = _CANONICAL["tick"]


def _self_heal():
    """Restore every AntiCheat attribute a client may have swapped out."""
    for name, attr in _CANONICAL.items():
        if getattr(AntiCheat, name, None) is not attr:
            try:
                setattr(AntiCheat, name, attr)
            except Exception:
                pass


def run_guard(ac):
    """Run the canonical guard, healing the class if it was tampered with."""
    _self_heal()
    if getattr(ac.game, "anticheat", None) is not ac:
        ac.game.anticheat = ac
    _CANON_GUARD(ac)


def run_tick(ac, dt):
    _self_heal()
    _CANON_TICK(ac, dt)
