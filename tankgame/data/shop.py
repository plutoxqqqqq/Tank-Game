"""Shop items, cosmetics and bundles + their lookups."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from tankgame.config import *


@dataclass
class ShopItemDef:
    id: str
    name: str
    desc: str
    max_level: int
    base_cost: int
    cost_mult: float
    kind: str = "meta"  # meta / weapon / cosmetic / settings
    weapon_id: str = ""


SHOP_ITEMS = [
    # META
    ShopItemDef("meta_damage", "+5% Base Damage", "Permanent: increases starting damage.", 10, 40, 1.35, "meta"),
    ShopItemDef("meta_move", "+5% Move Speed", "Permanent: increases starting speed.", 10, 40, 1.35, "meta"),
    ShopItemDef("meta_hp", "+1 Max HP", "Permanent: increases starting max HP.", 5, 80, 1.50, "meta"),
    ShopItemDef("meta_xp", "+5% XP Gain", "Permanent: gain more XP from orbs.", 10, 35, 1.35, "meta"),
    ShopItemDef("meta_dash", "-5% Dash Cooldown", "Permanent: dash comes back faster.", 10, 45, 1.35, "meta"),
    ShopItemDef("meta_armor", "+10% Damage Resistance", "Permanent: take less damage.", 10, 45, 1.35, "meta"),
    ShopItemDef("meta_bulletspeed", "+5% Bullet Speed", "Permanent: faster bullets.", 10, 30, 1.35, "meta"),

    # WEAPONS (unlocks)
    ShopItemDef("unlock_cannon", "Unlock: Cannon", "Slow fire, heavy hits", 1, 110, 1.0, "weapon", weapon_id="cannon"),
    ShopItemDef("unlock_minigun", "Unlock: Minigun", "Fast fire, lower damage", 1, 150, 1.0, "weapon", weapon_id="minigun"),
    ShopItemDef("unlock_shotgun", "Unlock: Shotgun", "Wide spread close-range", 1, 200, 1.0, "weapon", weapon_id="shotgun"),
    ShopItemDef("unlock_rocket", "Unlock: Rocket", "Splash damage explosives", 1, 260, 1.0, "weapon", weapon_id="rocket"),

    # NEW
    ShopItemDef("unlock_sniper", "Unlock: Sniper", "Slow shots, massive damage", 1, 200, 1.0, "weapon", weapon_id="sniper"),
    ShopItemDef("unlock_flamethrower", "Unlock: Flamethrower", "Constant damage to melt enemies", 1, 300, 1.0, "weapon", weapon_id="flamethrower"),
    ShopItemDef("unlock_electricity", "Unlock: Electricity", "Chains many enemies", 1, 400, 1.0, "weapon", weapon_id="electricity"),
    ShopItemDef("unlock_windscreen_wiper", "Unlock: Windscreen Wiper", "Wipes the map clean...", 1, 2500, 1.0, "weapon", weapon_id="windscreen_wiper"),
    ShopItemDef("unlock_tank", "Unlock: Tank", "Insane damage but very slow", 1, 390, 1.0, "weapon", weapon_id="tank"),
    ShopItemDef("unlock_ricochet", "Unlock: Ricochet", "Shots bank off walls", 1, 350, 1.0, "weapon", weapon_id="ricochet"),
    ShopItemDef("unlock_mine_layer", "Unlock: Mine Layer", "Drops mines that detonate on contact", 1, 420, 1.0, "weapon", weapon_id="mine_layer"),
    ShopItemDef("unlock_siphon", "Unlock: Siphon", "Heals itself by dealing damage", 1, 380, 1.0, "weapon", weapon_id="siphon"),
    ShopItemDef("unlock_prism", "Unlock: Prism", "Shots shatter into a spray", 1, 460, 1.0, "weapon", weapon_id="prism"),
    ShopItemDef("unlock_gravity_well", "Unlock: Gravity Well", "Orbs drag enemies in, then blast", 1, 540, 1.0, "weapon", weapon_id="gravity_well"),
    ShopItemDef("unlock_railgun", "Unlock: Railgun", "Pierces the whole field", 1, 600, 1.0, "weapon", weapon_id="railgun"),
    ShopItemDef("unlock_nanite_swarm", "Unlock: Nanite Swarm", "Orbiting drones fight for you", 1, 660, 1.0, "weapon", weapon_id="nanite_swarm"),
    ShopItemDef("unlock_hypnosis", "Unlock: Hypnosis", "Brainwash the horde into allies", 1, 780, 1.0, "weapon", weapon_id="hypnosis"),
    ShopItemDef("unlock_homing", "Unlock: Homing", "Shots curve toward enemies", 1, 520, 1.0, "weapon", weapon_id="homing"),

    # MAPS (permanent unlocks; each run rolls one of the maps you own)
    ShopItemDef("map_open_field", "Map: Open Field", "Bare arena - room to kite", 1, 300, 1.0, "map", weapon_id="open_field"),
    ShopItemDef("map_pillars", "Map: Pillars", "A grid of cover blocks", 1, 500, 1.0, "map", weapon_id="pillars"),
    ShopItemDef("map_crowded", "Map: Crowded", "Dense clutter - tight and tense", 1, 700, 1.0, "map", weapon_id="crowded"),
    ShopItemDef("map_maze", "Map: Maze", "Long corridors to fight down", 1, 900, 1.0, "map", weapon_id="maze"),
    ShopItemDef("map_fortress", "Map: Fortress", "A fortified ring around the centre", 1, 1200, 1.0, "map", weapon_id="fortress"),
]

SHOP_ITEMS_BY_ID = {item.id: item for item in SHOP_ITEMS}
SHOP_ITEMS_BY_WEAPON = {item.weapon_id: item for item in SHOP_ITEMS if item.kind == "weapon"}
SHOP_ITEMS_BY_MAP = {item.weapon_id: item for item in SHOP_ITEMS if item.kind == "map"}


@dataclass
class CosmeticDef:
    id: str
    name: str
    desc: str
    category: str  # outline / bullet / trail / explosion
    cost: int
    color: Tuple[int, int, int]
    default: bool = False
    bundle_only: bool = False


DEFAULT_COSMETICS = {
    "outline": "outline_standard",
    "bullet": "bullet_standard",
    "trail": "trail_none",
    "explosion": "explosion_ember",
}

BUNDLE_ONLY_COSMETIC_VALUE = 150

COSMETICS = [
    CosmeticDef("outline_standard", "Standard Outline", "Clean default trim.", "outline", 0, C_ACCENT, default=True),
    CosmeticDef("outline_neon", "Neon Outline", "Bright cyan glow.", "outline", 120, C_OUTLINE_NEON),
    CosmeticDef("outline_ember", "Ember Outline", "Warm orange trim.", "outline", 140, C_OUTLINE_EMBER),
    CosmeticDef("outline_steel", "Steel Outline", "Cold metallic edge.", "outline", 0, C_OUTLINE_STEEL, bundle_only=True),
    CosmeticDef("bullet_standard", "Standard Rounds", "Classic bright shots.", "bullet", 0, C_BULLET, default=True),
    CosmeticDef("bullet_mint", "Mint Rounds", "Fresh neon bullets.", "bullet", 110, C_BULLET_MINT),
    CosmeticDef("bullet_violet", "Violet Rounds", "Electric violet shots.", "bullet", 130, C_BULLET_VIOLET),
    CosmeticDef("bullet_gold", "Gold Rounds", "Lux gilded shots.", "bullet", 0, C_BULLET_GOLD, bundle_only=True),
    CosmeticDef("trail_none", "No Trail", "Pure, clean movement.", "trail", 0, C_TEXT_DIM, default=True),
    CosmeticDef("trail_spark", "Spark Trail", "Short warm sparks.", "trail", 120, C_TRAIL_SPARK),
    CosmeticDef("trail_ion", "Ion Trail", "Cool ion streak.", "trail", 150, C_TRAIL_ION),
    CosmeticDef("explosion_ember", "Ember Burst", "Standard explosion flare.", "explosion", 0, C_WARN, default=True),
    CosmeticDef("explosion_plasma", "Plasma Burst", "Bright cyan burst.", "explosion", 170, C_EXPLOSION_PLASMA),
    CosmeticDef("explosion_magma", "Magma Burst", "Heavy orange blast.", "explosion", 0, C_EXPLOSION_MAGMA, bundle_only=True),
]

COSMETICS_BY_ID = {cosmetic.id: cosmetic for cosmetic in COSMETICS}


@dataclass
class BundleDef:
    id: str
    name: str
    desc: str
    weapons: List[str]
    meta: List[str]
    cosmetics: List[str]
    discount: float


BUNDLES = [
    BundleDef(
        "starter_arsenal",
        "Starter Arsenal",
        "A discounted mix of core firepower and extra durability.",
        weapons=["cannon", "prism"],
        meta=["meta_hp"],
        cosmetics=[],
        discount=0.15,
    ),
    BundleDef(
        "speed_demon",
        "Speed Demon",
        "A fast-paced bundle built for mobility and rapid fire.",
        weapons=["minigun"],
        meta=["meta_move", "meta_dash"],
        cosmetics=["bullet_mint"],
        discount=0.18,
    ),
    BundleDef(
        "heavy_metal",
        "Heavy Metal",
        "High-impact gear paired with rugged upgrades and exclusive cosmetics.",
        weapons=["tank"],
        meta=["meta_armor"],
        cosmetics=["outline_steel", "explosion_magma"],
        discount=0.22,
    ),
    BundleDef(
        "arc_surge",
        "Arc Surge",
        "A shocking bundle of experimental firepower and charged visuals.",
        weapons=["electricity", "railgun"],
        meta=["meta_bulletspeed"],
        cosmetics=["bullet_violet", "trail_ion"],
        discount=0.20,
    ),
]
