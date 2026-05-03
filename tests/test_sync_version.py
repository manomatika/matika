"""
Tests for scripts/sync_version.py.

Runs entirely against fixture trees under tmp_path — never touches the real
working tree. REPO_ROOT is patched at the module level so all path lookups
inside sync_version resolve to the fixture.
"""

import json
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import sync_version  # noqa: E402 — must come after sys.path manipulation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_tree(tmp_path: Path, version_raw: str) -> Path:
    """Create a minimal repo fixture: VERSION, pyproject.toml, package.json."""
    (tmp_path / "VERSION").write_text(version_raw + "\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "matika"\nversion = "OLD"\ndescription = "test"\n'
    )
    (tmp_path / "package.json").write_text(
        '{\n  "name": "matika",\n  "version": "OLD"\n}\n'
    )
    return tmp_path


def run_sync(root: Path) -> list[str]:
    with patch.object(sync_version, "REPO_ROOT", root):
        return sync_version.sync()


def run_drift_check(root: Path, expected: str) -> None:
    with patch.object(sync_version, "REPO_ROOT", root):
        sync_version.drift_check(expected)


def pyproject_version(root: Path) -> str:
    m = re.search(
        r'^version\s*=\s*"([^"]*)"',
        (root / "pyproject.toml").read_text(),
        re.MULTILINE,
    )
    return m.group(1) if m else ""


def package_json_version(root: Path) -> str:
    m = re.search(
        r'^(\s*"version"\s*:\s*)"([^"]*)"',
        (root / "package.json").read_text(),
        re.MULTILINE,
    )
    return m.group(2) if m else ""


# ---------------------------------------------------------------------------
# Core propagation
# ---------------------------------------------------------------------------

def test_dev_version_is_stripped_before_propagation(tmp_path):
    make_tree(tmp_path, "0.0.4_dev")
    run_sync(tmp_path)
    assert pyproject_version(tmp_path) == "0.0.4"
    assert package_json_version(tmp_path) == "0.0.4"


def test_clean_version_propagates_unchanged(tmp_path):
    make_tree(tmp_path, "0.0.4")
    run_sync(tmp_path)
    assert pyproject_version(tmp_path) == "0.0.4"
    assert package_json_version(tmp_path) == "0.0.4"


def test_dev_suffix_never_written_to_targets(tmp_path):
    make_tree(tmp_path, "1.2.3_dev")
    run_sync(tmp_path)
    for filename in ("pyproject.toml", "package.json"):
        assert "_dev" not in (tmp_path / filename).read_text(), (
            f"_dev suffix found in {filename}"
        )


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_sync_is_idempotent(tmp_path):
    make_tree(tmp_path, "0.0.4_dev")
    run_sync(tmp_path)
    before_py = (tmp_path / "pyproject.toml").read_text()
    before_pkg = (tmp_path / "package.json").read_text()

    run_sync(tmp_path)
    assert (tmp_path / "pyproject.toml").read_text() == before_py
    assert (tmp_path / "package.json").read_text() == before_pkg


def test_sync_returns_empty_list_when_already_current(tmp_path):
    make_tree(tmp_path, "0.0.4_dev")
    run_sync(tmp_path)
    written = run_sync(tmp_path)
    assert written == [], f"Expected no files written on second run, got: {written}"


# ---------------------------------------------------------------------------
# Missing files are skipped gracefully
# ---------------------------------------------------------------------------

def test_sync_skips_missing_package_json(tmp_path):
    make_tree(tmp_path, "0.0.4_dev")
    (tmp_path / "package.json").unlink()
    run_sync(tmp_path)
    assert pyproject_version(tmp_path) == "0.0.4"


def test_sync_skips_missing_pyproject(tmp_path):
    make_tree(tmp_path, "0.0.4_dev")
    (tmp_path / "pyproject.toml").unlink()
    run_sync(tmp_path)
    assert package_json_version(tmp_path) == "0.0.4"


# ---------------------------------------------------------------------------
# Drift check
# ---------------------------------------------------------------------------

def test_drift_check_passes_when_all_targets_match(tmp_path):
    make_tree(tmp_path, "0.0.4_dev")
    run_sync(tmp_path)
    (tmp_path / "VERSION").write_text("0.0.4\n")
    run_drift_check(tmp_path, "0.0.4")  # must not raise or exit


def test_drift_check_fails_when_version_has_dev(tmp_path):
    make_tree(tmp_path, "0.0.4_dev")
    run_sync(tmp_path)
    with pytest.raises(SystemExit):
        run_drift_check(tmp_path, "0.0.4")  # VERSION still has _dev


def test_drift_check_fails_on_pyproject_mismatch(tmp_path):
    make_tree(tmp_path, "0.0.4_dev")
    run_sync(tmp_path)
    (tmp_path / "VERSION").write_text("0.0.4\n")
    # Manually corrupt pyproject
    content = (tmp_path / "pyproject.toml").read_text()
    (tmp_path / "pyproject.toml").write_text(content.replace('"0.0.4"', '"0.0.3"'))
    with pytest.raises(SystemExit):
        run_drift_check(tmp_path, "0.0.4")


def test_drift_check_fails_on_package_json_mismatch(tmp_path):
    make_tree(tmp_path, "0.0.4_dev")
    run_sync(tmp_path)
    (tmp_path / "VERSION").write_text("0.0.4\n")
    content = (tmp_path / "package.json").read_text()
    (tmp_path / "package.json").write_text(content.replace('"0.0.4"', '"9.9.9"'))
    with pytest.raises(SystemExit):
        run_drift_check(tmp_path, "0.0.4")


# ---------------------------------------------------------------------------
# --check mode
# ---------------------------------------------------------------------------

def run_check(root: Path) -> list[str]:
    with patch.object(sync_version, "REPO_ROOT", root):
        return sync_version.sync(check_only=True)


def test_check_mode_returns_empty_when_clean(tmp_path):
    make_tree(tmp_path, "0.0.4_dev")
    run_sync(tmp_path)
    drifted = run_check(tmp_path)
    assert drifted == [], f"Expected no drift, got: {drifted}"


def test_check_mode_reports_pyproject_drift(tmp_path):
    make_tree(tmp_path, "0.0.4_dev")
    run_sync(tmp_path)
    content = (tmp_path / "pyproject.toml").read_text()
    (tmp_path / "pyproject.toml").write_text(content.replace('"0.0.4"', '"0.0.1"'))
    drifted = run_check(tmp_path)
    assert "pyproject.toml" in drifted[0]


def test_check_mode_reports_package_json_drift(tmp_path):
    make_tree(tmp_path, "0.0.4_dev")
    run_sync(tmp_path)
    content = (tmp_path / "package.json").read_text()
    (tmp_path / "package.json").write_text(content.replace('"0.0.4"', '"9.9.9"'))
    drifted = run_check(tmp_path)
    assert "package.json" in drifted[0]


def test_check_mode_does_not_modify_files(tmp_path):
    make_tree(tmp_path, "0.0.4_dev")
    # Leave files at OLD — check mode must not fix them
    before_py = (tmp_path / "pyproject.toml").read_text()
    before_pkg = (tmp_path / "package.json").read_text()
    run_check(tmp_path)
    assert (tmp_path / "pyproject.toml").read_text() == before_py
    assert (tmp_path / "package.json").read_text() == before_pkg


def test_check_mode_accepts_dev_version(tmp_path):
    """--check must not fail just because VERSION carries _dev."""
    make_tree(tmp_path, "0.0.4_dev")
    run_sync(tmp_path)
    # VERSION still has _dev — check mode should be fine with that
    drifted = run_check(tmp_path)
    assert drifted == []


def test_release_drift_gate_uses_check_mode(tmp_path):
    """release.py calls sync(check_only=True) as its drift gate.
    Verify the gate returns no drift immediately after propagation."""
    make_tree(tmp_path, "0.0.4_dev")
    with patch.object(sync_version, "REPO_ROOT", tmp_path):
        sync_version.sync()                            # propagation (as release does)
        drifted = sync_version.sync(check_only=True)   # drift gate (as release does)
    assert drifted == [], f"Drift gate should pass after clean propagation, got: {drifted}"
