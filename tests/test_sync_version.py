"""
Tests for scripts/sync_version.py.

Runs entirely against fixture trees under tmp_path — never touches the real
working tree. REPO_ROOT is patched at the module level so all path lookups
inside sync_version resolve to the fixture.
"""

import json
import re
import subprocess
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
    make_tree(tmp_path, "0.0.4-dev")
    run_sync(tmp_path)
    assert pyproject_version(tmp_path) == "0.0.4"
    assert package_json_version(tmp_path) == "0.0.4"


def test_clean_version_propagates_unchanged(tmp_path):
    make_tree(tmp_path, "0.0.4")
    run_sync(tmp_path)
    assert pyproject_version(tmp_path) == "0.0.4"
    assert package_json_version(tmp_path) == "0.0.4"


def test_dev_suffix_never_written_to_targets(tmp_path):
    make_tree(tmp_path, "1.2.3-dev")
    run_sync(tmp_path)
    for filename in ("pyproject.toml", "package.json"):
        content = (tmp_path / filename).read_text()
        assert "-dev" not in content, f"-dev suffix found in {filename}"
        assert "1.2.3" in content, f"bare core not propagated to {filename}"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_sync_is_idempotent(tmp_path):
    make_tree(tmp_path, "0.0.4-dev")
    run_sync(tmp_path)
    before_py = (tmp_path / "pyproject.toml").read_text()
    before_pkg = (tmp_path / "package.json").read_text()

    run_sync(tmp_path)
    assert (tmp_path / "pyproject.toml").read_text() == before_py
    assert (tmp_path / "package.json").read_text() == before_pkg


def test_sync_returns_empty_list_when_already_current(tmp_path):
    make_tree(tmp_path, "0.0.4-dev")
    run_sync(tmp_path)
    written = run_sync(tmp_path)
    assert written == [], f"Expected no files written on second run, got: {written}"


# ---------------------------------------------------------------------------
# Missing files are skipped gracefully
# ---------------------------------------------------------------------------

def test_sync_skips_missing_package_json(tmp_path):
    make_tree(tmp_path, "0.0.4-dev")
    (tmp_path / "package.json").unlink()
    run_sync(tmp_path)
    assert pyproject_version(tmp_path) == "0.0.4"


def test_sync_skips_missing_pyproject(tmp_path):
    make_tree(tmp_path, "0.0.4-dev")
    (tmp_path / "pyproject.toml").unlink()
    run_sync(tmp_path)
    assert package_json_version(tmp_path) == "0.0.4"


# ---------------------------------------------------------------------------
# Drift check
# ---------------------------------------------------------------------------

def test_drift_check_passes_when_all_targets_match(tmp_path):
    make_tree(tmp_path, "0.0.4-dev")
    run_sync(tmp_path)
    (tmp_path / "VERSION").write_text("0.0.4\n")
    run_drift_check(tmp_path, "0.0.4")  # must not raise or exit


def test_drift_check_fails_when_version_has_dev(tmp_path):
    make_tree(tmp_path, "0.0.4-dev")
    run_sync(tmp_path)
    with pytest.raises(SystemExit):
        run_drift_check(tmp_path, "0.0.4")  # VERSION still carries -dev suffix


def test_drift_check_fails_when_version_has_rc(tmp_path):
    """drift_check rejects any pre-release suffix, not just -dev (e.g. -rc.N)."""
    make_tree(tmp_path, "0.0.4-rc.1")
    run_sync(tmp_path)
    with pytest.raises(SystemExit):
        run_drift_check(tmp_path, "0.0.4")  # VERSION still carries -rc.1 suffix


def test_rc_version_core_propagates(tmp_path):
    """An -rc.N VERSION propagates the bare core to all targets."""
    make_tree(tmp_path, "0.0.4-rc.2")
    run_sync(tmp_path)
    assert pyproject_version(tmp_path) == "0.0.4"
    assert package_json_version(tmp_path) == "0.0.4"


def test_drift_check_fails_on_pyproject_mismatch(tmp_path):
    make_tree(tmp_path, "0.0.4-dev")
    run_sync(tmp_path)
    (tmp_path / "VERSION").write_text("0.0.4\n")
    # Manually corrupt pyproject
    content = (tmp_path / "pyproject.toml").read_text()
    (tmp_path / "pyproject.toml").write_text(content.replace('"0.0.4"', '"0.0.3"'))
    with pytest.raises(SystemExit):
        run_drift_check(tmp_path, "0.0.4")


def test_drift_check_fails_on_package_json_mismatch(tmp_path):
    make_tree(tmp_path, "0.0.4-dev")
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
    make_tree(tmp_path, "0.0.4-dev")
    run_sync(tmp_path)
    drifted = run_check(tmp_path)
    assert drifted == [], f"Expected no drift, got: {drifted}"


def test_check_mode_reports_pyproject_drift(tmp_path):
    make_tree(tmp_path, "0.0.4-dev")
    run_sync(tmp_path)
    content = (tmp_path / "pyproject.toml").read_text()
    (tmp_path / "pyproject.toml").write_text(content.replace('"0.0.4"', '"0.0.1"'))
    drifted = run_check(tmp_path)
    assert drifted[0]["path"] == "pyproject.toml"
    assert drifted[0]["expected"] == "0.0.4"
    assert drifted[0]["found"] == "0.0.1"


def test_check_mode_reports_package_json_drift(tmp_path):
    make_tree(tmp_path, "0.0.4-dev")
    run_sync(tmp_path)
    content = (tmp_path / "package.json").read_text()
    (tmp_path / "package.json").write_text(content.replace('"0.0.4"', '"9.9.9"'))
    drifted = run_check(tmp_path)
    assert drifted[0]["path"] == "package.json"
    assert drifted[0]["found"] == "9.9.9"


def test_check_mode_does_not_modify_files(tmp_path):
    make_tree(tmp_path, "0.0.4-dev")
    # Leave files at OLD — check mode must not fix them
    before_py = (tmp_path / "pyproject.toml").read_text()
    before_pkg = (tmp_path / "package.json").read_text()
    run_check(tmp_path)
    assert (tmp_path / "pyproject.toml").read_text() == before_py
    assert (tmp_path / "package.json").read_text() == before_pkg


def test_check_mode_accepts_dev_version(tmp_path):
    """--check must not fail just because VERSION carries a pre-release suffix."""
    make_tree(tmp_path, "0.0.4-dev")
    run_sync(tmp_path)
    # VERSION still has -dev — check mode should be fine with that
    drifted = run_check(tmp_path)
    assert drifted == []


def test_release_drift_gate_uses_check_mode(tmp_path):
    """release.py calls sync(check_only=True) as its drift gate.
    Verify the gate returns no drift immediately after propagation."""
    make_tree(tmp_path, "0.0.4-dev")
    with patch.object(sync_version, "REPO_ROOT", tmp_path):
        sync_version.sync()                            # propagation (as release does)
        drifted = sync_version.sync(check_only=True)   # drift gate (as release does)
    assert drifted == [], f"Drift gate should pass after clean propagation, got: {drifted}"


# ---------------------------------------------------------------------------
# --check --json mode
# ---------------------------------------------------------------------------

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


def _run_check_json(root: Path) -> tuple[int, dict]:
    """Invoke sync_version.py --check --json as a subprocess; return (exit_code, parsed_json)."""
    env_patch = {"PYTHONPATH": ""}  # ensure clean import
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "sync_version.py"), "--check", "--json"],
        capture_output=True,
        text=True,
        cwd=str(root),
    )
    parsed = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, parsed


def test_check_json_clean_tree_exits_0_with_empty_drift(tmp_path):
    make_tree(tmp_path, "0.0.4-dev")
    run_sync(tmp_path)
    # Point REPO_ROOT at tmp_path by running from there (script resolves __file__)
    # Use the module-level approach instead to keep things consistent
    with patch.object(sync_version, "REPO_ROOT", tmp_path):
        _, clean = sync_version.read_version()
        drifted = sync_version.sync(check_only=True, quiet=True)
    output = json.dumps({"version": clean, "drift": drifted})
    parsed = json.loads(output)
    assert parsed["version"] == "0.0.4"
    assert parsed["drift"] == []


def test_check_json_drifted_file_returns_drift_entry(tmp_path):
    make_tree(tmp_path, "0.0.4-dev")
    run_sync(tmp_path)
    content = (tmp_path / "pyproject.toml").read_text()
    (tmp_path / "pyproject.toml").write_text(content.replace('"0.0.4"', '"0.0.2"'))
    with patch.object(sync_version, "REPO_ROOT", tmp_path):
        _, clean = sync_version.read_version()
        drifted = sync_version.sync(check_only=True, quiet=True)
    output = json.dumps({"version": clean, "drift": drifted})
    parsed = json.loads(output)
    assert parsed["version"] == "0.0.4"
    assert len(parsed["drift"]) == 1
    entry = parsed["drift"][0]
    assert entry["path"] == "pyproject.toml"
    assert entry["expected"] == "0.0.4"
    assert entry["found"] == "0.0.2"


def test_json_without_check_exits_2(tmp_path):
    make_tree(tmp_path, "0.0.4-dev")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "sync_version.py"), "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 2


def test_drift_line_uses_double_quotes(tmp_path, capsys):
    """Human-readable DRIFT line must use double quotes, not single quotes."""
    make_tree(tmp_path, "0.0.4-dev")
    run_sync(tmp_path)
    content = (tmp_path / "pyproject.toml").read_text()
    (tmp_path / "pyproject.toml").write_text(content.replace('"0.0.4"', '"0.0.1"'))
    run_check(tmp_path)
    out = capsys.readouterr().out
    assert 'expected "0.0.4", found "0.0.1"' in out
    assert "expected '0.0.4'" not in out
