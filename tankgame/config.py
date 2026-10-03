"""All tunable constants and the shared colour palette.

Everything here is data - no pygame drawing, no imports from other tankgame modules - so this is a
safe leaf that any other module can import.

Note: ``WIDTH``/``HEIGHT`` are the *logical* viewport size. ``tankgame.viewport`` rewrites them
once at startup to match the monitor's aspect ratio, and that happens before any module does
``from tankgame.config import *``, so everyone sees the final value.
"""

from __future__ import annotations

import math
import random
import time
import traceback
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pygame
from pygame.math import Vector2


WIDTH, HEIGHT = 1100, 650
TITLE = "Tank Game v1.5"
FPS_CAP = 144

RECOIL_MULT = 1.0 # Default = 1       (Recoil multiplier)
                  # Off = 0
RECOIL_MAX = 165.0  # hardest a single shot can ever shove you
SAVE_PATH = "save.json"
LEADERBOARD_LIMIT = 10

COINS_SCORE_DIV = 50
COINS_PER_WAVE = 4

ARENA_W, ARENA_H = 3000, 3000
BG_GRID_SIZE = 90

OBSTACLE_COUNT = 22
OBSTACLE_MIN = (80, 60)
OBSTACLE_MAX = (220, 180)

# Maps: rolled at random from the ones you own. Unlocked permanently with coins in the shop.
MAP_DEFAULT_ID = "classic"

# Colors - flat, low-contrast surfaces with a single accent. Clean over "arcade bevel".
C_BG = (13, 15, 21)
C_BG_2 = (18, 21, 29)
C_GRID = (23, 27, 37)
C_PANEL = (22, 25, 34)
C_PANEL_2 = (30, 34, 45)
C_TEXT = (238, 242, 250)
C_TEXT_DIM = (148, 158, 182)
C_ACCENT = (86, 226, 200)
C_ACCENT_2 = (255, 104, 168)
C_WARN = (250, 200, 88)
C_OK = (110, 232, 150)
C_ULTRA = (255, 208, 74)       # Ultra cards: warm gold so they read as special
C_CHARM = (255, 150, 240)      # Hypnotised "ally" enemies

C_PLAYER = (90, 255, 220)      # Cyan
C_PLAYER_ALT = (120, 180, 255)
C_CHASER = (255, 80, 150)      # Pink
C_RANGED = (120, 190, 255)     # Light Blue
C_TANK = (255, 190, 80)        # Orange/Yellow
C_SPRINTER = (160, 255, 120)   # Lime Green
C_DASHER = (210, 160, 255)     # Purple

C_PINK = (255, 105, 205)       # Boss retinue "pink" enemies

C_BOSS = (255, 85, 95)         # Red
C_BOSS_EDGE = (255, 190, 210)

C_BULLET = (240, 240, 255)
C_EBULLET = (255, 120, 90)
C_XP = (120, 255, 160)
C_HEALTH = (255, 90, 110)
C_WALL = (30, 34, 45)
C_WALL_EDGE = (58, 66, 86)
C_COIN = (255, 220, 120)

# Cosmetic palette
C_OUTLINE_NEON = (120, 255, 210)
C_OUTLINE_EMBER = (255, 170, 90)
C_OUTLINE_STEEL = (180, 200, 230)
C_BULLET_MINT = (120, 255, 210)
C_BULLET_VIOLET = (200, 140, 255)
C_BULLET_GOLD = (255, 215, 120)
C_TRAIL_SPARK = (255, 200, 140)
C_TRAIL_ION = (120, 200, 255)
C_EXPLOSION_PLASMA = (120, 200, 255)
C_EXPLOSION_MAGMA = (255, 140, 90)

PLAYER_RADIUS = 16
ENEMY_RADIUS_CHASER = 14
ENEMY_RADIUS_RANGED = 15
ENEMY_RADIUS_TANK = 20
ENEMY_RADIUS_SPRINTER = 11
ENEMY_RADIUS_DASHER = 16
ENEMY_RADIUS_PINK = 13

BULLET_RADIUS_PLAYER = 4
BULLET_RADIUS_ENEMY = 4

PLAYER_MOVE_ACCEL_RATE = 13.0   # 1/s: how fast velocity converges on the wished velocity
PLAYER_MOVE_STOP_RATE = 11.0    # 1/s: how fast the tank coasts to a stop with no input
PLAYER_MAX_SPEED_BASE = 360.0

PLAYER_MAX_HP_BASE = 7
PLAYER_IFRAMES = 0.70

DASH_SPEED = 1000.0
DASH_TIME_BASE = 0.16
DASH_COOLDOWN_BASE = 1.15

WAVE_TIME_BASE = 15 # Originally 18, now 15    (Wave time)
RAPID_WAVE_TIME = 3.0   # "Rapid" minigame: waves last three seconds

# Difficulty ramping: reduced by ~30% (slower) by increasing the ramp time
DIFFICULTY_RAMP_TIME = 400.0 # 400s to reach "hard" instead of 180s

CHASER_SPEED_BASE, CHASER_SPEED_HARD = 140.0, 300.0
RANGED_SPEED_BASE, RANGED_SPEED_HARD = 110.0, 240.0
TANK_SPEED_BASE, TANK_SPEED_HARD = 75.0, 160.0
SPRINTER_SPEED_BASE, SPRINTER_SPEED_HARD = 175.0, 360.0
DASHER_SPEED_BASE, DASHER_SPEED_HARD = 115.0, 255.0

SPAWN_RATE_BASE = 1.35
SPAWN_RATE_HARD = 0.9
SPAWN_RATE_WAVE_BONUS = 0.008

ENEMY_HP_BASE_MUL = 1.0
ENEMY_HP_HARD_MUL = 1.3

ENEMY_CAP_BASE = 7
ENEMY_CAP_HARD = 20

RANGED_MAX_SHOOT_DIST = 520.0
RANGED_SHOOT_IF_ONSCREEN_MARGIN = 60
RANGED_LOS_ENABLED = True

RANGED_BULLET_SPEED_BASE = 470.0
RANGED_BULLET_LIFETIME = 1.55
RANGED_DAMAGE_BASE = 1
RANGED_DAMAGE_HARD = 2

RANGED_COOLDOWN_MIN = 1.10
RANGED_COOLDOWN_MAX = 1.55

XP_ORB_VALUE_BASE = 12
XP_ORB_RADIUS = 8
HEALTH_PACK_AMOUNT = 1
HEALTH_PACK_RADIUS = 10

PICKUP_ATTRACT_FORCE = 900.0
PICKUP_ATTRACT_DIST_BASE = 190.0

POWERUP_SPAWN_MIN = 20.0
POWERUP_SPAWN_MAX = 34.0
POWERUP_MAX_ON_MAP = 2
POWERUP_RADIUS = 12

POWERUP_DURATION_DAMAGE = 10.0
POWERUP_DURATION_RAPID = 8.0
POWERUP_DURATION_SPEED = 10.0
POWERUP_DURATION_SHIELD = 6.0

UI_PAD = 16

UPGRADE_BOX_PADDING = 18
UPGRADE_LINE_SPACING = 6
UPGRADE_RIGHT_LABEL_WIDTH = 160

HIT_PARTICLE_COUNT = 10
PARTICLE_LIFE = 0.35
SHAKE_HIT = 10.0
SHAKE_DECAY = 24.0

PLAYER_ENEMY_MIN_DIST_EPS = 1.0
PLAYER_ENEMY_PUSH_STRENGTH = 1.0
ENEMY_SEPARATION_CELL = 120
ENEMY_SEPARATION_SOFT = 1.15
ENEMY_SEPARATION_FORCE = 2.2

AUDIO_ENABLED_DEFAULT = True

# Performance / safety caps
MAX_PROJECTILES = 700
# Immortal rounds (Endless Shells / Absolute Bounce) need headroom, otherwise the cap recycles
# them away and they look like they still expire.
MAX_PROJECTILES_IMMORTAL = 1600
MAX_PARTICLES = 900
MAX_FLOAT_TEXTS = 90
SFX_MIN_INTERVAL = 0.030

# Cannon "Siege Breaker": a borrowed copy on a splash-less tank still needs something to detonate.
PIERCE_SPLASH_FALLBACK_RADIUS = 70.0

# Tank traits
POINT_BLANK_RANGE = 160.0       # shotgun trait range
BARREL_EAT_RADIUS = 74.0        # windscreen wiper clears enemy shots this close to the player

# Elite enemies (tougher, golden, only later on)
ELITE_MIN_WAVE = 6
ELITE_CHANCE_BASE = 0.06
ELITE_CHANCE_HARD = 0.14
ELITE_HP_MUL = 2.2
ELITE_SCORE_MUL = 2.5
ELITE_RADIUS_MUL = 1.12
ELITE_POWERUP_CHANCE = 0.25

# Spawning safety
ENEMY_SPAWN_DIST = 900.0        # preferred distance from the player
ENEMY_SPAWN_ATTEMPTS = 32
ENEMY_SPAWN_EDGE_MARGIN = 70    # keep spawns inside the arena
BOSS_SPAWN_DIST = 620.0

# Boss rules
BOSS_EVERY_WAVES = 10
BOSS_GRACE_AFTER_DEATH = 3  # seconds where normal spawning is paused after boss dies

# Wave mutators: one announced twist per wave, so difficulty spikes are readable, not random.
MUTATOR_MIN_WAVE = 3
MUTATOR_CHANCE = 0.50

# Ultra cards: overpowered, tank-specific, and very rare. 1% at the start of a run, +0.5% each wave.
ULTRA_CHANCE_BASE = 0.01
ULTRA_CHANCE_PER_WAVE = 0.005
ULTRA_CHANCE_MAX = 0.40

# Gravity Well pull (px/s at full strength) and Homing steer rate.
# Kept moderate: the tanks should bend shots / drag crowds, not vacuum or lock on.
GRAVITY_PULL_SPEED = 190.0
HOMING_TURN_RATE = 2.2
HOMING_TURN_CAP = 0.16

# Drones (Nanite Swarm)
DRONE_ORBIT_RADIUS = 62.0
DRONE_FIRE_CD = 0.55
DRONE_RANGE = 340.0
DRONE_BULLET_DAMAGE = 9.0
DRONE_MAX = 10

# Drone targeting: how each drone picks its victim. Free to switch in the pause menu.
DRONE_TARGET_MODES = [
    ("distance", "Distance", "Closest enemy to each drone"),
    ("mouse", "Mouse", "Enemy closest to your cursor"),
    ("angle", "Angle", "Enemy nearest your aim"),
    ("health", "Health", "Weakest enemy first"),
    ("threat", "Threat", "Toughest enemy first"),
]
DRONE_TARGET_MODE_DEFAULT = "distance"
# Drone Range power-up: widens the drones' reach for a while.
POWERUP_DURATION_DRONE_RANGE = 14.0
DRONE_RANGE_BOOST_MUL = 1.7

# Pink enemy (spawned in bulk by bosses)
PINK_HP_BASE = 30.0
PINK_SPEED_BASE = 150.0
PINK_SPEED_HARD = 235.0
PINK_DAMAGE_CONTACT = 1

# Hard ceiling on bullets per shot, regardless of how many pellet upgrades stack up.
MAX_PELLETS_PER_SHOT = 40
# The Windscreen "x5 output" ultra deliberately blows past that ceiling (bounded separately so a
# single shot can still never flood the field).
MAX_PELLETS_ULTRA = 90

# --- Ultra mechanics -------------------------------------------------------
# Sniper/Homing "Aimbot": fire at a predicted intercept point instead of the cursor. The target is
# chosen with the same read as the drone modes (reuses DRONE_TARGET_MODES in the pause menu).
AIMBOT_TARGET_MODE_DEFAULT = "distance"
# Rocket "Meteor Barrage": every shot calls down a meteor at the aim point.
METEOR_SHOT_TELEGRAPH = 0.5
METEOR_SHOT_DAMAGE = 9000.0
METEOR_SHOT_RADIUS = 175.0
# Flamethrower "Ashen Ground": shots scorch the floor into a lingering burn patch.
GROUND_FIRE_LIFE = 6.0
GROUND_FIRE_RADIUS = 54.0
GROUND_FIRE_DPS = 22.0
HAZARD_MAX = 64
# Nanite Swarm "Swarm Unleashed": +10 drones that leave the ring and hunt on their own.
DRONE_MAX_ULTRA = 22
DRONE_FREE_ROAM_SPEED = 320.0
DRONE_FREE_ROAM_KEEP = 46.0

# --- Player build stats -----------------------------------------------------
# Every combat stat a level-up card may touch. Player.apply_effects diffs this list to record
# exactly which stats a *legitimate* upgrade changed, and the AntiCheat uses it as the set of
# stats that may only change through that funnel. Keeping it in one place means a new card can
# never silently fall outside the referee's baselines.
BUILD_STAT_ATTRS = (
    # ultra flags
    "always_crit", "instant_kill", "aimbot", "bullet_life_inf", "spin_instant",
    "meteor_shot", "ground_fire", "chain_double", "pull_instant", "split_recursive",
    "drone_free_roam", "twin_shot", "charm_forever", "bounce_enemies", "infinite_bounces",
    "mine_homing", "retribution", "pierce_splash", "pellet_uncap",
    # weapon scalars
    "damage_mult", "fire_rate_mult", "bullet_speed_mult", "bullet_life_add",
    "move_speed_add", "piercing", "crit_chance", "crit_mult", "knockback_mult",
    "magnet_bonus", "extra_pellets", "spread_add", "splash_mult", "chain_bonus",
    "chain_mult_add", "bounce_bonus", "slow_add", "slow_time_add", "burn_dps_add",
    "burn_time_mult", "recoil_mult", "spin_bonus", "burst_bonus", "lifesteal_frac",
    "pull_add", "pull_radius_add", "split_add", "split_mult", "drones_add",
    "overpen_add", "charm_add", "charm_damage_add", "homing_add", "homing_range_add",
    "pellet_mul", "splash_add", "spread_set", "mine_trail", "dash_time_bonus",
    "max_hp", "flat_damage",
    # account multipliers (applied once at run start)
    "meta_damage_mul", "meta_move_mul", "meta_xp_mul", "meta_dash_mul", "meta_armor_mul",
    "meta_bulletspd_mul",
)

# Hypnosis: cap the number of simultaneous brainwashed allies. Beyond this the oldest charm is
# released, so a "permanent charm" build can never fill the arena with unkillable allies.
CHARM_MAX_ACTIVE = 8
