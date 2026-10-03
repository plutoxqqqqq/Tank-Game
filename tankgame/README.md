# tankgame package layout

The game is a single pygame program split by responsibility. Dependencies flow strictly
downward, so there are no import cycles:

```
config, util, viewport   (leaf: constants + helpers + logical screen sizing)
   ↓
data                     (weapon/trait/upgrade/shop/map/mutator/minigame tables)
   ↓
entities, art            (projectile, pickup, fx, enemies, drone, meteor, player, tank art)
   ↓
ui                       (text, widgets, screens/, hud panels)
   ↓
game                     (the Game class, assembled from mixins)
   ↓
main.py                  (bootstrap + compatibility re-exports)
```

| Module | Holds |
| --- | --- |
| `config.py` | Every tunable constant + the colour palette. Pure data, imports nothing local. |
| `util.py` | `clamp`, `lerp`, `smoothstep`, geometry helpers, `safe_int`, `fmt_amount`. |
| `viewport.py` | Picks the logical viewport so fullscreen fills the monitor with no black bars. |
| `audio.py` | Procedural tone generator + optional `.wav` loading. |
| `save.py` | `SaveManager` — the JSON save (settings, unlocks, mastery, challenges, leaderboard). |
| `data/` | All dataclass tables: weapons, traits, upgrades, shop, maps, mutators, minigames, mastery. |
| `entities/` | `Projectile`, `Pickup`, `Particle`/`FloatingText`, the enemy family + `Boss`, `Drone`, `Meteor`, `Player`. |
| `art/` | `draw_tank` (hull, treads, per-weapon barrel). |
| `ui/` | `text.py`, `widgets.py`, and `screens/` (one module per menu screen). |
| `game/` | The `Game` class mixins: `app`, `display`, `meta`, `world`, `combat`, `progression`, `minigames`, `run`, `render`, plus the base-game `anticheat`. |

`game/__init__.py` assembles the class:

```python
class Game(AppMixin, DisplayMixin, MetaMixin, WorldMixin, CombatMixin, ProgressionMixin,
           MinigameMixin, RunMixin, RenderMixin, MenuScreenMixin, InfoScreenMixin,
           WeaponsScreenMixin, ShopScreenMixin, MinigameScreenMixin, LevelUpScreenMixin,
           PausedScreenMixin, GameOverScreenMixin):
    ...
```

Each mixin file holds a slice of the old `Game` methods verbatim — relocation only, no behaviour
change.

## Adding things

- **A new tank** → add a `WeaponDef` to `data/weapons.py`, its trait to `data/traits.py`, its
  exclusive cards to `data/upgrades.py`, and a shop unlock in `data/shop.py`.
- **A new enemy** → add the class to `entities/enemies.py` and a spawn branch in
  `game/progression.py`.
- **A new menu screen** → add a `draw_*` mixin under `ui/screens/` and list it in
  `game/__init__.py`.

## Running

```
python main.py
```

The save file is `save.json` next to `main.py`.

## Injecting the cheat menu (optional)

The cheat menu is not part of the game. Start the game first, then inject it into the running
process from a second terminal:

```
python main.py    # terminal 1
python inject.py  # terminal 2
```

`inject.py` finds the game process, calls `install()` inside it, and paints the menu onto the
existing frame (RightShift / F1 toggles it). Because nothing is written to the source, restarting
`main.py` always gives you the legit game again until you inject. Requires `psutil` and `pywin32`.

The base game ships with a small, cheat-agnostic anti-cheat (`game/anticheat.py`). It inspects live
game state against the engine's own rules — rule-method integrity, stat baselines, bounds, speed,
dash/fire, damage accounting, vitals, world and progression provenance — and reverts anything the
engine could not have produced, no matter how the cheat is delivered. It only prevents; it never
kills the player.
