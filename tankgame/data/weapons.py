"""Weapon (tank) definitions + the WEAPONS table."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from tankgame.config import *


@dataclass
class WeaponDef:
    id: str
    name: str
    desc: str
    base_damage: int
    fire_cd: float
    bullet_speed: float
    bullet_life: float
    bullets_per_shot: int = 1
    spread_deg: float = 0.0
    bullet_radius: int = BULLET_RADIUS_PLAYER
    recoil: float = 30.0
    burst_count: int = 0
    burst_gap: float = 0.06
    splash_radius: float = 0.0   # rocket
    chain: int = 0               # number of extra chains
    chain_range: float = 0.0     # chain range
    chain_damage_mult: float = 0.65
    base_pierce: int = 0         # weapon provides pierce baseline
    radial: int = 0              # radial volley: fires this many shots around the compass
    pierces_walls: bool = False  # railgun: ignores cover entirely
    beam: float = 0.0            # drawn as a laser of this length instead of a dot


WEAPONS: Dict[str, WeaponDef] = {
    "pistol": WeaponDef(
        id="pistol",
        name="Pistol",
        desc="Reliable default tank",
        base_damage=14,
        fire_cd=0.16,
        bullet_speed=880.0,
        bullet_life=1.0,
        bullets_per_shot=1,
        spread_deg=0.0,
        bullet_radius=4,
        recoil=22.0,
    ),
    "cannon": WeaponDef(
        id="cannon",
        name="Cannon",
        desc="Slow fire, heavy hits",
        base_damage=28,
        fire_cd=0.44,
        bullet_speed=780.0,
        bullet_life=1.15,
        bullet_radius=5,
        recoil=62.0,
    ),
    "minigun": WeaponDef(
        id="minigun",
        name="Minigun",
        desc="Fast fire, lower damage",
        base_damage=7,
        fire_cd=0.070,
        bullet_speed=920.0,
        bullet_life=0.95,
        spread_deg=6.0,
        bullet_radius=3,
        recoil=9.0,
    ),
    "shotgun": WeaponDef(
        id="shotgun",
        name="Shotgun",
        desc="Wide spread, close-range shred",
        base_damage=9,
        fire_cd=0.55,
        bullet_speed=760.0,
        bullet_life=0.70,
        bullets_per_shot=5,
        spread_deg=20.0,
        bullet_radius=3,
        recoil=78.0,
    ),
    "rocket": WeaponDef(
        id="rocket",
        name="Rocket",
        desc="Explosive splash damage",
        base_damage=33, # Originally 28
        fire_cd=0.85,   # Originally 0.7
        bullet_speed=680.0,
        bullet_life=1.25,
        bullet_radius=5,
        recoil=92.0,
        splash_radius=95.0,
    ),
    "sniper": WeaponDef(
        id="sniper",
        name="Sniper",
        desc="Slow shots, massive damage",
        base_damage=50,
        fire_cd=0.78,
        bullet_speed=1500.0, # Originally 1450
        bullet_life=1.55,
        bullet_radius=3,     # Originally 4
        recoil=30.0,
        base_pierce=1,
    ),
     "flamethrower": WeaponDef(
        id="flamethrower",
        name="Flamethrower",
        desc="Constant damage to melt enemies",
        base_damage=1,
        fire_cd=0.05,        # 0.05
        bullet_speed=520,    # 520
        bullet_life=0.45,    # 0.45
        bullets_per_shot=6,  # 6
        spread_deg=18,       # 18
        bullet_radius=1,
        recoil=4,            # light, it fires constantly
    ),
     "windscreen_wiper": WeaponDef(
        id="windscreen_wiper",
        name="Windscreen Wiper",
        desc="A constant sweeping curtain of fire",
        base_damage=4,
        fire_cd=0.125,
        bullet_speed=640,
        bullet_life=0.8,
        bullets_per_shot=13,
        spread_deg=80,
        bullet_radius=3,
        recoil=3,
        base_pierce=1,
    ),
    "electricity": WeaponDef(
        id="electricity",
        name="Electricity",
        desc="Chains many enemies",
        base_damage=7,
        fire_cd=0.27,
        bullet_speed=920.0,
        bullet_life=0.85,
        bullet_radius=4,
        recoil=15.0,
        chain=6,
        chain_range=200.0,
        chain_damage_mult=0.85
    ),
    "tank": WeaponDef(
        id="tank",
        name="Tank",
        desc="Insane damage but very slow",
        base_damage=56, # Originally 52
        fire_cd=1.5,    # Originally 1.65
        bullet_speed=350.0,
        bullet_life=1,
        bullet_radius=7,
        recoil=165.0,
        splash_radius=150,
    ),
    "gravity_well": WeaponDef(
        id="gravity_well",
        name="Gravity Well",
        desc="Orbs drag enemies in, then detonate",
        base_damage=23,
        fire_cd=0.85,
        bullet_speed=360.0,
        bullet_life=1.7,
        bullet_radius=8,
        recoil=42.0,
        splash_radius=130.0,
    ),
    "prism": WeaponDef(
        id="prism",
        name="Prism",
        desc="Shots shatter into a spray on impact",
        base_damage=15,
        fire_cd=0.52,
        bullet_speed=940.0,
        bullet_life=1.1,
        bullet_radius=4,
        recoil=22.0,
    ),
    "nanite_swarm": WeaponDef(
        id="nanite_swarm",
        name="Nanite Swarm",
        desc="Orbiting drones fight alongside you",
        base_damage=7,
        fire_cd=0.30,
        bullet_speed=880.0,
        bullet_life=0.9,
        bullet_radius=3,
        recoil=9.0,
    ),
    "railgun": WeaponDef(
        id="railgun",
        name="Railgun",
        desc="A laser that crosses the whole map through walls",
        base_damage=52,
        fire_cd=0.98,
        bullet_speed=2400.0,
        bullet_life=2.4,
        bullet_radius=3,
        recoil=120.0,
        base_pierce=99,
        pierces_walls=True,
        beam=96.0,
    ),
    "homing": WeaponDef(
        id="homing",
        name="Homing",
        desc="Shots curve into the nearest enemy",
        base_damage=13,
        fire_cd=0.20,
        bullet_speed=680.0,
        bullet_life=1.6,
        bullet_radius=4,
        recoil=18.0,
    ),
    "hypnosis": WeaponDef(
        id="hypnosis",
        name="Hypnosis",
        desc="Turns the horde against itself",
        base_damage=14,
        fire_cd=0.24,
        bullet_speed=820.0,
        bullet_life=1.0,
        bullet_radius=5,
        recoil=15.0,
    ),
    "ricochet": WeaponDef(
        id="ricochet",
        name="Ricochet",
        desc="Shots bank off walls",
        base_damage=18,
        fire_cd=0.30,
        bullet_speed=720.0,
        bullet_life=1.7,
        bullet_radius=4,
        recoil=24.0,
    ),
    "mine_layer": WeaponDef(
        id="mine_layer",
        name="Mine Layer",
        desc="Drops mines that detonate on contact",
        base_damage=30,
        fire_cd=0.62,
        bullet_speed=0.0,
        bullet_life=8.0,
        bullet_radius=6,
        recoil=0.0,
        splash_radius=110.0,
    ),
    "siphon": WeaponDef(
        id="siphon",
        name="Siphon",
        desc="Drains HP back from its own damage",
        base_damage=13,
        fire_cd=0.22,
        bullet_speed=840.0,
        bullet_life=1.0,
        bullet_radius=4,
        recoil=17.0,
    ),
}
