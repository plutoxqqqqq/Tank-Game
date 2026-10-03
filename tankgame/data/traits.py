"""Innate per-tank traits + lookup."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from tankgame.config import *


@dataclass
class TraitDef:
    """Innate perk that comes with a tank.

    `desc` is what the player reads; `data` holds the numbers the engine consumes, so most
    traits need no code at all (slow, burn, bounces, mines, ...).
    """
    id: str
    name: str
    desc: str
    data: Dict[str, float] = field(default_factory=dict)


TRAITS: Dict[str, TraitDef] = {
    "pistol": TraitDef("deadeye", "Deadeye", "+8% crit chance", {"crit_add": 0.08}),
    "cannon": TraitDef("breach", "Breach", "+25% damage to healthy targets", {"damage_vs_high_hp": 1.25}),
    "minigun": TraitDef("spin_up", "Spin-Up", "Fire rate climbs while held down",
                        {"spin_min": 0.80, "spin_max": 1.20, "spin_time": 1.5}),
    "shotgun": TraitDef("point_blank", "Point Blank", "+30% damage within 160px", {"point_blank": 1.30}),
    "rocket": TraitDef("demolition", "Demolition", "+25% blast radius", {"splash_mul": 1.25}),
    "sniper": TraitDef("executioner", "Executioner", "+50% damage below 40% HP", {"executioner": 1.50}),
    "flamethrower": TraitDef("ignite", "Ignite", "Sets enemies alight", {"burn_dps": 10.0, "burn_time": 1.5}),
    "windscreen_wiper": TraitDef("clean_sweep", "Clean Sweep", "Wipes enemy shots near you", {"eats_bullets": 1.0}),
    "electricity": TraitDef("conduction", "Conduction", "+1 chain, +80 chain range",
                            {"chain_add": 1.0, "chain_range_add": 80.0}),
    "tank": TraitDef("juggernaut", "Juggernaut", "+60% knockback dealt", {"knockback_mul": 1.6}),
    "gravity_well": TraitDef("singularity", "Singularity", "Shots drag nearby enemies inward",
                             {"pull": 1.0, "pull_radius": 175.0}),
    "prism": TraitDef("refraction", "Refraction", "Shots burst into 7 shards on impact",
                      {"split": 7.0, "split_mult": 0.55}),
    "nanite_swarm": TraitDef("swarm_protocol", "Swarm Protocol", "Maintains 3 orbiting combat drones",
                              {"drones": 3.0}),
    "railgun": TraitDef("overpenetration", "Overpenetration", "+8% damage for every enemy pierced",
                        {"overpen": 0.08}),
    "hypnosis": TraitDef("suggestion", "Suggestion", "Hits brainwash enemies into allies for 3.2s",
                         {"charm": 3.2}),
    "homing": TraitDef("seeker", "Seeker", "Shots steer toward nearby enemies",
                       {"homing": 1.0, "homing_range": 430.0}),
    "ricochet": TraitDef("bank_shot", "Bank Shot", "Shots bounce off walls twice", {"bounces": 2.0}),
    "mine_layer": TraitDef("blast_mines", "Blast Mines", "Mines arm where they land", {"mine": 1.0}),
    "siphon": TraitDef("vampiric", "Vampiric", "Heals 1 HP per 160 damage dealt", {"lifesteal": 1.0 / 160.0}),
}


def trait_of(weapon_id: str) -> TraitDef:
    return TRAITS.get(weapon_id, TraitDef("", "None", "", {}))
