"""Tank Game Rebirth - restore the legit, uninjected game.

The cheat is **no longer baked into the source**. To use it, start the legit game and
then inject the menu into that running process::

    python main.py        # terminal 1
    python inject.py      # terminal 2

This script exists only to undo the old v2/v3 ``patch.py`` if a copy of the game still
has the scaffold embedded in ``tankgame/game/app.py``. Run it once and the game is clean.

    python patch.py
"""
from __future__ import annotations

import py_compile
import re
import sys
import tempfile
from pathlib import Path

MARKER = "# --- tank inject v3 ---"
V2_MARKER = "# --- tank inject v2 ---"
LEGACY_MARKER = "# --- tank inject ---"

_RE_METHOD = re.compile(
    r"\n    def _inject_pre\(self[^\n]*\).*?"
    r"(?=\n    # ---------------- Camera ----------------)",
    re.DOTALL,
)
_RE_V2_METHOD = re.compile(
    r"\n    def _process_inject\(self[^\n]*\).*?"
    r"(?=\n    # ---------------- Camera ----------------)",
    re.DOTALL,
)
_RE_V2_APPLY = re.compile(
    r"\n    def _apply_inject_modules\(self[^\n]*\).*?"
    r"(?=\n    # ---------------- Camera ----------------)",
    re.DOTALL,
)
_RE_IMPORT = re.compile(
    r"\n\ntry:\n    import inject as _tank_inject[^\n]*\n(?:.*?\n)*?    _tank_inject = None\n",
    re.DOTALL,
)
_RE_FOCUS = re.compile(
    r"\n            if getattr\(self, \"_inject_menu_visible\", False\)[^\n]*\n                continue\n",
)
_RE_RUN = re.compile(r"            self\._inject_pre\([^\n]*\n")
_RE_FLIP = re.compile(r"            self\._inject_draw\([^\n]*\n")
_RE_RSHIFT = re.compile(
    r"\n\n                    if e\.key == pygame\.K_RSHIFT:.*?"
    r"(?=\n\n                elif self\.state == \"paused\":)",
    re.DOTALL,
)


def strip_inject(text: str) -> str:
    """Remove previously injected scaffolding (v2 or v3)."""
    text = _RE_V2_APPLY.sub("", text)
    text = _RE_V2_METHOD.sub("", text)
    text = _RE_METHOD.sub("", text)
    text = _RE_IMPORT.sub("", text)
    text = _RE_RSHIFT.sub("", text)
    text = _RE_RUN.sub("", text)
    text = _RE_FLIP.sub("", text)
    text = _RE_FOCUS.sub(
        "\n            # Losing focus mid-run used to keep the fight going in the background.\n"
        "            if e.type == pygame.WINDOWFOCUSLOST and self.state == \"playing\":\n"
        "                self.set_state(\"paused\")\n",
        text,
    )
    text = text.replace("import json\nimport math\nimport os\n", "import math\n")
    return text


def find_app() -> Path:
    roots = [Path.cwd(), Path(__file__).resolve().parent]
    for root in roots:
        for candidate in (
            root / "tankgame" / "game" / "app.py",
            root / "Tank Game Rebirth" / "tankgame" / "game" / "app.py",
            root.parent / "tankgame" / "game" / "app.py",
        ):
            if candidate.is_file():
                return candidate.resolve()
    for root in roots:
        for p in root.rglob("tankgame/game/app.py"):
            return p.resolve()
    raise FileNotFoundError(
        "Could not find tankgame/game/app.py. Put patch.py in the game root and retry."
    )


def verify(text: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as tmp:
        tmp.write(text)
        tmp_path = tmp.name
    try:
        py_compile.compile(tmp_path, doraise=True)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def is_patched(text: str) -> bool:
    return (
        MARKER in text or V2_MARKER in text or LEGACY_MARKER in text
        or "import inject as _tank_inject" in text or "def _inject_pre" in text
    )


def restore(path: Path) -> None:
    current = path.read_text(encoding="utf-8")
    if not is_patched(current):
        print(f"Already legit: {path}")
        print("The cheat is not in the source. Inject it at runtime with:  python inject.py")
        return
    clean = strip_inject(current)
    verify(clean)
    path.write_text(clean, encoding="utf-8")
    print(f"Restored {path}")
    print("The old file patch is gone. Start the game with:  python main.py")


if __name__ == "__main__":
    try:
        restore(find_app())
    except Exception as exc:  # noqa: BLE001
        print(f"patch restore failed: {exc}")
        sys.exit(1)
