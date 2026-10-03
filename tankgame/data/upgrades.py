"""Level-up card definitions + the UPGRADES table."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from tankgame.config import *


@dataclass
class UpgradeDef:
    """A level-up card.

    `effects` is applied by Player.apply_effects, so a new upgrade usually needs no new code.
    `weapon_id` makes a card exclusive to one tank - those only ever show up while driving it,
    which is how the level-up pool grows without ever feeling cluttered.

    `tank_bonus` is the other half of that idea: a universal card can pay extra while you drive a
    particular tank (and the card says so on its face). That deepens the pool without adding a
    single extra card to it, so a level-up still reads as three clean choices.
    """
    id: str
    name: str
    desc: str
    tag: str
    weapon_id: str = ""
    effects: Dict[str, float] = field(default_factory=dict)
    tank_bonus: Dict[str, Dict[str, float]] = field(default_factory=dict)
    tank_note: str = ""
    ultra: bool = False          # Ultra tier: overpowered, tank-exclusive, only via the ultra roll

    def bonus_for(self, weapon_id: str) -> Dict[str, float]:
        """Extra effects this card grants to the given tank (empty for everyone else)."""
        return self.tank_bonus.get(weapon_id, {})

    def bonus_note_for(self, weapon_id: str) -> str:
        return self.tank_note if self.bonus_for(weapon_id) else ""


UPGRADES = [
    # ---------------- universal ----------------
    UpgradeDef("damage", "Overcharged Rounds", "12% more damage per shot.", "DMG",
               effects={"damage_mul": 1.12}, tank_bonus={"tank": {"damage_mul": 1.06}},
               tank_note="TANK: +6% more damage"),
    UpgradeDef("fire_rate", "Rapid Trigger", "Shoot 12% faster.", "FR",
               effects={"fire_rate_mul": 1.12}, tank_bonus={"minigun": {"fire_rate_mul": 1.08}},
               tank_note="MINIGUN: +8% more fire rate"),
    UpgradeDef("bullet_speed", "Rail Assist", "Bullets travel 10% faster.", "BSPD",
               effects={"bullet_speed_mul": 1.10}, tank_bonus={"sniper": {"bullet_speed_mul": 1.10}},
               tank_note="SNIPER: +10% more bullet speed"),
    UpgradeDef("max_hp", "Reinforced Core", "Increase max HP by 1.", "HP",
               effects={"max_hp": 1}, tank_bonus={"tank": {"max_hp": 1}},
               tank_note="TANK: +1 extra max HP"),
    UpgradeDef("move_speed", "Neon Strides", "Move 20 units faster.", "MOVE",
               effects={"move_add": 20}, tank_bonus={"tank": {"move_add": 18}},
               tank_note="TANK: +18 more speed"),
    UpgradeDef("dash_cd", "Reflex Coil", "Dash cooldown reduced 8%.", "CD",
               effects={"dash_cd_mul": 0.92}, tank_bonus={"ricochet": {"dash_cd_mul": 0.93}},
               tank_note="RICOCHET: 7% shorter cooldown"),
    UpgradeDef("piercing", "Phase Ammo", "Bullets pierce +1 enemy.", "PIERCE",
               effects={"pierce": 1}, tank_bonus={"sniper": {"pierce": 1}},
               tank_note="SNIPER: +1 extra pierce"),
    UpgradeDef("crit", "Lucky Circuitry", "+4% crit chance.", "CRIT",
               effects={"crit_chance": 0.04}, tank_bonus={"pistol": {"crit_chance": 0.04}},
               tank_note="PISTOL: +4% more crit chance"),
    UpgradeDef("heal", "Emergency Patch", "Instantly heal 3 HP.", "HEAL",
               effects={"heal": 3}, tank_bonus={"siphon": {"heal": 1}},
               tank_note="SIPHON: +1 extra HP"),
    UpgradeDef("magnet", "Orb Magnet", "Pickups pull in from farther away.", "MAG",
               effects={"magnet": 35.0}, tank_bonus={"gravity_well": {"magnet": 30.0}},
               tank_note="GRAVITY WELL: +30 more pull"),

    # ---------------- universal trade-offs ----------------
    UpgradeDef("glass_cannon", "Glass Cannon", "+25% damage, but -1 max HP.", "RISK",
               effects={"damage_mul": 1.25, "max_hp": -1}, tank_bonus={"tank": {"max_hp": 1}},
               tank_note="TANK: keeps the HP"),
    UpgradeDef("second_wind", "Second Wind", "+2 max HP, but -6% damage.", "SAFE",
               effects={"max_hp": 2, "damage_mul": 0.94}, tank_bonus={"hypnosis": {"max_hp": 1}},
               tank_note="HYPNOSIS: +1 extra max HP"),
    UpgradeDef("siphon_rounds", "Siphon Rounds", "Heal 1 HP per 2000 damage dealt.", "LEECH",
               effects={"lifesteal": 1.0 / 2000.0}, tank_bonus={"siphon": {"lifesteal": 1.0 / 800.0}},
               tank_note="SIPHON: heals 2.5x faster"),

    # ---------------- tank exclusive ----------------
    UpgradeDef("ex_pistol", "Hollow Points", "+0.35 crit damage.", "PISTOL", "pistol", {"crit_mult": 0.35}),
    UpgradeDef("ex_cannon", "Siege Shells", "+30% damage, +10% bullet speed.", "CANNON", "cannon",
               {"damage_mul": 1.30, "bullet_speed_mul": 1.10}),
    UpgradeDef("ex_minigun", "Belt Fed", "+15% fire rate, faster spin-up.", "MINIGUN", "minigun",
               {"fire_rate_mul": 1.15, "spin_bonus": 0.25}),
    UpgradeDef("ex_shotgun", "Buckshot Loads", "+2 pellets, +8° spread.", "SHOTGUN", "shotgun",
               {"pellets": 2, "spread_add": 8.0}),
    UpgradeDef("ex_rocket", "Hot Load", "+35% blast radius, +15% damage.", "ROCKET", "rocket",
               {"splash_mul": 1.35, "damage_mul": 1.15}),
    UpgradeDef("ex_sniper", "Match Grade", "+30% damage, +20% bullet speed.", "SNIPER", "sniper",
               {"damage_mul": 1.30, "bullet_speed_mul": 1.20}),
    UpgradeDef("ex_flame", "Napalm", "+6 burn DPS, burns last 80% longer.", "FLAME", "flamethrower",
               {"burn_dps_add": 6.0, "burn_time_mul": 1.8}),
    UpgradeDef("ex_electric", "Superconductor", "+2 chains, +12% chain damage.", "ELEC", "electricity",
               {"chain": 2, "chain_mult_add": 0.12}),
    UpgradeDef("ex_tank", "Siege Mode", "+40% blast, -12% fire rate.", "TANK", "tank",
               {"splash_mul": 1.40, "fire_rate_mul": 0.88}),
    UpgradeDef("ex_wiper", "Rain Dance", "+35% rounds, +30% pellet damage.", "WIPER", "windscreen_wiper",
               {"pellet_mul": 1.35, "damage_mul": 1.30}),
    UpgradeDef("ex_ricochet", "Trick Shot", "+2 bounces, +1 pierce.", "BOUNCE", "ricochet",
               {"bounce": 2, "pierce": 1}),
    UpgradeDef("ex_mines", "Cluster Mines", "+1 mine per shot, +25% blast.", "MINES", "mine_layer",
               {"pellets": 1, "splash_mul": 1.25}),
    UpgradeDef("ex_siphon", "Deep Draught", "+12% damage, drains HP a little faster.", "SIPHON", "siphon",
               {"damage_mul": 1.12, "lifesteal": 1.0 / 220.0}),

    # ---------------- tank exclusive (second wave: one more per tank) ----------------
    UpgradeDef("ex2_pistol", "Fan The Hammer", "+18% fire rate, +3% crit chance.", "PISTOL", "pistol",
               {"fire_rate_mul": 1.18, "crit_chance": 0.03}),
    UpgradeDef("ex2_cannon", "Long Barrel", "+15% damage, +25% bullet speed.", "CANNON", "cannon",
               {"damage_mul": 1.15, "bullet_speed_mul": 1.25}),
    UpgradeDef("ex2_minigun", "Twin Barrels", "+1 bullet, wider spray.", "MINIGUN", "minigun",
               {"pellets": 1, "spread_add": 4.0, "damage_mul": 0.94}),
    UpgradeDef("ex2_shotgun", "Slug Rounds", "One heavy slug, tighter spread.", "SHOTGUN", "shotgun",
               {"pellets": -2, "damage_mul": 1.5, "spread_add": -8.0}),
    UpgradeDef("ex2_rocket", "Cluster Warhead", "+25% fire rate, +20% blast.", "ROCKET", "rocket",
               {"fire_rate_mul": 1.25, "splash_mul": 1.2, "damage_mul": 0.9}),
    UpgradeDef("ex2_sniper", "Armour Piercer", "+2 pierce, shots fly farther.", "SNIPER", "sniper",
               {"pierce": 2, "bullet_life_add": 0.3}),
    UpgradeDef("ex2_flame", "Pressurised Fuel", "+20% fire rate, tighter cone.", "FLAME", "flamethrower",
               {"fire_rate_mul": 1.2, "spread_add": -6.0, "bullet_life_add": 0.15}),
    UpgradeDef("ex2_wiper", "Streak Free", "+25% rounds, shots pierce.", "WIPER", "windscreen_wiper",
               {"pellet_mul": 1.25, "pierce": 1}),
    UpgradeDef("ex2_electric", "High Voltage", "+25% damage, better chaining.", "ELEC", "electricity",
               {"damage_mul": 1.25, "chain_mult_add": 0.1}),
    UpgradeDef("ex2_tank", "Dreadnought", "+2 max HP, tougher frame.", "TANK", "tank",
               {"max_hp": 2, "damage_mul": 1.15, "move_add": -20}),
    UpgradeDef("ex2_ricochet", "Angled Plating", "+1 bounce, 10% shorter dash cooldown.", "BOUNCE", "ricochet",
               {"bounce": 1, "dash_cd_mul": 0.90}),
    UpgradeDef("ex2_mines", "Wide Yield", "+40% blast, orbs pull to you.", "MINES", "mine_layer",
               {"splash_mul": 1.4, "magnet": 30.0}),
    UpgradeDef("ex2_siphon", "Capillary Burst", "Drains HP, +1 max HP.", "SIPHON", "siphon",
               {"lifesteal": 1.0 / 280.0, "max_hp": 1}),

    # ---------------- Homing (exclusive) ----------------
    UpgradeDef("ex_homing", "Smart Rounds", "Shots track enemies much harder.", "HOME", "homing",
               {"homing_add": 1.1, "homing_range_add": 90.0}),
    UpgradeDef("ex2_homing", "Predictive Aim", "Longer lock-on, +15% damage.", "HOME", "homing",
               {"homing_range_add": 150.0, "damage_mul": 1.15}),

    # ---------------- new tanks (exclusive) ----------------
    UpgradeDef("ex_gravity", "Event Horizon", "Wider, stronger pull, +20% blast.", "GRAV", "gravity_well",
               {"pull_radius_add": 90.0, "damage_mul": 1.2, "splash_mul": 1.2}),
    UpgradeDef("ex2_gravity", "Mass Driver", "+25% bullet speed, stronger pull.", "GRAV", "gravity_well",
               {"bullet_speed_mul": 1.25, "pull_add": 0.6}),
    UpgradeDef("ex_prism", "Beam Splitter", "+2 shards, +15% damage.", "PRISM", "prism",
               {"split_add": 2, "damage_mul": 1.15}),
    UpgradeDef("ex2_prism", "Kaleidoscope", "+3 shards, shards hit harder.", "PRISM", "prism",
               {"split_add": 3, "split_mult_mul": 1.15, "damage_mul": 0.9}),
    UpgradeDef("ex_nanite", "Hive Uplink", "+2 drones, +15% fire rate.", "NANO", "nanite_swarm",
               {"drones_add": 2, "fire_rate_mul": 1.15}),
    UpgradeDef("ex2_nanite", "Combat Algorithms", "+1 drone, +25% damage.", "NANO", "nanite_swarm",
               {"drones_add": 1, "damage_mul": 1.25}),
    UpgradeDef("ex_railgun", "Magnetic Accelerator", "+2 pierce, damage grows faster.", "RAIL", "railgun",
               {"pierce": 2, "overpen_add": 0.5, "damage_mul": 1.2}),
    UpgradeDef("ex2_railgun", "Overcharge", "+35% damage, slower cycling.", "RAIL", "railgun",
               {"damage_mul": 1.35, "fire_rate_mul": 0.9}),
    UpgradeDef("ex_hypno", "Deep Trance", "Brainwashing lasts 2.5s longer.", "HYPN", "hypnosis",
               {"charm_add": 2.5, "damage_mul": 1.1}),
    UpgradeDef("ex2_hypno", "Hive Mind", "Allies hit much harder.", "HYPN", "hypnosis",
               {"charm_add": 1.5, "charm_damage_add": 0.4}),

    # ---------------- ULTRA (overpowered, yellow, tank-exclusive, rare) ----------------
    UpgradeDef("ult_wiper", "Full Rotation", "Windscreen Wiper sprays a full 360\u00b0.", "ULTRA", "windscreen_wiper",
               {"spread_set": 360.0, "pellet_mul": 1.5, "pierce": 2, "bullet_life_add": 0.4}, ultra=True),
    UpgradeDef("ult_ricochet", "Infinite Bank", "Ricochet shots never stop bouncing - or dying.", "ULTRA", "ricochet",
               {"bounce_infinite": 1.0, "bullet_life_inf": 1.0, "damage_mul": 1.2}, ultra=True),
    UpgradeDef("ult_sniper", "Bouncy Rounds", "Sniper shots bounce off walls.", "ULTRA", "sniper",
               {"bounce": 3, "damage_mul": 1.25}, ultra=True),
    UpgradeDef("ult_electric", "Chain Every Entity", "Lightning leaps to every enemy, at any range.", "ULTRA", "electricity",
               {"chain_all": 1.0, "chain_mult_add": 0.2}, ultra=True),
    UpgradeDef("ult_mines", "Mega Mines", "Huge mines, and you lay a trail as you move.", "ULTRA", "mine_layer",
               {"splash_mul": 3.0, "splash_add": 120.0, "mine_trail": 1.0, "fire_rate_mul": 1.3}, ultra=True),
    UpgradeDef("ult_minigun", "Bullet Heaven", "Minigun fires 10x the bullets.", "ULTRA", "minigun",
               {"pellet_mul": 10.0, "spread_add": 6.0}, ultra=True),
    UpgradeDef("ult_pistol", "Perfect Aim", "+30% crit chance and +1.0 crit damage.", "ULTRA", "pistol",
               {"crit_chance": 0.30, "crit_mult": 1.0, "damage_mul": 1.15}, ultra=True),
    UpgradeDef("ult_cannon", "Earthshaker", "Massive shells with a huge blast.", "ULTRA", "cannon",
               {"damage_mul": 1.6, "splash_mul": 2.0, "splash_add": 90.0}, ultra=True),
    UpgradeDef("ult_shotgun", "Dragon's Breath", "A wall of burning pellets.", "ULTRA", "shotgun",
               {"pellets": 8, "spread_add": 10.0, "burn_dps_add": 12.0, "burn_time_mul": 2.0}, ultra=True),
    UpgradeDef("ult_rocket", "Tactical Nuke", "Enormous blast radius.", "ULTRA", "rocket",
               {"splash_mul": 2.5, "splash_add": 90.0, "damage_mul": 1.7}, ultra=True),
    UpgradeDef("ult_flame", "Firestorm", "Much bigger damage and far harder burns.", "ULTRA", "flamethrower",
               {"damage_mul": 1.55, "burn_dps_add": 10.0, "burn_time_mul": 1.8}, ultra=True),
    UpgradeDef("ult_tank", "Apocalypse", "Colossal shells, colossal boom.", "ULTRA", "tank",
               {"splash_mul": 3.0, "splash_add": 110.0, "damage_mul": 1.5}, ultra=True),
    UpgradeDef("ult_gravity", "Black Hole", "Drags the whole crowd into the blast.", "ULTRA", "gravity_well",
               {"pull_add": 1.8, "pull_radius_add": 200.0, "splash_mul": 2.4}, ultra=True),
    UpgradeDef("ult_prism", "Shatterstorm", "Shots explode into 6 harder shards.", "ULTRA", "prism",
               {"split_add": 6, "split_mult_mul": 1.1}, ultra=True),
    UpgradeDef("ult_nanite", "Legion", "Five more drones, all deadlier.", "ULTRA", "nanite_swarm",
               {"drones_add": 5, "damage_mul": 1.3}, ultra=True),
    UpgradeDef("ult_railgun", "Annihilator", "Rips through everything, hits stack hard.", "ULTRA", "railgun",
               {"overpen_add": 1.0, "damage_mul": 2.1, "pierce": 5}, ultra=True),
    UpgradeDef("ult_hypno", "Mass Hysteria", "Brainwashing lasts ages and allies rampage.", "ULTRA", "hypnosis",
               {"charm_add": 3.0, "charm_damage_add": 1.0, "damage_mul": 1.3}, ultra=True),
    UpgradeDef("ult_siphon", "Monsoon", "Doubles damage and drains faster.", "ULTRA", "siphon",
               {"damage_mul": 2.0, "lifesteal": 1.0 / 90.0, "max_hp": 1}, ultra=True),
    UpgradeDef("ult_homing", "Swarm Intelligence", "Shots hunt relentlessly and pierce.", "ULTRA", "homing",
               {"homing_add": 3.0, "homing_range_add": 260.0, "pierce": 2, "damage_mul": 1.5}, ultra=True),

    # ---------------- ULTRA, second wave (one more per tank) ----------------
    # Every effect here is a plain player flag, so a card pulled from another tank in the
    # "Ultra Only" minigame still works exactly as written.
    UpgradeDef("ult2_pistol", "Deadeye Protocol", "Every single shot is a critical hit.", "ULTRA", "pistol",
               {"always_crit": 1.0, "crit_mult": 0.5, "damage_mul": 1.1}, ultra=True),
    UpgradeDef("ult2_cannon", "Siege Breaker", "Shells punch through and blast every enemy on the way.", "ULTRA", "cannon",
               {"pierce": 4, "pierce_splash": 1.0, "splash_mul": 1.4, "splash_add": 40.0}, ultra=True),
    UpgradeDef("ult2_minigun", "Gatling God", "No spin-up at all, and far faster.", "ULTRA", "minigun",
               {"spin_instant": 1.0, "fire_rate_mul": 1.25, "damage_mul": 1.1}, ultra=True),
    UpgradeDef("ult2_shotgun", "Endless Shells", "Pellets never expire - they only stop on a wall.", "ULTRA", "shotgun",
               {"bullet_life_inf": 1.0, "pellets": 4, "damage_mul": 1.15}, ultra=True),
    UpgradeDef("ult2_rocket", "Meteor Barrage", "Every shot calls a meteor down on the aim point.", "ULTRA", "rocket",
               {"meteor_shot": 1.0, "damage_mul": 1.2}, ultra=True),
    UpgradeDef("ult2_sniper", "Dead Reckoning", "Aimbot: shots lead the target perfectly.", "ULTRA", "sniper",
               {"aimbot": 1.0, "damage_mul": 1.35, "bullet_speed_mul": 1.15}, ultra=True),
    UpgradeDef("ult2_flame", "Ashen Ground", "Shots scorch the floor - anyone crossing burns.", "ULTRA", "flamethrower",
               {"ground_fire": 1.0, "burn_dps_add": 8.0, "damage_mul": 1.3}, ultra=True),
    UpgradeDef("ult2_wiper", "Cyclone", "Five times the output in every sweep.", "ULTRA", "windscreen_wiper",
               {"pellet_mul": 5.0, "pellet_uncap": 1.0, "damage_mul": 1.2}, ultra=True),
    UpgradeDef("ult2_electric", "Overload", "Every chain lightning strikes twice.", "ULTRA", "electricity",
               {"chain_double": 1.0, "chain_mult_add": 0.3, "damage_mul": 1.2}, ultra=True),
    UpgradeDef("ult2_tank", "Executioner", "Shots execute any enemy outright - bosses excepted.", "ULTRA", "tank",
               {"instant_kill": 1.0, "fire_rate_mul": 1.15}, ultra=True),
    UpgradeDef("ult2_gravity", "Collapse", "Enemies snap straight onto the orb the instant it fires.", "ULTRA", "gravity_well",
               {"pull_instant": 1.0, "pull_radius_add": 120.0, "splash_mul": 1.9}, ultra=True),
    UpgradeDef("ult2_prism", "Fractal Shards", "Even the shards split again.", "ULTRA", "prism",
               {"split_recursive": 1.0, "split_add": 3, "damage_mul": 1.15}, ultra=True),
    UpgradeDef("ult2_nanite", "Swarm Unleashed", "Drones leave the ring to hunt, and you gain ten more.", "ULTRA", "nanite_swarm",
               {"drone_free_roam": 1.0, "drones_add": 10, "damage_mul": 1.25}, ultra=True),
    UpgradeDef("ult2_railgun", "Twin Lance", "Each shot fires a mirrored laser the other way.", "ULTRA", "railgun",
               {"twin_shot": 1.0, "damage_mul": 1.4, "pierce": 4}, ultra=True),
    UpgradeDef("ult2_homing", "Ghost Tracker", "Aimbot: homing rounds are launched already on target.", "ULTRA", "homing",
               {"aimbot": 1.0, "homing_add": 1.5, "damage_mul": 1.45}, ultra=True),
    UpgradeDef("ult2_hypno", "Total Control", "Brainwashing never wears off - ever.", "ULTRA", "hypnosis",
               {"charm_forever": 1.0, "charm_damage_add": 0.7, "damage_mul": 1.2}, ultra=True),
    UpgradeDef("ult2_ricochet", "Absolute Bounce", "Rounds rebound off walls, the arena edge AND enemies, and live forever.", "ULTRA", "ricochet",
               {"bounce_infinite": 1.0, "bounce_enemies": 1.0, "pierce": 99, "bullet_life_inf": 1.0,
                "damage_mul": 1.5}, ultra=True),
    UpgradeDef("ult2_mines", "Homing Mines", "Armed mines creep toward the nearest enemy.", "ULTRA", "mine_layer",
               {"mine_homing": 1.0, "splash_mul": 1.6, "splash_add": 40.0, "fire_rate_mul": 1.2}, ultra=True),
    UpgradeDef("ult2_siphon", "Blood Price", "Whenever you take damage, the attacker is detonated.", "ULTRA", "siphon",
               {"retribution": 1.0, "damage_mul": 1.2, "max_hp": 1}, ultra=True),
]

UPGRADES_BY_ID: Dict[str, UpgradeDef] = {up.id: up for up in UPGRADES}
