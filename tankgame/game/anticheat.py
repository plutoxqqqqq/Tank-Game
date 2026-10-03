"""Base-game anti-cheat — a cheat-agnostic behavioural referee.

It watches the *live* game for states the engine itself could never produce and reverts them.
It assumes nothing about *how* a cheat is delivered (menu, injected DLL, memory trainer, a
patched method, a direct field poke): it only knows the rules the engine guarantees, so a clean
run can never trip a check and any client that breaks a rule is caught no matter the vector.

It **only ever prevents** — it reverts the illegal state and never kills the player.

The referee is driven through ``run_guard`` / ``run_tick`` (see the bottom of the file). Those
re-install the canonical implementations if a client monkey-patches the referee class, and the
game keeps a private ``_referee`` handle, so swapping ``game.anticheat`` does not detach it.

What it enforces, grouped:

* **Integrity** — the engine never replaces its own combat/movement/stat methods, projectile
  physics, enemy rules or the damage gate, and the referee never replaces its own checks. Any of
  them swapped is restored on sight and reported ("Referee tampered" / "Referee detached").
* **Sanity** — no NaN / infinity / impossible-negative ever survives in the player's position,
  velocity, vitals, timers or build stats, in an enemy's HP or position, or in a round's speed.
* **Baselines** — every build flag/scalar may change only through the engine's upgrade funnel
  (``Player.apply_effects`` records exactly which stats a legit card touched); any other change,
  on any guarded stat, is reverted even if an unrelated card was picked the same frame. An
  impostor player object (carrying whatever stats a client gave it) is never adopted.
* **Exact grants, not yes/no flags** — every engine funnel declares *how much* it changed:
  heals report the HP they add, XP gains the XP they add (level-ups are then re-derived from the
  engine's own threshold curve), kills the score they bank, wave clears the waves they advance,
  and every shop / reward / payout the exact coin delta and the exact unlocks or meta levels it
  sets. Anything the declaration does not account for is reverted — forging a single flag buys
  nothing. Pending save changes are judged before any re-snapshot, so nothing launders through
  a run restart.
* **Kill provenance** — every point of HP an enemy loses is recorded by the engine's own damage
  paths. Before dead enemies are reaped and paid out, HP lost must equal recorded damage, so a
  poked kill (HP set to 0 / NaN) is undone and never pays score, XP or drops.
* **Bounds** — i-frames, dash duration/cooldown, shoot timer, burst count, spin-up, power-up
  durations (and power-up kinds), velocity, lifesteal charge and the magnet radius are all
  clamped to their legal ceilings.
* **Movement / dash / fire** — displacement never exceeds the tank's legal top speed; a dash
  that started without the engine's own permission is cancelled; shots before their cooldown,
  with no trigger, or faster than any weapon could cycle (a sliding-window rate cap) are blocked.
  Rounds are speed-checked *before* they move, against what the build can legally fire.
* **Damage** — a player-sourced hit that applies zero knockback (a damage aura) is refused, and
  NaN / infinite hit damage is dropped.
* **World** — wall-clipping, injected obstacles, projectile floods (yours and the enemies'),
  enemies above their own max HP, frozen-solid enemies, out-of-arena enemies, an over-cap
  brainwashed herd and a charmed boss are all undone.
* **Save / time** — survival time only advances with the clamped frame.

Every violation is reported once per episode and counted for the whole session.
"""
from __future__ import annotations

import math
import time
from collections import deque

from pygame.math import Vector2

from tankgame.config import (
    PLAYER_MAX_SPEED_BASE, DASH_SPEED, MAX_PROJECTILES, MAX_PROJECTILES_IMMORTAL,
    PLAYER_IFRAMES, PLAYER_RADIUS, DASH_TIME_BASE, DASH_COOLDOWN_BASE, ARENA_W, ARENA_H,
    POWERUP_DURATION_DAMAGE, POWERUP_DURATION_RAPID, POWERUP_DURATION_SPEED,
    POWERUP_DURATION_SHIELD, POWERUP_DURATION_DRONE_RANGE, BUILD_STAT_ATTRS,
    CHARM_MAX_ACTIVE,
)

MAX_DASH_BONUS = 0.12   # apply_effects clamps dash_time_bonus to this
MAGNET_BONUS_CAP = 120.0   # apply_effects clamps magnet_bonus to this
EFFECT_KEYS = ("damage_boost", "rapid_fire", "speed_boost", "shield", "drone_range")

# Round speed ceilings. Player-side rounds may travel as fast as the build legally fires (bullet
# speed cards stack without limit, so the cap tracks the live stat) with headroom; nothing the
# engine spawns on its own (drones, allies, prism shards) beats ROUND_SPEED_FLOOR.
ROUND_SPEED_HEADROOM = 1.25
ROUND_SPEED_FLOOR = 1200.0
ENEMY_ROUND_SPEED_CAP = 1500.0

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

# Engine methods that enforce rules. Presentation/loop methods are intentionally excluded so a
# normal overlay is not treated as a rule violation.
_GAME_METHODS = (
    "damage_player", "_handle_enemy_contact_player",
    "_handle_enemy_bullet_player_collisions", "spawn_player_shot",
    "credit_player_damage", "credit_burn_damage",
    "_handle_bullet_enemy_collisions", "resolve_player_walls",
)
_PLAYER_METHODS = (
    "update", "get_move_speed", "get_dash_time", "get_dash_cooldown", "get_damage",
    "get_fire_cooldown", "get_pellets", "get_spread", "get_recoil", "get_bullet_speed",
    "get_bullet_lifetime", "get_crit_chance", "get_crit_mult", "get_burst_count",
    "get_chain_count", "get_chain_range", "get_chain_mult", "get_bounces", "get_pull",
    "get_split", "get_drone_count", "get_drone_range", "get_overpen", "get_charm",
    "get_charm_damage_mult", "get_homing", "drops_mines", "eats_bullets", "invulnerable",
    "apply_effects", "apply_powerup", "gain_xp", "try_level_up", "apply_upgrade",
    "bank_lifesteal", "get_lifesteal",
)

_EFFECT_CAPS = (
    ("damage_boost", POWERUP_DURATION_DAMAGE),
    ("rapid_fire", POWERUP_DURATION_RAPID),
    ("speed_boost", POWERUP_DURATION_SPEED),
    ("shield", POWERUP_DURATION_SHIELD),
    ("drone_range", POWERUP_DURATION_DRONE_RANGE),
)

# Methods a client might shadow on the referee *instance* to neuter a gate (for example setting
# ac.allow_shot = lambda p: True). The audit strips any such instance override so the class method
# — which the self-heal keeps canonical — is what actually runs.
_GATE_METHODS = ("guard", "tick", "pre_flight", "pre_reap", "allow_shot", "allow_dash",
                 "_check_methods", "_check_attrs", "_check_hp", "_check_sanity", "_check_bounds",
                 "_check_progress", "_check_save", "_check_enemies", "_check_projectiles",
                 "_check_speed", "_check_dash", "_check_walls", "_check_obstacles", "_check_aura",
                 "_check_time", "_raise")

# Active anticheat for the damage hook (one game per process in normal play).
_ACTIVE = None
_ORIG_TAKE_DAMAGE = None
_HOOK_FN = None
_TAKE_DAMAGE_HOOKED = False


def _finite(v) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def _vec_ok(v) -> bool:
    return isinstance(v, Vector2) and _finite(v.x) and _finite(v.y)


def _install_damage_hook():
    global _ORIG_TAKE_DAMAGE, _TAKE_DAMAGE_HOOKED, _HOOK_FN
    if _TAKE_DAMAGE_HOOKED:
        return
    from tankgame.entities.enemies import EnemyBase
    _ORIG_TAKE_DAMAGE = EnemyBase.take_damage

    def take_damage(self, dmg, knock_dir, knockback=0.0, weapon_id=None, from_player=False):
        # A NaN/infinite hit is never something the engine produces.
        if from_player and not _finite(dmg):
            if _ACTIVE is not None:
                _ACTIVE._bad_hits += 1
            return
        # Every genuine player hit applies knockback; a zero-knockback player hit is a damage
        # aura (no weapon fires without a recoil impulse on the target) and is refused outright.
        if from_player and knockback <= 0.0:
            if _ACTIVE is not None:
                _ACTIVE._bad_hits += 1
            return
        return _ORIG_TAKE_DAMAGE(self, dmg, knock_dir, knockback, weapon_id, from_player)

    EnemyBase.take_damage = take_damage
    _HOOK_FN = take_damage
    _TAKE_DAMAGE_HOOKED = True


class AntiCheat:
    SPEED_TOLERANCE = 1.15
    DASH_SPEED_TOLERANCE = 1.10
    MIN_SHOT_GAP = 0.03     # the engine can never legitimately fire twice inside this window
    SHOT_WINDOW = 1.0       # sliding window (seconds) for the fire-rate ceiling
    MAX_SHOTS_PER_WINDOW = 90   # trigger-pulls/sec ceiling (fastest cycle ~22/s, bursts add more)
    EPISODE_GAP = 1.0       # seconds of silence before the same violation counts again

    def __init__(self, game):
        self.game = game
        self._cls = type(game)
        self._pcls = type(game.player)
        self._game_hooks = tuple((name, getattr(self._cls, name)) for name in _GAME_METHODS)
        self._player_hooks = tuple((name, getattr(self._pcls, name)) for name in _PLAYER_METHODS)
        from tankgame.entities.projectile import Projectile
        from tankgame.entities.enemies import EnemyBase
        self._proj_cls = Projectile
        self._enemy_cls = EnemyBase
        self._proj_hooks = tuple((name, getattr(Projectile, name)) for name in ("update", "swept_hit", "alive"))
        self._enemy_hooks = tuple((name, getattr(EnemyBase, name)) for name in ("alive", "apply_slow", "tick_status"))
        _install_damage_hook()
        self.violations = 0     # cumulative for the session: a run restart never wipes the record
        self.reset()

    # ---------------------------------------------------------------- lifecycle
    def reset(self):
        # Never launder: anything pending against the save is judged before a re-snapshot.
        if getattr(self, "_save_snap", None) is not None:
            self._check_save()
        player = getattr(self.game, "player", None)
        self._player = player
        if player is not None:
            for attr in ("_ac_xp_grant", "_ac_score_grant", "_ac_heal_amount"):
                if hasattr(player, attr):
                    setattr(player, attr, 0)
        self.game._ac_wave_steps = 0
        self._save_grant = self._empty_save_grant()
        self.last_pos = Vector2(player.pos) if player is not None else Vector2(0, 0)
        self._last_shot_at = -1.0e9
        self._shot_times = deque()
        self._weapon_id = getattr(player, "weapon_id", None)
        self.dash_ready_at = 0.0
        self._dash_authorized = False
        self._was_dashing = False
        self._save_legit = False
        self._bad_hits = 0
        self._heal_budget = 0.0
        self._hp = player.hp if player is not None else 0.0
        self._max_hp = player.max_hp if player is not None else 0.0
        self._xp = player.xp if player is not None else 0
        self._level = player.level if player is not None else 1
        self._xp_next = player.xp_to_next if player is not None else 0
        self._score = player.score if player is not None else 0
        self._wave = getattr(self.game, "wave", 1)
        self._time = getattr(self.game, "survival_time", 0.0)
        self._obstacles = list(getattr(self.game, "obstacles", ()))
        self._last_seen = {}
        self._snapshot_save()
        self._rebaseline()

    def _sync_player(self):
        player = getattr(self.game, "player", None)
        if player is not self._player:
            if getattr(self.game, "_ac_new_run", False) or self._player is None:
                self.game._ac_new_run = False
                self.reset()
                return
            # An impostor player (carrying whatever stats a client gave it) is never adopted:
            # the real one is put back.
            self.game.player = self._player
            self._raise("Player object replaced")

    def _rebaseline(self):
        player = self._player
        if player is None:
            self._baseline = {}
            return
        self._baseline = {attr: getattr(player, attr, None) for attr in _GUARDED_ATTRS}

    # ---------------------------------------------- engine authorisation funnels
    @staticmethod
    def _empty_save_grant():
        return {"coins": 0, "weapons": set(), "maps": set(), "cosmetics": set(), "levels": {}}

    def note_save(self, coins: int = 0, weapons=(), maps=(), cosmetics=(), levels=None):
        """The engine is about to change the save. It declares exactly what: the coin delta and
        which unlocks / meta levels it sets. Anything beyond the declaration is reverted."""
        g = getattr(self, "_save_grant", None) or self._empty_save_grant()
        g["coins"] += int(coins)
        g["weapons"].update(weapons or ())
        g["maps"].update(maps or ())
        g["cosmetics"].update(cosmetics or ())
        for k, v in (levels or {}).items():
            g["levels"][k] = int(v)
        self._save_grant = g
        self._save_legit = True

    def note_heal(self, amount: float):
        """The engine is about to heal the player by up to ``amount`` HP (legitimately)."""
        if _finite(amount) and amount > 0:
            self._heal_budget += float(amount)

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
            if getattr(self._cls, name, None) is not func:
                try:
                    setattr(self._cls, name, func)
                except Exception:
                    pass
                self._raise("Rule method replaced: " + name)
        for name, func in self._player_hooks:
            if getattr(self._pcls, name, None) is not func:
                try:
                    setattr(self._pcls, name, func)
                except Exception:
                    pass
                self._raise("Rule method replaced: Player." + name)
        for cls, hooks, label in ((self._proj_cls, self._proj_hooks, "Projectile."),
                                  (self._enemy_cls, self._enemy_hooks, "Enemy.")):
            for name, func in hooks:
                if getattr(cls, name, None) is not func:
                    try:
                        setattr(cls, name, func)
                    except Exception:
                        pass
                    self._raise("Rule method replaced: " + label + name)
        if _HOOK_FN is not None and getattr(self._enemy_cls, "take_damage", None) is not _HOOK_FN:
            # Something replaced the damage gate (the aura / NaN filter); put it back.
            self._enemy_cls.take_damage = _HOOK_FN
            self._raise("Damage gate replaced")

    # ---------------------------------------------------------------- sanity
    def _check_sanity(self):
        """Nothing finite the engine touches may become NaN / infinity / impossibly negative."""
        player = self._player
        if player is None:
            return
        if not _vec_ok(player.pos):
            player.pos = Vector2(self.last_pos)
            player.vel = Vector2(0, 0)
            self._raise("Invalid position")
        if not _vec_ok(player.vel):
            player.vel = Vector2(0, 0)
            self._raise("Invalid velocity")
        if not _finite(player.hp):
            player.hp = self._hp
            self._raise("Invalid HP")
        if not _finite(player.max_hp) or player.max_hp < 1:
            player.max_hp = max(1.0, self._max_hp)
            self._raise("Invalid max HP")
        for attr in ("iframes", "dash_timer", "dash_cd_timer", "shoot_timer",
                     "dash_momentum_timer", "burst_gap_timer", "lifesteal_charge", "spin_timer"):
            v = getattr(player, attr, 0.0)
            if not _finite(v):
                setattr(player, attr, 0.0)
                self._raise("Invalid timer: " + attr)
        for attr in _GUARDED_ATTRS:
            v = getattr(player, attr, None)
            if isinstance(v, (int, float)) and not _finite(v):
                try:
                    setattr(player, attr, self._baseline.get(attr, 0))
                except Exception:
                    pass
                self._raise("Invalid stat: " + _FLAG_LABELS.get(attr, attr))

    # ---------------------------------------------------------------- stat baseline
    def _check_attrs(self):
        player = self._player
        if player is None:
            return
        # A legitimate upgrade re-baselines ONLY the stats it actually changed. Anything else this
        # frame is a tamper even if an unrelated card was picked at the same time, so a cheat can
        # not bury a wiped stat under a real upgrade.
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
        # The magnet radius has its own hard ceiling inside apply_effects; enforce it here too so
        # a direct poke cannot grant map-wide pickup vacuuming.
        if _finite(player.magnet_bonus) and player.magnet_bonus > MAGNET_BONUS_CAP + 1e-6:
            player.magnet_bonus = MAGNET_BONUS_CAP
            base["magnet_bonus"] = MAGNET_BONUS_CAP
            self._raise("Magnet range overflow")

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
        # The dash cooldown timer can never exceed the longest cooldown the engine can set.
        if player.dash_cd_timer > DASH_COOLDOWN_BASE + 1e-3:
            player.dash_cd_timer = DASH_COOLDOWN_BASE
            self._raise("Dash cooldown overflow")
        # A zeroed shoot timer every frame means fire-rate tampering; cap it to a sane window.
        if player.shoot_timer > 4.0:
            player.shoot_timer = 4.0
            self._raise("Shoot timer overflow")
        # Burst is bounded by the weapon's burst plus any card; a huge burst_remaining fires a
        # round every frame through the burst path (which skips the cooldown gate).
        max_burst = max(0, player.get_burst_count()) + 4
        if player.burst_remaining > max_burst:
            player.burst_remaining = max_burst
            self._raise("Burst overflow")
        if player.spin_timer < 0.0 or player.spin_timer > 6.0:
            player.spin_timer = max(0.0, min(6.0, player.spin_timer))
        if player.lifesteal_charge < 0.0 or player.lifesteal_charge > player.max_hp + 1.0:
            player.lifesteal_charge = max(0.0, min(float(player.max_hp), player.lifesteal_charge))
        effects = player.effects
        for key in list(effects.keys()):
            if key not in EFFECT_KEYS:
                del effects[key]   # a power-up key the engine never creates
                self._raise("Unknown power-up")
        for key, cap in _EFFECT_CAPS:
            value = effects.get(key, 0.0)
            if not _finite(value) or value < 0.0:
                effects[key] = 0.0
            elif value > cap + 1e-6:
                effects[key] = cap
                self._raise("Power-up overflow")
        # Velocity is capped by the engine; recoil/knockback never approach this ceiling.
        vmax = DASH_SPEED * 1.5
        if player.vel.length_squared() > vmax * vmax:
            if player.vel.length_squared() > 1e-9:
                player.vel.scale_to_length(vmax)
            self._raise("Velocity overflow")

    # -------------------------------------------------------------------- time
    def _check_time(self):
        now = getattr(self.game, "survival_time", 0.0)
        if not _finite(now) or now < self._time - 1e-6 or now > self._time + 0.25:
            self.game.survival_time = self._time
            now = self._time
            self._raise("Time manipulation")
        self._time = now

    # ---------------------------------------------------------------------- vitals
    def _check_hp(self):
        player = self._player
        if player is None:
            return
        # Heal funnels report exactly how much they heal; that amount is the only budget.
        grant = getattr(player, "_ac_heal_amount", 0.0)
        if grant:
            player._ac_heal_amount = 0.0
            self.note_heal(grant)
        # A legit max-HP increase (a card / meta) lifts the ceiling the HP may track up to.
        if player.max_hp > self._max_hp:
            self._heal_budget += (player.max_hp - self._max_hp)
        self._max_hp = player.max_hp
        legit = getattr(player, "_ac_hp", False)
        if legit:
            player._ac_hp = False
        if player.hp > player.max_hp + 0.01:
            player.hp = player.max_hp
            self._raise("HP overflow")
        elif player.hp > 0.0 and player.hp > self._hp + 0.001:
            # Rising from below zero back to zero is the engine settling a death, not a heal.
            gained = player.hp - max(self._hp, 0.0)
            # HP may rise only through an engine heal funnel, and only by what it authorised.
            if legit and gained <= self._heal_budget + 1e-6:
                self._heal_budget = max(0.0, self._heal_budget - gained)
            else:
                player.hp = self._hp
                self._raise("Unexplained heal")
        self._heal_budget = min(self._heal_budget, float(player.max_hp))
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

    def _round_cap(self) -> float:
        player = self._player
        try:
            legit = float(player.get_bullet_speed()) if player is not None else 0.0
        except Exception:
            legit = 0.0
        if not _finite(legit):
            legit = 0.0
        return max(ROUND_SPEED_FLOOR, legit * ROUND_SPEED_HEADROOM)

    def _clamp_round_speeds(self):
        caps = ((self.game.projectiles, self._round_cap()),
                (self.game.enemy_projectiles, ENEMY_ROUND_SPEED_CAP))
        for store, cap in caps:
            cap2 = cap * cap
            for b in store:
                vel = getattr(b, "vel", None)
                if vel is None:
                    continue
                if not _vec_ok(vel):
                    b.vel = Vector2(0, 0)
                    self._raise("Invalid projectile velocity")
                elif vel.length_squared() > cap2:
                    b.vel.scale_to_length(cap)
                    self._raise("Projectile speed overflow")

    def _check_projectiles(self):
        # Floods: a client that appends thousands of rounds to crash the frame or blanket the map.
        extra = len(self.game.projectiles) - MAX_PROJECTILES_IMMORTAL
        if extra > 0:
            del self.game.projectiles[:extra]
            self._raise("Projectile flood")
        e_extra = len(self.game.enemy_projectiles) - MAX_PROJECTILES
        if e_extra > 0:
            del self.game.enemy_projectiles[:e_extra]
            self._raise("Enemy projectile flood")
        # Impossibly fast rounds tunnel through everything; clamp any round past the ceiling.
        self._clamp_round_speeds()

    def _check_enemies(self):
        charmed = []
        for e in self.game.enemies:
            if not _finite(e.hp):
                e.hp = 0.0
                self._raise("Invalid enemy HP")
            elif e.hp > e.hp_max + 0.01:
                e.hp = e.hp_max
                self._raise("Enemy HP overflow")
            if e.slow_frac > 0.9 + 1e-6:
                e.slow_frac = 0.9
                self._raise("Enemy perma-slow")
            if _vec_ok(e.pos):
                # Enemies the engine spawns are always inside the arena; a poked position outside
                # it (to park an ally off-map, say) is pulled back in.
                nx = min(max(e.pos.x, e.radius), ARENA_W - e.radius)
                ny = min(max(e.pos.y, e.radius), ARENA_H - e.radius)
                if abs(nx - e.pos.x) > 1.0 or abs(ny - e.pos.y) > 1.0:
                    e.pos.update(nx, ny)
                    self._raise("Enemy outside arena")
            else:
                e.pos = Vector2(ARENA_W / 2, ARENA_H / 2)
                self._raise("Invalid enemy position")
            if e.is_charmed():
                charmed.append(e)
        # The brainwashed herd is hard-capped by the engine; enforce it here so a direct poke of
        # charm timers cannot fill the arena with unkillable allies and stall every spawn.
        excess = len(charmed) - CHARM_MAX_ACTIVE
        if excess > 0:
            charmed.sort(key=lambda e: e.charm_timer)
            for e in charmed[:excess]:
                e.charm_timer = 0.0
            self._raise("Charm cap exceeded")
        # Bosses are charm-immune in the engine; a charmed boss is always a poke.
        from tankgame.entities.enemies import Boss
        for e in charmed:
            if isinstance(e, Boss):
                e.charm_timer = 0.0
                self._raise("Charmed boss")

    # ------------------------------------------------------------- mid-frame audits
    def pre_flight(self):
        """Before rounds move: no round may travel faster than the build can legally fire it."""
        self._clamp_round_speeds()

    def pre_reap(self):
        """Before dead enemies are reaped and paid out: HP lost must equal recorded damage."""
        for e in self.game.enemies:
            recorded = getattr(e, "_ac_dmg", None)
            if recorded is None or not _finite(recorded):
                e._ac_dmg = max(0.0, float(e.hp_max) - (float(e.hp) if _finite(e.hp) else 0.0))
                continue
            expected = float(e.hp_max) - float(recorded)
            hp = e.hp if _finite(e.hp) else -1.0e18
            tol = 0.5 + 1e-6 * abs(float(e.hp_max))
            if hp < expected - tol:
                # The enemy lost HP no engine damage path recorded: undo it, so a poked kill
                # never pays out score, XP or drops.
                e.hp = expected
                self._raise("Enemy HP tamper")

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
        # XP: the gain funnel declares exactly what it added; level-ups must then follow the
        # engine's own threshold curve, so XP can neither appear from nowhere nor be mis-spent.
        grant = getattr(player, "_ac_xp_grant", 0) or 0
        if grant:
            player._ac_xp_grant = 0
        if not _finite(grant) or grant < 0:
            grant = 0
        pool = self._xp + grant
        if not (_finite(player.xp) and _finite(player.xp_to_next) and _finite(player.level)):
            ok = False
        else:
            lvl, nxt, steps = self._level, self._xp_next, 0
            while lvl < player.level and steps < 64:
                pool -= nxt
                lvl += 1
                nxt = int(nxt * 1.18 + 18)
                steps += 1
            ok = (lvl == player.level and abs(pool - player.xp) < 1e-6
                  and nxt == player.xp_to_next and pool >= -1e-6)
        if not ok:
            # Keep the legitimately granted XP; drop everything the funnel did not account for.
            player.xp = self._xp + grant
            player.level = self._level
            player.xp_to_next = self._xp_next
            self._raise("XP/level injection")
        self._xp, self._level, self._xp_next = player.xp, player.level, player.xp_to_next

        # Score: exactly what the kill/boss funnel banked, never more, never less.
        sgrant = getattr(player, "_ac_score_grant", 0) or 0
        if sgrant:
            player._ac_score_grant = 0
        if not _finite(sgrant) or sgrant < 0:
            sgrant = 0
        if not _finite(player.score) or player.score != self._score + sgrant:
            player.score = self._score + sgrant
            self._raise("Score injection")
        self._score = player.score

        # Wave: advances exactly one per engine wave-clear (minigames lock it at setup).
        steps = getattr(self.game, "_ac_wave_steps", 0) or 0
        if steps:
            self.game._ac_wave_steps = 0
        if self.game.wave != self._wave + steps:
            self.game.wave = self._wave + steps
            self._raise("Wave injection")
        self._wave = self.game.wave

    # ------------------------------------------------------------------- save guard
    def _snapshot_save(self):
        save = self.game.save
        self._save_snap = (
            save.coins,
            dict(save.weapon_unlocks),
            dict(save.map_unlocks),
            dict(save.cosmetics_unlocked),
            dict(save.shop_levels),
        )

    def _save_diff_ok(self) -> bool:
        save = self.game.save
        g = getattr(self, "_save_grant", None) or self._empty_save_grant()
        coins0, wu0, mu0, cu0, sl0 = self._save_snap
        if not _finite(save.coins) or int(save.coins) != save.coins:
            return False
        if save.coins - coins0 != g["coins"]:
            return False
        from tankgame.data.shop import DEFAULT_COSMETICS
        free = set(DEFAULT_COSMETICS.values())
        for cur, prev, allowed, benign in ((save.weapon_unlocks, wu0, g["weapons"], ()),
                                           (save.map_unlocks, mu0, g["maps"], ()),
                                           (save.cosmetics_unlocked, cu0, g["cosmetics"], free)):
            if not isinstance(cur, dict):
                return False
            for key in set(cur) | set(prev):
                new, old = cur.get(key), prev.get(key)
                if new == old or not new:
                    continue   # unchanged, or something became locked: no benefit to anyone
                if key in allowed or key in benign:
                    continue
                return False
        if not isinstance(save.shop_levels, dict):
            return False
        for key in set(save.shop_levels) | set(sl0):
            try:
                new = int(save.shop_levels.get(key, 0))
                old = int(sl0.get(key, 0))
            except (TypeError, ValueError):
                return False
            if new <= old:
                continue
            if g["levels"].get(key) != new:
                return False
        return True

    def _check_save(self):
        save = self.game.save
        current = (save.coins, save.weapon_unlocks, save.map_unlocks,
                   save.cosmetics_unlocked, save.shop_levels)
        if current == self._save_snap:
            self._save_legit = False
            self._save_grant = self._empty_save_grant()
            return
        ok = self._save_diff_ok()
        self._save_legit = False
        self._save_grant = self._empty_save_grant()
        if ok:
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
        self._check_sanity()
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
            self._check_sanity()
            self._check_hp()
            self._check_speed(player, dt)
            self._check_dash(player)
        self._check_bounds()
        self._check_aura()
        self._check_projectiles()
        self._check_enemies()
        self._check_progress()
        self._check_save()
        self._check_time()

    def _check_speed(self, player, dt):
        if dt <= 0.0:
            return
        if not _vec_ok(player.pos):
            return   # sanity check already handled it
        speed = (player.pos - self.last_pos).length() / dt
        limit = self._legit_speed(player) * self.SPEED_TOLERANCE
        if player.is_dashing() or player.dash_momentum_timer > 0.0:
            limit = max(limit, DASH_SPEED * self.DASH_SPEED_TOLERANCE)
        if speed > limit:
            # Wall push-out can add a few px to a dash into cover; that is geometry, not speed.
            # (inflate() grows by half its argument per side, so double the per-side pad.)
            pad = PLAYER_RADIUS + 6
            for r in self.game.obstacles:
                if r.inflate(pad * 2, pad * 2).collidepoint(player.pos.x, player.pos.y):
                    self.last_pos = Vector2(player.pos)
                    return
            player.pos = Vector2(self.last_pos)
            player.vel = Vector2(0, 0)
            self._raise("Speed hack", f"{speed:.0f}px/s")
            return
        self.last_pos = Vector2(player.pos)

    def _check_dash(self, player):
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
            # A weapon swap resets the engine's own shot timer, so restart our windows too.
            self._weapon_id = player.weapon_id
            self._last_shot_at = -1.0e9
            self._shot_times.clear()
        # Sliding-window rate ceiling: catches a cheat that fires every frame through the burst
        # path (which skips the cooldown gate) or by zeroing the shoot timer.
        while self._shot_times and now - self._shot_times[0] > self.SHOT_WINDOW:
            self._shot_times.popleft()
        if len(self._shot_times) >= self.MAX_SHOTS_PER_WINDOW:
            self._raise("Fire-rate hack")
            return False
        if player.burst_remaining > 0 or player.burst_gap_timer > 0.0:
            self._last_shot_at = now
            self._shot_times.append(now)
            return True
        if not (player.trigger_held or player.auto_fire):
            self._raise("Shot without trigger")
            return False
        if now - self._last_shot_at < self.MIN_SHOT_GAP:
            self._raise("Shot before cooldown")
            return False
        self._last_shot_at = now
        self._shot_times.append(now)
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
# implementations if a client has monkey-patched them, so patching ``AntiCheat.guard`` / ``tick``
# / any of the checks out of the way simply gets healed on the next call.
# ---------------------------------------------------------------------------

_CANONICAL = {name: getattr(AntiCheat, name) for name in dir(AntiCheat)
              if not name.startswith("__") and callable(getattr(AntiCheat, name))}
_CANON_GUARD = _CANONICAL["guard"]
_CANON_TICK = _CANONICAL["tick"]


_CANON_PRE_FLIGHT = _CANONICAL["pre_flight"]
_CANON_PRE_REAP = _CANONICAL["pre_reap"]
_CANON_RAISE = _CANONICAL["_raise"]


def _self_heal() -> bool:
    """Restore every AntiCheat method a client may have swapped out. True if anything was."""
    healed = False
    for name, attr in _CANONICAL.items():
        if getattr(AntiCheat, name, None) is not attr:
            try:
                setattr(AntiCheat, name, attr)
                healed = True
            except Exception:
                pass
    return healed


def _heal_and_report(ac):
    if _self_heal():
        _CANON_RAISE(ac, "Referee tampered")
    if getattr(ac.game, "anticheat", None) is not ac:
        ac.game.anticheat = ac
        _CANON_RAISE(ac, "Referee detached")


def _strip_overrides(ac):
    """Remove any instance-level shadow of a gate method so the canonical class method runs."""
    d = getattr(ac, "__dict__", None)
    if not d:
        return
    for name in _GATE_METHODS:
        if name in d:
            try:
                del d[name]
                _CANON_RAISE(ac, "Referee gate replaced: " + name)
            except Exception:
                pass


def run_audit(ac, dt, playing):
    """Authoritative per-frame pass, driven directly from the main loop.

    The engine's own ``run_guard`` / ``run_tick`` entry points can be swapped out by a client to
    silence the referee; this pass is reached by a different name and re-runs the full checks, so
    the referee keeps policing even when those entry points have been detached. It heals every
    tampered method and instance override first, so a cheat that hooked the engine's combat/stat
    methods or neutered a gate is undone here.
    """
    _heal_and_report(ac)
    _strip_overrides(ac)
    _CANON_GUARD(ac)
    if playing:
        _CANON_TICK(ac, dt)


def run_guard(ac):
    """Run the canonical guard, healing the class if it was tampered with."""
    _heal_and_report(ac)
    _CANON_GUARD(ac)


def run_tick(ac, dt):
    _heal_and_report(ac)
    _CANON_TICK(ac, dt)


def run_preflight(ac):
    _heal_and_report(ac)
    _CANON_PRE_FLIGHT(ac)


def run_prereap(ac):
    _heal_and_report(ac)
    _CANON_PRE_REAP(ac)
