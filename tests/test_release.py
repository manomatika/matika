"""
Tests for scripts/release.py — the release-commit preparation entry point.

These exercise argument parsing and the VERSION pre-flight gate in isolation:
the version regex (accepts -dev / -rc.N), version_core stripping, and the
"VERSION must be a pre-release of the target core" guard. Git/commit side
effects are not exercised here.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import release  # noqa: E402 — after sys.path manipulation


# ---------------------------------------------------------------------------
# Version regex accepts the pre-release ladder
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value",
    ["0.0.4", "0.0.4-dev", "0.0.4-rc.1", "10.20.30-rc.99", "1.2.3-dev.0"],
)
def test_version_regex_accepts_ladder(value):
    assert release.VERSION_RE.match(value), f"{value!r} should be accepted"


@pytest.mark.parametrize("value", ["0.0", "v0.0.4", "0.0.4_dev", "abc", "0.0.4-"])
def test_version_regex_rejects_invalid(value):
    # Note: a leading "v" is stripped by main() before matching, so the regex
    # itself must reject a literal "v0.0.4". "_dev" (underscore) must be rejected.
    assert not release.VERSION_RE.match(value), f"{value!r} should be rejected"


# ---------------------------------------------------------------------------
# version_core is the shared strip-to-core helper (imported from sync_version)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,core",
    [("0.0.4-dev", "0.0.4"), ("0.0.4-rc.1", "0.0.4"), ("0.0.4", "0.0.4")],
)
def test_version_core(raw, core):
    assert release.version_core(raw) == core
