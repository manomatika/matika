"""
Rule-22 regression: every marker in matika_screens.json must resolve to a real
CSS selector present in that screen's rendering template(s).

This test would have caught all 17 stale markers that blocked the A5 tier-b
gate — markers that declared selectors like `.roles-table` and `#login-form`
when the templates have `id="roles-table"` and no login-form id at all.

Resolution strategy per selector type:
  .class-name  → class name token must appear in the template source text
  #id-name     → id="id-name" must appear in the template source text
  tag[attr='v']→ value 'v' must appear in template source OR route handler
                 source (export/import screens pass action_url dynamically)

Dynamic action_url residue: export/import macros use action="{{ action_url }}";
the URL literal lives in the route handler. Those screens provide .settings-
container as a statically-verifiable alternative marker.
"""
from __future__ import annotations

import json
import os
import re

import pytest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKTREE_ROOT = os.path.dirname(_TESTS_DIR)

SCREENS_FILE = os.path.join(
    _WORKTREE_ROOT, "src", "matika", "screens", "matika_screens.json"
)
TEMPLATES_DIR = os.path.join(_WORKTREE_ROOT, "src", "matika", "templates")
ROUTERS_DIR = os.path.join(_WORKTREE_ROOT, "src", "matika", "routers")

# Maps every core screen_id to the template file(s) whose rendered output
# contains that screen's HTML. Includes macros.html where it contributes.
SCREEN_TEMPLATE_MAP: dict[str, list[str]] = {
    "home": ["index.html"],
    "about": ["about.html"],
    "login": ["login.html"],
    "register": ["register.html"],
    "forgot_password": ["forgot_password.html"],
    "change_password": ["change_password.html"],
    "admin_roles": ["admin_roles.html"],
    "admin_permissions": ["admin_permissions.html"],
    "admin_users": ["admin_users.html"],
    "admin_data_export": ["export_data.html", "macros.html"],
    "admin_data_import": ["import_data.html", "macros.html"],
    "user_settings": ["user_settings.html"],
    "user_change_username": ["user_change_username.html"],
    "user_change_password": ["user_change_password.html"],
    "settings_export": ["export_data.html", "macros.html"],
    "settings_import": ["import_data.html", "macros.html"],
    "system_settings": ["system_settings.html"],
}

# Router source files searched for dynamic attribute values (e.g. action_url).
ROUTER_FILES = ["admin.py", "settings.py"]


def _load_source(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _router_text() -> str:
    parts = []
    for fname in ROUTER_FILES:
        p = os.path.join(ROUTERS_DIR, fname)
        if os.path.exists(p):
            parts.append(_load_source(p))
    return "\n".join(parts)


def _selector_resolves(selector: str, template_text: str, router_text: str) -> bool:
    """Return True if the CSS selector has a real referent in the source."""
    if selector.startswith("#"):
        id_name = selector[1:]
        return (
            f'id="{id_name}"' in template_text
            or f"id='{id_name}'" in template_text
        )
    if selector.startswith("."):
        class_name = selector[1:]
        return class_name in template_text
    if "[" in selector:
        m = re.search(r"\[.*?=\s*['\"]([^'\"]+)['\"]", selector)
        if not m:
            return False
        value = m.group(1)
        return value in template_text or value in router_text
    return selector in template_text


def _build_cases() -> list[tuple[str, str, str, str]]:
    """Return (screen_id, marker, template_text, router_text) for every marker."""
    with open(SCREENS_FILE, encoding="utf-8") as f:
        data = json.load(f)

    rt = _router_text()
    cases = []
    for entry in data["screens"]:
        if entry.get("type") != "screen":
            continue
        sid = entry["screen_id"]
        if sid not in SCREEN_TEMPLATE_MAP:
            continue
        tmpl_text = "".join(
            _load_source(os.path.join(TEMPLATES_DIR, t))
            for t in SCREEN_TEMPLATE_MAP[sid]
        )
        for marker in entry.get("markers", []):
            cases.append((sid, marker, tmpl_text, rt))
    return cases


_CASES = _build_cases()
_IDS = [f"{sid}::{marker}" for sid, marker, _, _ in _CASES]


@pytest.mark.parametrize("screen_id,marker,template_text,router_text", _CASES, ids=_IDS)
def test_screen_marker_resolves_in_template(
    screen_id, marker, template_text, router_text
):
    """Each declared marker must correspond to a real selector in the template."""
    assert _selector_resolves(marker, template_text, router_text), (
        f"screen '{screen_id}': marker {marker!r} has no real referent in "
        f"{SCREEN_TEMPLATE_MAP[screen_id]} (or route handler source for "
        f"attribute selectors). Fix the marker or the template."
    )


def test_all_screen_ids_have_template_mapping():
    """Every screen-type entry in the manifest must have a template mapping."""
    with open(SCREENS_FILE, encoding="utf-8") as f:
        data = json.load(f)

    missing = [
        e["screen_id"]
        for e in data["screens"]
        if e.get("type") == "screen" and e["screen_id"] not in SCREEN_TEMPLATE_MAP
    ]
    assert not missing, (
        f"The following screen_ids have no entry in SCREEN_TEMPLATE_MAP: {missing}. "
        f"Add the mapping so marker resolution can be verified."
    )
