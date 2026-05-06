#!/usr/bin/env python3
"""
dev_setup.py — wire local AppLug repositories into plugins/ for development.

Reads plugins.dev.json (sibling of this script's parent directory), resolves
each path, validates it, and creates a symlink inside plugins/ using the
plugin's directory name.  Idempotent: safe to run multiple times.

Usage
-----
    python scripts/dev_setup.py

First-time setup
----------------
    cp plugins.dev.json.example plugins.dev.json
    # Edit plugins.dev.json to point at your local plugin repos
    python scripts/dev_setup.py
"""

import json
import os
import shutil
import sys
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────

REPO_ROOT   = Path(__file__).resolve().parent.parent
PLUGINS_DIR = REPO_ROOT / "plugins"
CONFIG_FILE = REPO_ROOT / "plugins.dev.json"
EXAMPLE_FILE = REPO_ROOT / "plugins.dev.json.example"

# ── Helpers ─────────────────────────────────────────────────────────────────

def _ok(msg: str)   -> None: print(f"  ✓  {msg}")
def _warn(msg: str) -> None: print(f"  ⚠  {msg}")
def _err(msg: str)  -> None: print(f"  ✗  {msg}")
def _info(msg: str) -> None: print(f"     {msg}")


def _has_menu_json(directory: Path) -> bool:
    # Plugins use the consolidated *_menus.json format (plural).
    # Core menus use individual *_menu.json files (singular) — not matched here.
    return any(directory.glob("*_menus.json"))


def _resolve_path(raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p.resolve()
    return (REPO_ROOT / p).resolve()


# ── Core logic ───────────────────────────────────────────────────────────────

def process_plugin(raw_path: str) -> str:
    """
    Validate a plugin path and create (or verify) its symlink in plugins/.

    Returns one of: "linked", "already_ok", "skipped", "fixed".
    """
    plugin_path = _resolve_path(raw_path)
    plugin_name = plugin_path.name
    link_target = PLUGINS_DIR / plugin_name

    # ── Existence checks ───────────────────────────────────────────────────

    if not plugin_path.exists():
        _warn(f"{raw_path!r} — path does not exist, skipping.")
        return "skipped"

    if not plugin_path.is_dir():
        _warn(f"{raw_path!r} — not a directory, skipping.")
        return "skipped"

    if not (plugin_path / "applug.json").exists():
        _warn(f"{plugin_name} — missing applug.json, skipping.")
        return "skipped"

    if not _has_menu_json(plugin_path):
        _warn(f"{plugin_name} — no *_menu.json found, skipping.")
        return "skipped"

    # ── Symlink state ──────────────────────────────────────────────────────

    if link_target.exists() or link_target.is_symlink():
        if link_target.is_symlink():
            current_target = link_target.resolve()
            if current_target == plugin_path:
                _ok(f"{plugin_name} → already correctly linked.")
                return "already_ok"
            else:
                # Points somewhere else — broken or wrong target
                _warn(
                    f"{plugin_name} → symlink points to {current_target}, "
                    f"expected {plugin_path}."
                )
                answer = input(f"     Replace it? [y/N] ").strip().lower()
                if answer == "y":
                    link_target.unlink()
                    link_target.symlink_to(plugin_path)
                    _ok(f"{plugin_name} → fixed → {plugin_path}")
                    return "fixed"
                else:
                    _info(f"{plugin_name} — left unchanged.")
                    return "skipped"
        else:
            # A real file or directory already exists at that name
            _warn(
                f"{plugin_name} — a non-symlink entry already exists at "
                f"{link_target}. Skipping to avoid data loss."
            )
            return "skipped"

    # ── Create the symlink ─────────────────────────────────────────────────

    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    link_target.symlink_to(plugin_path)
    _ok(f"{plugin_name} → linked → {plugin_path}")
    return "linked"


def main() -> int:
    print("Matika dev_setup.py — plugin wiring")
    print("=" * 42)

    # ── Ensure plugins.dev.json exists ────────────────────────────────────

    if not CONFIG_FILE.exists():
        if EXAMPLE_FILE.exists():
            shutil.copy(EXAMPLE_FILE, CONFIG_FILE)
            print()
            print("plugins.dev.json not found — created from example.")
            print(f"Edit {CONFIG_FILE} to point at your local plugin repos, then re-run.")
            print()
            _info(f"  open {CONFIG_FILE}")
            print()
        else:
            _err("plugins.dev.json not found and no example to copy from.")
            print("Create plugins.dev.json manually — see plugins.dev.json.example.")
        return 1

    # ── Load config ───────────────────────────────────────────────────────

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            # Strip JS-style // comments before parsing
            lines = [l for l in f if not l.lstrip().startswith("//")]
            config = json.loads("".join(lines))
    except json.JSONDecodeError as exc:
        _err(f"plugins.dev.json is not valid JSON: {exc}")
        return 1

    plugins_list = config.get("plugins", [])

    if not plugins_list:
        print()
        print("plugins.dev.json has an empty 'plugins' array — nothing to link.")
        print("Add path entries to plugins.dev.json, then re-run.")
        print()
        return 0

    # ── Process each entry ────────────────────────────────────────────────

    print()
    counts: dict[str, int] = {"linked": 0, "already_ok": 0, "skipped": 0, "fixed": 0}

    for raw in plugins_list:
        result = process_plugin(str(raw))
        counts[result] = counts.get(result, 0) + 1

    # ── Summary ───────────────────────────────────────────────────────────

    print()
    print("─" * 42)
    print("Summary")
    print(f"  Newly linked : {counts['linked']}")
    print(f"  Already OK   : {counts['already_ok']}")
    print(f"  Fixed        : {counts['fixed']}")
    print(f"  Skipped/warn : {counts['skipped']}")
    print()

    if counts["linked"] + counts["already_ok"] + counts["fixed"] == 0:
        print("No plugins were wired. Check the warnings above.")
        return 1

    print("Plugin setup complete. Start the server with:")
    print("  SECRET_KEY=<key> PYTHONPATH=src uvicorn matika.main:app "
          "--host 127.0.0.1 --port 8000 --reload")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
