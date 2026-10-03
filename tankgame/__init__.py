"""Tank Game Rebirth — a top-down survival shooter built on pygame.

The game was originally a single ``main.py``. It now lives in this package, split by
responsibility, with ``main.py`` kept as a thin bootstrap that also re-exports the public
names so existing tooling (and the smoke-test harness) can keep importing ``main``.
"""

__version__ = "5.0.0"
