"""
Regression tests for matika.spec's product-identity naming.

matika is a reusable framework; the user-facing PRODUCT that bundles it owns the
installed bundle/exe identity. The ahimsa build job passes the recipe's product
name + product version into the spec via env (MATIKA_PRODUCT_NAME /
MATIKA_PRODUCT_VERSION) so the frozen artifact is named after the PRODUCT
(e.g. ManoMatika-0.0.1.app), NOT after matika the component or matika's VERSION.

The spec can't be imported (PyInstaller injects globals like Analysis/EXE/SPEC),
so these tests exec the spec source in a stubbed namespace that captures the
name= kwargs handed to EXE / COLLECT / BUNDLE plus the Info.plist values. This
exercises the REAL naming logic — not a copy of it.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SPEC_PATH = Path(__file__).parent.parent / "matika.spec"


def _exec_spec(monkeypatch, *, product_name=None, product_version=None, ci=False):
    """Exec matika.spec with PyInstaller globals stubbed; return captured kwargs.

    Returns a dict with keys 'EXE', 'COLLECT', 'BUNDLE' each mapping to the
    kwargs dict passed to that constructor in the spec.

    Pass ci=True to simulate a CI environment (sets CI=true). By default the CI
    env var is cleared so standalone/dev tests are not affected by the CI
    fail-loud guard.
    """
    for var in ("MATIKA_PRODUCT_NAME", "MATIKA_PRODUCT_VERSION", "CI"):
        monkeypatch.delenv(var, raising=False)
    if product_name is not None:
        monkeypatch.setenv("MATIKA_PRODUCT_NAME", product_name)
    if product_version is not None:
        monkeypatch.setenv("MATIKA_PRODUCT_VERSION", product_version)
    if ci:
        monkeypatch.setenv("CI", "true")

    captured: dict[str, dict] = {}

    def _capture(label):
        def _ctor(*args, **kwargs):
            captured[label] = kwargs
            return MagicMock()
        return _ctor

    namespace = {
        "Analysis": lambda *a, **k: MagicMock(),
        "PYZ": lambda *a, **k: MagicMock(),
        "EXE": _capture("EXE"),
        "COLLECT": _capture("COLLECT"),
        "BUNDLE": _capture("BUNDLE"),
        # The spec resolves SPEC-relative paths (VERSION, plugins/) off SPEC.
        "SPEC": str(SPEC_PATH),
    }

    exec(compile(SPEC_PATH.read_text(), str(SPEC_PATH), "exec"), namespace)
    return captured


def _matika_version_core() -> str:
    """The bare-core matika VERSION — the standalone/dev fallback identity."""
    import re
    raw = (SPEC_PATH.parent / "VERSION").read_text().strip()
    return re.match(r"v?(\d+\.\d+\.\d+)", raw).group(1)


# ---------------------------------------------------------------------------
# CI product build: env supplies the product identity
# ---------------------------------------------------------------------------

def test_product_env_drives_bundle_and_exe_names(monkeypatch):
    cap = _exec_spec(monkeypatch, product_name="ManoMatika", product_version="0.0.1")
    assert cap["EXE"]["name"] == "ManoMatika-0.0.1"
    assert cap["COLLECT"]["name"] == "ManoMatika-0.0.1"
    assert cap["BUNDLE"]["name"] == "ManoMatika-0.0.1.app"


def test_product_env_drives_info_plist_identity(monkeypatch):
    cap = _exec_spec(monkeypatch, product_name="ManoMatika", product_version="0.0.1")
    plist = cap["BUNDLE"]["info_plist"]
    assert plist["CFBundleName"] == "ManoMatika"
    assert plist["CFBundleDisplayName"] == "ManoMatika"
    # Version fields carry the PRODUCT version (bare core), not matika's.
    assert plist["CFBundleVersion"] == "0.0.1"
    assert plist["CFBundleShortVersionString"] == "0.0.1"
    assert cap["EXE"]["version_info"]["product_name"] == "ManoMatika"


def test_product_version_suffix_stripped_to_core(monkeypatch):
    """A product version passed at an rc TAG still names the bundle by bare core."""
    cap = _exec_spec(monkeypatch, product_name="ManoMatika", product_version="0.0.1-rc.2")
    assert cap["BUNDLE"]["name"] == "ManoMatika-0.0.1.app"
    assert cap["BUNDLE"]["info_plist"]["CFBundleVersion"] == "0.0.1"


# ---------------------------------------------------------------------------
# Standalone/dev build: no env -> framework defaults
# ---------------------------------------------------------------------------

def test_standalone_defaults_to_matika_and_version_file(monkeypatch):
    core = _matika_version_core()
    cap = _exec_spec(monkeypatch)  # no product env
    assert cap["BUNDLE"]["name"] == f"Matika-{core}.app"
    assert cap["EXE"]["name"] == f"Matika-{core}"
    assert cap["BUNDLE"]["info_plist"]["CFBundleName"] == "Matika"


# ---------------------------------------------------------------------------
# No hardcoded component identity may survive in the naming fields
# ---------------------------------------------------------------------------

def test_no_hardcoded_matika_literal_in_name_fields():
    text = SPEC_PATH.read_text()
    assert 'name=f"Matika-{APP_VERSION}"' not in text
    assert 'name=f"Matika-{APP_VERSION}.app"' not in text
    assert '"CFBundleName": "Matika"' not in text
    # The product identity must be read from the build-provided env var.
    assert "MATIKA_PRODUCT_NAME" in text
    assert "MATIKA_PRODUCT_VERSION" in text


# ---------------------------------------------------------------------------
# CI fail-loud guard — missing product env in CI context must be a hard failure
# ---------------------------------------------------------------------------

def test_ci_build_without_product_name_exits(monkeypatch):
    """Regression guard: if CI=true and MATIKA_PRODUCT_NAME is unset, the spec
    must exit(1) immediately rather than silently falling back to 'Matika' and
    producing a mis-named bundle that causes a confusing 'bundle not found'
    error at the DMG/installer step.

    Root cause: v0.0.4-rc.2 did not have this guard; the verification run
    27849321193 used matika branch feat/product-name-identity (which had the
    spec changes) via a temporary recipe pin, so the clean-main build was never
    actually tested. The guard ensures the misconfig surfaces immediately.
    """
    with pytest.raises(SystemExit):
        _exec_spec(monkeypatch, ci=True)  # CI=true, no product_name -> must exit


def test_ci_build_with_product_env_succeeds(monkeypatch):
    """CI=true + MATIKA_PRODUCT_NAME set must NOT trigger the guard."""
    cap = _exec_spec(monkeypatch, ci=True, product_name="ManoMatika", product_version="0.0.1")
    assert cap["BUNDLE"]["name"] == "ManoMatika-0.0.1.app"


def test_ci_guard_present_in_spec():
    """Structural guard: the CI fail-loud check must exist in the spec source."""
    text = SPEC_PATH.read_text()
    assert 'os.environ.get("CI")' in text
    assert 'MATIKA_PRODUCT_NAME' in text
