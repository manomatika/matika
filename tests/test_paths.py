"""
Tests for the canonical strict SemVer parser in src/matika/core/paths.py.

paths.py owns the single canonical version authority for the product:
_parse_semver / version_core / is_prerelease. These tests assert BOTH the valid
and invalid directions, that error messages NAME the offending value, and that
get_matika_version() raises a specific PATH-BEARING error (RULE B) instead of
the old "unknown" sentinel.

The parser is mirrored verbatim in scripts/sync_version.py and matika.spec;
parity with the sync_version mirror is asserted here too.
"""

import os
import sys
from pathlib import Path

import pytest

from matika.core import paths
from matika.core.paths import version_core, is_prerelease, get_matika_version

# The sync_version mirror (build/release tooling copy).
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import sync_version  # noqa: E402


# ---------------------------------------------------------------------------
# version_core — valid inputs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,core",
    [
        ("0.0.4", "0.0.4"),
        ("0.0.4-dev", "0.0.4"),
        ("0.0.4-rc.1", "0.0.4"),
        ("v0.0.4-rc.1", "0.0.4"),
        ("0.0.4+build.5", "0.0.4"),
        ("0.0.4-rc.1+build.5", "0.0.4"),
        ("1.2.3-alpha-1", "1.2.3"),  # hyphen INSIDE the pre-release identifier
        ("10.20.30", "10.20.30"),
    ],
)
def test_version_core_valid(raw, core):
    assert version_core(raw) == core


# ---------------------------------------------------------------------------
# version_core — invalid inputs RAISE, and the message NAMES the bad value
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw",
    ["", "unknown", "1.2", "1.2.3.4", "01.2.3", "1.2.x", "abc", "1.2.3-"],
)
def test_version_core_raises_on_invalid(raw):
    with pytest.raises(ValueError) as exc:
        version_core(raw)
    # The error must specifically name the offending value.
    assert repr(raw) in str(exc.value)


# ---------------------------------------------------------------------------
# is_prerelease — build metadata alone is NOT pre-release
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw",
    ["0.0.4-dev", "0.0.4-rc.1", "0.0.4-rc.2+build.5", "1.2.3-alpha-1"],
)
def test_is_prerelease_true(raw):
    assert is_prerelease(raw) is True


@pytest.mark.parametrize(
    "raw",
    ["0.0.4", "0.0.4+build", "v1.2.3+build.5", "10.20.30"],
)
def test_is_prerelease_false(raw):
    assert is_prerelease(raw) is False


@pytest.mark.parametrize("raw", ["", "unknown", "1.2", "01.2.3", "1.2.3-"])
def test_is_prerelease_raises_on_invalid(raw):
    with pytest.raises(ValueError) as exc:
        is_prerelease(raw)
    assert repr(raw) in str(exc.value)


# ---------------------------------------------------------------------------
# Leading-zero pre-release identifiers
# ---------------------------------------------------------------------------

def test_numeric_prerelease_leading_zero_rejected():
    with pytest.raises(ValueError):
        version_core("1.2.3-01")


def test_numeric_prerelease_zero_allowed():
    assert version_core("1.2.3-0") == "1.2.3"
    assert is_prerelease("1.2.3-0") is True


# ---------------------------------------------------------------------------
# get_matika_version — RULE B: no "unknown" sentinel; path-bearing error
# ---------------------------------------------------------------------------

def test_get_matika_version_reads_version_file(tmp_path, monkeypatch):
    vfile = tmp_path / "VERSION"
    vfile.write_text("0.0.4-dev\n")
    monkeypatch.setattr(paths, "BASE_DIR", str(tmp_path))
    assert get_matika_version() == "0.0.4-dev"


def test_get_matika_version_raises_path_bearing_error_when_missing(tmp_path, monkeypatch):
    # Point BASE_DIR at a dir with NO VERSION file.
    missing_base = tmp_path / "no_version_here"
    missing_base.mkdir()
    monkeypatch.setattr(paths, "BASE_DIR", str(missing_base))

    with pytest.raises(RuntimeError) as exc:
        get_matika_version()

    msg = str(exc.value)
    # RULE B: NOT the old sentinel, and NOT a bare SemVer error.
    assert "unknown" not in msg
    assert "invalid version" not in msg
    # Must name the absolute path of the missing VERSION file.
    expected_path = os.path.abspath(os.path.join(str(missing_base), "VERSION"))
    assert expected_path in msg


def test_get_matika_version_raises_when_unreadable(tmp_path, monkeypatch):
    # A VERSION path that is a directory -> open() raises OSError (IsADirectory).
    base = tmp_path / "weird"
    base.mkdir()
    (base / "VERSION").mkdir()
    monkeypatch.setattr(paths, "BASE_DIR", str(base))
    with pytest.raises(RuntimeError) as exc:
        get_matika_version()
    assert "unknown" not in str(exc.value)
    assert os.path.abspath(os.path.join(str(base), "VERSION")) in str(exc.value)


# ---------------------------------------------------------------------------
# Mirror parity: paths.version_core / is_prerelease match sync_version's copy
# ---------------------------------------------------------------------------

_PARITY_CASES = [
    "0.0.4", "0.0.4-dev", "0.0.4-rc.1", "v0.0.4-rc.1", "0.0.4+build.5",
    "0.0.4-rc.1+build.5", "1.2.3-alpha-1", "1.2.3-0", "10.20.30",
    "", "unknown", "1.2", "1.2.3.4", "01.2.3", "1.2.x", "abc", "1.2.3-",
    "1.2.3-01",
]


@pytest.mark.parametrize("raw", _PARITY_CASES)
def test_version_core_mirror_parity(raw):
    def _result(fn):
        try:
            return ("ok", fn(raw))
        except ValueError:
            return ("raise", None)

    assert _result(version_core) == _result(sync_version.version_core)


@pytest.mark.parametrize("raw", _PARITY_CASES)
def test_is_prerelease_mirror_parity(raw):
    def _result(fn):
        try:
            return ("ok", fn(raw))
        except ValueError:
            return ("raise", None)

    assert _result(is_prerelease) == _result(sync_version.is_prerelease)
