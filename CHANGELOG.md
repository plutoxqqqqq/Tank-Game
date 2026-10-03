# Changelog

All notable changes to Tank Game Rebirth, newest first.

> Tank Game — a top-down survival shooter in Pygame. Asset-free (all visuals are shapes) and
> audio-optional, with a fallback-safe sound layer.

## Collision, upgrades, hypnosis, homing/gravity, balance pass

- **Rounds no longer vanish at the last moment.** `_cull_projectiles` ran *before* the collision
  pass, so a shot whose lifetime elapsed on the frame it reached its target was deleted instead of
  connecting. Culling is now split: walls/off-arena are handled first, an expired round gets one
  final collision pass, and the dead are swept afterwards. Fast rounds and low-lifetime shots now
  reliably hit.
- **Upgrades can no longer overwrite each other.** The AntiCheat used to re-baseline *every* guarded
  stat whenever any card was picked, so a cheat (e.g. the injector's stale-base stat write) could
  wipe an ultra and get that wiped value "blessed" by an unrelated card. `Player.apply_effects` now
  diffs `BUILD_STAT_ATTRS` and records exactly which stats a card changed; the referee re-baselines
  only those. Cyclone (and every other ultra) now survives any later pick.
- **Hypnosis no longer stalls the game.** Charmed enemies are excluded from the enemy cap
  (`active_enemy_count`), so a permanent-charm build keeps spawning new hostiles, and a
  `CHARM_MAX_ACTIVE` cap releases the oldest charm so the arena can't fill with unkillable allies.
  Brainwashed allies' damage is now credited to the player (stats + lifesteal).
- **Brainwashed shooters can actually aim.** Charmed `Ranged` units now lead their target with
  `predict_intercept` instead of firing where the target was.
- **Homing and gravity tuned down.** `HOMING_TURN_RATE` 6.0 → 2.2 (cap 0.35 → 0.16 per frame) and
  `GRAVITY_PULL_SPEED` 430 → 190, so both bend shots / drag crowds instead of vacuuming or locking on.
- **Real balance pass.** A headless combat simulation (each tank firing at a respawning group of
  hostiles) measures DPS at early / mid / late upgrade tiers. Outliers were tuned across
  `weapons.py` (cannon, rocket, railgun, homing, hypnosis, ricochet, siphon, gravity well, prism,
  nanite) and `upgrades.py` (prism, flamethrower, rocket, railgun, homing, ricochet, gravity,
  hypnosis ultras). Final spread is ~2.1–2.6× between the strongest and weakest tank at every tier.
- **AntiCheat hardened (still zero false flags, ~32µs/frame).**
  - `Game` now drives it through `run_guard`/`run_tick`, which re-install every canonical method if a
    client monkey-patches the referee (`_self_heal`). The engine keeps a private `_referee` handle, so
    replacing `game.anticheat` does not detach it.
  - New invariants: `survival_time` may only advance with the frame (time manipulation reverted),
    player velocity is clamped to a legal ceiling, and per-stat re-baselining means a tamper cannot
    be laundered through a real upgrade.
  - Speed checks ignore frames where the tank is touching cover (a dash push-out is geometry, not a
    speed hack), removing the last rare false positive.

## Live injection + base-game AntiCheat

- **The cheat is no longer baked into the source.** Start the legit game (`python main.py`), then
  inject the menu into that *running* process from a second terminal (`python inject.py`). The
  injector finds the game's PID and hands it `inject.install()`, which hooks the live `Game` /
  `Player` classes and draws the menu onto the existing frame. Close and reopen the game and it is
  untouched again until you inject once more. `patch.py` is now just a cleanup tool that strips the
  old v2/v3 file patch if a copy still has it. Requires `psutil` + `pywin32` (Windows).
- **Base-game AntiCheat.** A new `tankgame/game/anticheat.py` referee watches the *live game state*
  and reverts anything the engine itself could not have produced. It is deliberately cheat-agnostic:
  it knows nothing about how a cheat is delivered (no menu/module/file assumptions), only the rules
  the engine guarantees, so a clean run can never trip a check and any client that breaks a rule is
  caught. It **only prevents** - it reverts the abnormal state and never kills the player. It runs
  before the player is updated each frame, so an overlay that swallows the event hook cannot slip a
  stat through. The whole referee costs ~38µs per frame.
  - **Rule integrity** — the engine never replaces its own combat/movement/stat methods, so a patched
    `damage_player` / `_handle_enemy_contact_player` / `spawn_player_shot` / `credit_player_damage`
    or `Player.update` / `get_move_speed` / `get_damage` / `get_fire_cooldown` / `get_pellets` /
    `get_dash_time` / `get_recoil` / ... (29 player methods + 6 game methods) is restored on sight.
  - **Stat baseline** — every build flag/scalar (ultra flags, damage/fire-rate/crit/recoil/pellet
    stats, max HP, meta multipliers, ...) is snapshotted whenever the engine changes it through its
    own upgrade funnel; any other change is reverted.
  - **Bounds** — values the engine caps (invulnerability frames, dash duration, the five power-up
    timers) are clamped back to their legal ceiling.
  - **Movement** — the tank can never travel further in a frame than its legal top speed (360 base,
    raised by move upgrades and the speed power-up; dash speed is exempt while dashing/coasting).
  - **Dash/fire** — dashes or shots before their cooldown are blocked, a shot with no trigger held is
    blocked, shot gaps below the engine's hard floor are refused, and dash duration is capped
    (this is what finally neutralises DashExtender).
  - **Damage accounting** — a player-sourced hit with zero knockback (a damage aura) is refused.
  - **Vitals** — HP never exceeds max and only rises through the engine's heal funnels (lifesteal,
    health packs, upgrades); an unexplained heal is reverted.
  - **World** — wall-clipping is pushed back out, injected obstacles are removed, and projectile
    floods are trimmed to the engine cap.
  - **Provenance** — XP, level, score, wave and the save (coins / unlocks / meta) only move through
    the engine's own funnels; anything else is reverted.
  - Violations are counted once per episode, so a sustained cheat is neutralised quietly instead of
    spamming the HUD.

## Ultra fixes, Nightmare minigame, Uninject

- **Ricochet shots now truly never die.** "Infinite Bank" only granted infinite bounces, so rounds
  still expired; it now also grants `bullet_life_inf`. Immortal rounds (Infinite Bank / Absolute
  Bounce / Endless Shells) get a much larger projectile allowance (1600 vs 700) and are recycled
  last, so the normal cap can no longer quietly delete them. The live weapon is also kept in
  lockstep with `weapon_id`, so a card can never leave the tank firing a stale default gun.
- **Borrowed ultras now work on every tank** (Ultra Only). Siege Breaker detonates on splash-less
  tanks, Collapse drags targets with a fallback pull, Overload arcs from chain-less tanks, Mega /
  Homing Mines grant the mine behaviour to any tank, and Legion / Swarm Unleashed finally produce
  drones without the Nanite Swarm trait.
- **New minigame: Nightmare.** Every spawn is a maxed wave-50 boss — normal enemies never appear,
  the wave clock is frozen at 50, and the boss count ramps up the longer you survive (180s / 600
  coins).
- **Uninject button** in the cheat's States tab: restores every wrapped game/player method, resets
  every overridden player field, deletes `.inject_cfg` and the bytecode cache, and detaches the menu
  from the running game.

## Inject tooling fixed + in-game cheat menu

- **The menu now lives inside the game.** `patch.py` wires `tankgame/game/app.py` to `inject.py`,
  which renders a glassy overlay directly onto the pygame frame. No second window, no external
  process — just run `python patch.py`, then `python main.py`, and press **RightShift** (or F1) in a
  match. Running `python inject.py` auto-applies the patch for you.
- **Fixed the inject bridge on Windows.** The old patch wrote its trigger/command files to hardcoded
  `/tmp/...` paths, so RightShift silently did nothing. The v3 patch is self-healing — it rebuilds
  from a clean `app.py.bak` (or strips an already-patched file) and is idempotent. Use
  `python patch.py --force` to re-apply.
- **No more pausing when the window loses focus** — alt-tabbing keeps the run going.
- **The GUI was rebuilt from scratch** with drag-to-move glass panels, category tabs, switch/slider
  rows, inline settings under each module, dropdown pickers, a SaveEditor modal, and an active-count
  readout. Module state persists in `.inject_cfg`.
- **Modules:** Combat — ProjectileAura (with Range + Target Sorting), GodMode, OneTap, AlwaysCrit,
  AimAssist, Aura (Range + Damage), AutoWin (aims, shoots, moves, dashes and picks upgrades).
  Movement — Speed, DashExploit, DashExtender, Velocity (no recoil/knockback). States — Upgrade,
  Wave, Spawn (dropdown for orbs, power-ups, enemies, structures and projectiles), Coins,
  UnlockEverything, SaveEditor. Tanks — the matching ultra module appears only while that tank is
  driven (Deadeye Protocol, Gatling God, Twin Lance, Swarm Unleashed, and the rest of the roster).

## Second-wave ultras, longer minigames

- Every tank now carries **two** ultra cards (38 total). The new ones: Pistol *Deadeye Protocol*
  (every shot crits), Cannon *Siege Breaker* (blast fires on every enemy pierced), Minigun
  *Gatling God* (no spin-up), Shotgun *Endless Shells* (pellets never expire), Rocket *Meteor
  Barrage* (each shot calls a meteor), Sniper *Dead Reckoning* (aimbot with lead modes),
  Flamethrower *Ashen Ground* (shots scorch the floor), Windscreen *Cyclone* (x5 output past the
  normal cap), Electricity *Overload* (every chain strikes twice), Tank *Executioner* (shots
  execute non-bosses outright), Gravity Well *Collapse* (enemies snap onto the orb), Prism
  *Fractal Shards* (shards split again), Nanite *Swarm Unleashed* (drones roam free, +10),
  Railgun *Twin Lance* (mirrored laser), Homing *Ghost Tracker* (aimbot), Hypnosis *Total Control*
  (permanent brainwashing), Ricochet *Absolute Bounce* (rebounds off walls, the arena edge AND
  enemies, endless life + pierce), Mine Layer *Homing Mines* (mines creep toward enemies), Siphon
  *Blood Price* (whoever damages you is detonated).
- **Ultra Only** now offers every ultra from every tank, and every effect is a plain player flag,
  so a card borrowed from another tank works exactly as written.
- **Minigames are 4x longer with 4x the payout** (e.g. Meteor Strike is 300s / 240 coins).
- Aimbot (Sniper/Homing) adds a free **lead-mode picker** in the pause menu, sharing the drone
  target modes (Distance / Mouse / Angle / Health / Threat).
- Scorched ground, roaming drones, homing mines and the new aimbot lead modes all get dedicated
  rendering/UI, and the verification suites were extended to cover every new mechanic: **681 smoke
  checks** (all passing), a clean soak run (0 errors) and the 400-trial ricochet regression (0 fails).

## Drone targeting, boss retinues, new minigames

- Fixed the Ricochet ultra ("Infinite Bank"): it made shots vanish on the first wall instead of
  bouncing forever. Infinite bounces are now honoured by the wall and arena reflectors.
- Audited every ultra card — unique names, one per tank at the time (the roster later grew to two
  per tank, 38 total — see the newest section) — and the smoke harness now asserts that applying
  each one actually changes the tank's stats.
- Bosses now arrive with a retinue of **pink** swarmers: one per wave number (wave 10 → 10, wave
  20 → 20, wave 40 → 40).
- New minigame **Rapid**: waves flip every 3 seconds.
- New minigame **Ultra Only**: every level-up offers nothing but ultra cards.
- Drones: "+1 Drone" now visibly slots into an **evenly spaced ring** (a shared orbit phase is
  re-indexed every frame instead of each drone keeping a stale angle).
- Drones: five **target modes** — Distance, Mouse, Angle, Health, Threat — switchable for free in
  the pause menu while driving the Nanite Swarm tank.
- New **Drone Range** power-up: widens the drones' reach by 70% for 14 seconds (only offered once
  you actually have drones).
- Minigame list layout reflowed so the result banner can no longer cover the rows.

## Restructure — package split + true fullscreen

- Split the 7,000-line `main.py` into the `tankgame` package: `config`, `util`, `audio`, `save`,
  `viewport`, plus `data/`, `entities/`, `art/`, `ui/` and `game/` subpackages. The `Game` class is
  assembled from **seventeen** single-purpose mixins (`app`, `display`, `meta`, `world`, `combat`,
  `progression`, `minigames`, `run`, `render`, and the eight `ui/screens/*` screens). `main.py` is a
  ~50-line launcher that also re-exports the public names, so `import main` keeps working for tooling
  and the test harness.
- Behaviour is unchanged: the smoke harness, the soak run and the 400-trial ricochet regression all
  pass against the split package.
- FULLSCREEN reworked: a borderless window at the monitor's native size (the way a maximised game
  fills the screen). The logical viewport tracks the monitor's aspect ratio at startup, so
  `pygame.SCALED` fills the whole screen with no black bars and no distortion.
- Docs: `tankgame/README.md` (layout), `requirements.txt`.

## Balance & mechanics pass — homing, gravity, hypnosis, bosses, GUI

- ✅ NEW TANK: **Homing** — shots curve toward the nearest enemy (Trait: Seeker). Exclusive cards
  *Smart Rounds* and *Predictive Aim* plus the *Swarm Intelligence* ultra crank the steering up hard,
  and it unlocks in Shop → WEAPONS as "Unlock: Homing".
- ✅ RAILGUN reworked into a true laser: a long red beam that crosses the WHOLE map and ignores walls
  entirely (`pierces_walls`), instead of a bullet that stops on cover.
- ✅ GRAVITY WELL pull rewritten: it now moves enemy POSITIONS (the old velocity-only pull was damped
  out every frame by the enemies' own AI, so orbs barely did anything). With a proper falloff curve
  and a much higher `GRAVITY_PULL_SPEED` the crowd visibly gets hauled into the blast.
- ✅ HYPNOSIS rework: a brainwashed enemy now keeps its OWN behaviour — a charmed blue shooter still
  shoots from range (at its former friends), a charger still charges. Everything chases a real enemy
  target instead of blindly walking into you. Ally rounds live in the player list and hurt enemies;
  charmed units also maul whatever they bump into (`charm_damage_mult` scales it).
- ✅ RECOIL polished: per-tank recoil values retuned and clamped by `RECOIL_MAX`, and the recoil/kick
  boosting upgrade is gone (Siege Shells is now pure damage + bullet speed).
- ✅ SIPHON nerfed: the tank heals 1 HP per 160 damage (was 1 per 70), its cards drain far slower
  (1/220, 1/280, 1/90) and total lifesteal is hard-capped at 0.12. The universal "Siphon Rounds" card
  is now 1 HP per 2000 damage (was 1 per 300), so it is a trickle, not a fountain.
- ✅ GLASS GAUNTLET: your damage is pinned to a flat 99 regardless of tank, upgrades or multipliers.
- ✅ MAZE MINIGAME REMOVED (the Maze MAP stays). The challenge roster has since grown to seven.
- ✅ BOSS PROGRESSION retuned: boss HP scales with stage AND wave, and their attacks get faster, wider
  and harder-hitting every stage — later bosses are a genuine threat instead of a speed-bump.
- ✅ MINIGAMES tab on the main menu: telegraphed challenges with escalating coin payouts, each with a
  real ending and a persisted clear count + best run — Meteor Strike (meteor rain, shorter and shorter
  warnings), Impossible Mode (three bosses, always, refilled as they die), Dash Only (no walking),
  Blitz (maximum spawn pressure), Glass Gauntlet (1 HP, flat 99), plus Rapid and Ultra Only (added
  later — see the drone/minigame section).
- ✅ FULLSCREEN: F11 or the Settings toggle. (Later reworked into a borderless window at the monitor's
  native size — see the restructure section.)
- ✅ ULTRAS tuned: unmistakably GOLD and genuinely rare — 1% at the start of a run, +0.5% per wave.
  "Chain Every Entity" is now unlimited in BOTH jumps and range (it really does hit everything).
- ✅ GUI REWRITE: flat, low-contrast surfaces, hairline borders and no more drop shadow on every
  label — menus, cards, buttons, tabs, HUD bars and the arena all share one clean house style. The
  balance pass flattened every remaining heavy 2px panel to the same hairline style.
- ✅ TANKS REDRAWN: real top-down armour with treads, a hull and a turret, and a barrel silhouette per
  weapon — Minigun triples, Railgun twins, Shotgun choke, Wiper blade, Gravity ring, Prism wedge,
  drone cluster, and so on. You can tell the tanks apart at a glance now.

## CHANGES (expansion pass 3 — ultras, new tanks, maps, focus):

- ✅ ULTRA CARDS: yellow, overpowered, tank-exclusive, and rare - and the odds climb the longer a run lasts.
  Full Rotation (wiper sprays 360°), Infinite Bank (endless ricochets), Bouncy Rounds, Chain Every Entity,
  Mega Mines (huge + a mine trail), Bullet Heaven (10x bullets) and more, one for every tank. They are
  kept out of the normal pool and never offered twice.
- ✅ ROSTER: retired the repetitive tanks (Tesla, Burst Rifle, Omni Pistol) and the Cryo Cannon. Five new
  gimmick tanks instead: Gravity Well (orbs drag enemies in), Prism (shots shatter), Nanite Swarm
  (orbiting drones fight for you), Railgun (pierces all, damage stacks per hit) and Hypnosis (hits
  brainwash enemies into temporary allies that attack their own kind).
- ✅ MAPS: six layouts (Classic, Open Field, Crowded, Pillars, Maze, Fortress). Every run rolls one of the
  maps you own; the rest unlock with coins from the new MAPS shop tab.
- ✅ FOCUS ON YOUR TANK: the card pool leans far harder on tank-exclusive cards (two per tank plus an ultra)
  and dropped the never-picked universals (Data Magnet, Momentum Surge).
- ✅ Windscreen Wiper fixed: it was firing 50 tiny rounds a shot straight into the projectile cap, so it
  stuttered, went silent, and melted the frame rate. It is now a bounded, constant curtain (and any spray
  tank recycles an old round at the cap instead of skipping the shot).

## CHANGES (expansion pass 2 — modifiers, tank identity, QoL):

- ✅ Wave mutators: from wave 3 a run can roll a wave twist (Swarm, Hardened, Overdrive, Elite Hunt) that
  scales spawns and pays a coin bonus if you clear it. Never repeats twice in a row, never on boss waves,
  and the bonus banks when the next wave starts.
- ✅ Tank bonuses on universal cards: the same card reads stronger on the tank it was built for (e.g. "+12%
  Damage" -> "+19% on the Tank"). The card shows a "▶ Tank: ..." line so the synergy is visible instead of
  hidden. Cards stay data-driven (UpgradeDef.tank_bonus).
- ✅ Four new trade-off cards: Glass Cannon, Second Wind, Siphon Rounds, Kinetic Slugs.
- ✅ New tank: Siphon - a fast, fragile leech gun (Trait: Vampiric - heals 1 HP per 70 damage), with its own
  exclusive card "Deep Draught". Lifesteal is now a first-class effect.
- ✅ QoL: pause screen shows a live build summary + run stats side by side; level-up cards hint at the tank
  synergy; R/ENTER restarts straight from the game-over screen; ricochet shots now correctly bank off the
  arena edges as well as walls (they used to die silently at the border).

## CHANGES (expansion pass 1 — new tanks, traits, mechanics):

- ✅ Tank traits: every tank now has an innate perk (Spin-Up, Point Blank, Executioner, Clean Sweep, Bank
  Shot, Blast Mines, ...) shown on its card and in the pause screen. Traits are data (TRAITS), so the
  engine only handles the handful that need real hooks.
- ✅ 16 tank-exclusive level-up cards (one per tank). The pool only ever contains the universal cards plus
  your own tank's, so the choice stays 3-from-13 instead of drowning in options.
- ✅ Upgrades are data driven now (UpgradeDef.effects + Player.apply_effects) - new cards need no code.
- ✅ Three new tanks: Cryo Cannon (slows), Ricochet (shots bank off walls), Mine Layer (armed mines).
- ✅ New mechanics: slow, burning damage-over-time, wall bounces, mines, and elite golden enemies from wave 6
  that hit harder and often drop a power-up.
- ✅ Weapons screen shows each tank's trait; level-up cards can be picked with 1/2/3; M mutes.
- ✅ Run summary on the game over screen (kills, damage, accuracy), and leaving a run from the pause menu now
  banks your coins instead of silently throwing them away.

## CHANGES (bug sweep + polish):

- ✅ MOVEMENT: the old model fought itself every frame (acceleration lerped toward the wished velocity, then
  friction multiplied the result), so the player topped out near 24% of PLAYER_MAX_SPEED_BASE and every
  enemy outran them from wave 1. Rebuilt as a predictable "converge on wished velocity, only coast when
  idle, hard speed cap" model.
- ✅ Bullets no longer get eaten by already-dead enemies, and fast shots use swept (segment) collision so
  sniper/omni shots can't tunnel straight through small enemies.
- ✅ The "+10% Damage Resistance" shop upgrade actually works now (id was "armor", code read "meta_armor").
- ✅ "Unlock: Windscreen Wiper" could never be bought (cost = inf, rendered as "inf coins") and pointed at a
  weapon id that does not exist.
- ✅ Enemies can no longer spawn on top of the camera when you hug an arena edge.
- ✅ Multiple level-ups in one frame used to grant a single upgrade — levels are queued now.
- ✅ Ranged enemies aimed with a stale distance; knockback is applied as a wall slide, not a full stop.
- ✅ Projectiles/particles/floating text are capped and SFX are rate-limited (no more frame drops from the
  flamethrower / windscreen wiper).
- ✅ GUI: translucency actually renders, boss bar no longer covers the HUD, HP pips auto-fit, wave + dash +
  power-up timers, damage-number toggle, menu/shop/mastery layout overlap fixes.
