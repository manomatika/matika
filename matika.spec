# -*- mode: python ; coding: utf-8 -*-
#
# matika.spec — PyInstaller build spec for Matika frozen app
#
# Build:
#   pyinstaller matika.spec
#
# Prerequisites:
#   pip install pyinstaller
#   npm run build   (compiles TypeScript → src/matika/static/js/)
#
# Notes:
#   - This spec bundles Matika's static assets, templates, locales, menus, the
#     Alembic migration tree, and any plugins cloned into plugins/ by the ahimsa
#     build job.  launcher.py extracts the bundled plugins to ~/matika/plugins/
#     on first run (see _extract_bundled_plugins).
#   - The app icon is a PNG (matika_icon_128.png).  Swap for a platform-native
#     .icns (macOS) or .ico (Windows) when those assets are available.

import os
import re as _re
import sys as _sys

# collect_all is only importable while PyInstaller is actually driving this
# spec (the normal `pyinstaller matika.spec` path). The naming/identity unit
# tests exec this spec source directly in a stubbed namespace WITHOUT
# PyInstaller installed; guard the import so the spec stays exec-able there.
# In every real build PyInstaller is present, so the except branch is
# unreachable and full alembic/sqlalchemy collection always runs.
try:
    from PyInstaller.utils.hooks import collect_all
except ImportError:  # pragma: no cover - only hit by the spec-exec unit tests
    collect_all = None

# ---------------------------------------------------------------------------
# Version — read from the VERSION file at spec-build time so the EXE name and
# version metadata always stay in sync with the repo's single source of truth
# without any manual edits to this spec.
#
# APP_VERSION is the BARE CORE (MAJOR.MINOR.PATCH). macOS requires
# CFBundleShortVersionString / CFBundleVersion to be numeric x.y.z, and
# bundle/exe names must match the cross-repo contract `Matika-<bare-core>`. The
# pre-release suffix (-dev, -rc.N) and build metadata are human/audit markers
# only and never enter any OS/installer field or artifact name.
#
# CANONICAL SEMVER PARSER (mirror): the parser below is an IDENTICAL copy of the
# strict SemVer 2.0.0 parser whose canonical source is
# src/matika/core/paths.py (_parse_semver / version_core). The spec cannot
# import the installed package, so the parser is inlined here verbatim. Any
# change in paths.py MUST be applied here (and in scripts/sync_version.py).
# ---------------------------------------------------------------------------

# MAJOR.MINOR.PATCH: each a non-negative integer with NO leading zeros.
_SEMVER_CORE = r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
# A pre-release identifier: numeric (no leading zeros) OR alphanumeric-with-hyphen.
_SEMVER_PRE_IDENT = r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
# Dot-separated pre-release identifiers, after the first '-'.
_SEMVER_PRERELEASE = rf"(?:{_SEMVER_PRE_IDENT}(?:\.{_SEMVER_PRE_IDENT})*)"
# Build metadata: dot-separated alphanumeric-with-hyphen identifiers, after '+'.
_SEMVER_BUILD = r"(?:[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)"

_SEMVER_RE = _re.compile(
    rf"^(?P<core>{_SEMVER_CORE})"
    rf"(?:-(?P<prerelease>{_SEMVER_PRERELEASE}))?"
    rf"(?:\+(?P<build>{_SEMVER_BUILD}))?$"
)


def _parse_semver(raw):
    """Strictly parse a SemVer 2.0.0 string of the form
    ``[v]MAJOR.MINOR.PATCH[-prerelease][+build]``.

    A single optional leading 'v' is tolerated and stripped. MAJOR/MINOR/PATCH
    are non-negative integers with no leading zeros (so '01.2.3' is invalid),
    exactly three of them. Pre-release identifiers are dot-separated; numeric
    identifiers carry no leading zeros; identifiers are alphanumerics and hyphens
    (so a pre-release identifier MAY contain hyphens, e.g. 'alpha-1'). Build
    metadata after '+' is NOT part of the core and is NOT a pre-release signal.
    An empty pre-release ('1.2.3-') or empty build is invalid.

    Returns ``(core, prerelease, build)`` where prerelease/build are the
    substrings after '-'/'+' or None when absent. Raises ValueError naming the
    offending value and the expected shape on any invalid input.
    """
    if not isinstance(raw, str):
        raise ValueError(
            f"invalid version {raw!r}: expected a string of the form "
            f"[v]MAJOR.MINOR.PATCH[-prerelease][+build]"
        )
    candidate = raw.strip()
    if candidate.startswith("v"):
        candidate = candidate[1:]
    m = _SEMVER_RE.match(candidate)
    if not m:
        raise ValueError(
            f"invalid version {raw!r}: expected SemVer of the form "
            f"[v]MAJOR.MINOR.PATCH[-prerelease][+build] "
            f"(three dot-separated non-negative integers without leading zeros, "
            f"optional pre-release and build metadata)"
        )
    return m.group("core"), m.group("prerelease"), m.group("build")


def version_core(version: str) -> str:
    """Return the bare MAJOR.MINOR.PATCH core of a SemVer string.

    The version CORE is the canonical identity used for ALL comparison,
    artifact/bundle naming, and OS/installer/Info.plist version fields. The
    pre-release SUFFIX (``-dev``, ``-rc.N``, ...) and build metadata live only on
    human/audit surfaces (the VERSION file string, git tags, release titles, the
    audit log).

    Examples:
      "0.0.4-dev"        -> "0.0.4"
      "0.0.4-rc.1"       -> "0.0.4"
      "v0.0.4-rc.1"      -> "0.0.4"
      "0.0.4+build.5"    -> "0.0.4"
      "1.2.3-alpha-1"    -> "1.2.3"
      "0.0.4"            -> "0.0.4"

    Raises ValueError (naming the offending value) on any non-SemVer input.
    """
    core, _prerelease, _build = _parse_semver(version)
    return core


# ---------------------------------------------------------------------------
# Product identity (cross-repo: driven by ahimsa build.yml from the recipe).
#
# matika is a reusable FRAMEWORK; the user-facing PRODUCT that bundles it
# (e.g. ManoMatika) owns the installed bundle/exe identity. The ahimsa build
# job passes the recipe's product name + product version in via env so the
# frozen artifact is named after the PRODUCT, not after matika the component:
#
#   MATIKA_PRODUCT_NAME    -> proper-noun bundle/exe identity   (e.g. ManoMatika)
#   MATIKA_PRODUCT_VERSION -> bare-core product version          (e.g. 0.0.1)
#
# When neither is set — a standalone developer build — the framework's own
# name ("Matika") and its VERSION-file core are used as sensible defaults. CI
# product builds always set both, so they emit ManoMatika-<product-core>.app.
# ---------------------------------------------------------------------------
APP_NAME = os.environ.get("MATIKA_PRODUCT_NAME") or "Matika"

# CI guard: a CI product build that omits MATIKA_PRODUCT_NAME would silently
# emit Matika-<framework-version> instead of the correct product bundle name,
# causing the DMG/installer step to fail on a confusing "bundle not found"
# error rather than a clear misconfiguration message here. Fail loudly instead.
if os.environ.get("CI") and not os.environ.get("MATIKA_PRODUCT_NAME"):
    _sys.exit(
        "matika.spec: CI=true but MATIKA_PRODUCT_NAME is not set.\n"
        "A product build must pass the recipe's application.product_name via "
        "MATIKA_PRODUCT_NAME (e.g. ManoMatika). "
        "Ahimsa's build.yml provides this from recipe_info outputs. "
        "Without it the bundle falls back to 'Matika' and the DMG/installer "
        "step fails with 'bundle not found'. "
        "Ensure the cloned matika.spec tag includes the product-identity "
        "changes (v0.0.4-rc.3 or later)."
    )

_product_version = os.environ.get("MATIKA_PRODUCT_VERSION")
if _product_version:
    APP_VERSION = version_core(_product_version)  # bare core, see note above
else:
    _VERSION_FILE = os.path.join(os.path.dirname(SPEC), "VERSION")
    with open(_VERSION_FILE, "r") as _vf:
        _version_raw = _vf.read().strip()
    APP_VERSION = version_core(_version_raw)  # bare core, see note above

# ---------------------------------------------------------------------------
# Data files bundled into the frozen app
# ---------------------------------------------------------------------------
datas = [
    # Static web assets (CSS, JS, images)
    ("src/matika/static", "src/matika/static"),
    # Jinja2 HTML templates
    ("src/matika/templates", "src/matika/templates"),
    # i18n locale files
    ("src/matika/locales", "src/matika/locales"),
    # Core menu definitions
    ("src/matika/menus", "src/matika/menus"),
    # Alembic configuration and migration scripts
    ("alembic.ini", "."),
    ("migrations", "migrations"),
    # Version file (read at runtime by paths.get_matika_version)
    ("VERSION", "."),
]

# Plugins cloned by the ahimsa build job into plugins/ are bundled into the
# frozen app here so that launcher.py::_extract_bundled_plugins() can copy
# them from sys._MEIPASS/plugins/ to ~/matika/plugins/ on first run.
# The guard is required: in a developer checkout plugins/ does not exist and
# must not cause pyinstaller matika.spec to fail.
_plugins_src = os.path.join(os.path.dirname(SPEC), "plugins")
if os.path.isdir(_plugins_src):
    datas.append(("plugins", "plugins"))

# ---------------------------------------------------------------------------
# Platform-native icon (per-platform; PNG placeholder works only with Pillow)
# ---------------------------------------------------------------------------
_ICON = (
    "src/matika/static/img/matika.icns" if _sys.platform == "darwin"
    else "src/matika/static/img/matika.ico" if _sys.platform == "win32"
    else None
)

# ---------------------------------------------------------------------------
# Hidden imports — packages that PyInstaller's static analysis misses
# ---------------------------------------------------------------------------
hiddenimports = [
    # SQLAlchemy dialects used at runtime
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.postgresql",
    "sqlalchemy.dialects.mysql",
    # Alembic — command and config are imported inside _run_alembic_upgrade at
    # runtime; the spec-time analysis misses late/conditional imports.
    "alembic.command",
    "alembic.config",
    "alembic.runtime.migration",
    "alembic.operations.ops",
    # passlib bcrypt backend
    "passlib.handlers.bcrypt",
    # Uvicorn / anyio workers
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.lifespan.on",
    "anyio._backends._asyncio",
    # python-multipart (form parsing)
    "multipart",
    # python-jose JWT
    "jose",
    "jose.jwt",
    # Authlib OAuth support
    "authlib.integrations.starlette_client",
    # Jinja2 extensions
    "jinja2.ext",
]

# ---------------------------------------------------------------------------
# Full-package collection — alembic + sqlalchemy
#
# WHY collect_all and not just hiddenimports: the in-process first-run
# migration (launcher.py::_run_alembic_upgrade -> alembic.command.upgrade)
# fails in the frozen bundle with "No module named 'alembic'" because listing
# "alembic.command"/"alembic.config" as hiddenimports does NOT pull in the
# rest of the alembic PACKAGE that the migration runtime loads dynamically:
# alembic.runtime / alembic.ddl dialect modules, alembic.util, the templates/
# data tree, and the importlib-metadata entry points. collect_all("alembic")
# returns (datas, binaries, hiddenimports) covering all of it.  sqlalchemy is
# collected the same way so every dialect/submodule that alembic + the app
# import lazily (e.g. sqlalchemy.sql.default_comparator) is present.
#
# These build on top of the explicit hiddenimports above (kept as a belt-and-
# suspenders for the specific late imports in _run_alembic_upgrade) and the
# alembic.ini + migrations/ datas below, which the migration runtime resolves
# at sys._MEIPASS-relative paths inside the frozen app.
# ---------------------------------------------------------------------------
if collect_all is not None:
    _alembic_datas, _alembic_bins, _alembic_hidden = collect_all("alembic")
    _sqlalchemy_datas, _sqlalchemy_bins, _sqlalchemy_hidden = collect_all("sqlalchemy")

    datas += _alembic_datas + _sqlalchemy_datas
    hiddenimports += _alembic_hidden + _sqlalchemy_hidden
    _collected_binaries = _alembic_bins + _sqlalchemy_bins
else:  # pragma: no cover - spec exec'd outside a real PyInstaller build
    _collected_binaries = []

# ---------------------------------------------------------------------------
# Bundle the ENTIRE matika package.
#
# matika submodules are loaded DYNAMICALLY and so are invisible to PyInstaller's
# static analysis of launcher.py:
#   - alembic's migrations/env.py runs `from matika.models import Base` when the
#     in-process first-run migration executes. alembic exec()s env.py at
#     runtime, so PyInstaller never traces its imports — and matika.models was
#     consequently NOT frozen, crashing the migration with
#     "No module named 'matika.models'".
#   - applugs import assorted matika submodules (security.service,
#     auth.dependencies, core.utils, ...) when AppLugService loads them.
#
# Enumerate every matika module by WALKING the source tree and add them as
# hiddenimports. We deliberately do NOT import the package to enumerate it
# (collect_submodules would): importing matika.main fires its module-level
# init_db()/init_plugins() side effects, which must never run at build time.
# PyInstaller analyses each hidden import statically (no execution), so this is
# side-effect-free and freezes the whole package.
# ---------------------------------------------------------------------------
def _matika_submodules(src_root):
    names = []
    pkg_root = os.path.join(src_root, "matika")
    for dirpath, _dirs, files in os.walk(pkg_root):
        if "__pycache__" in dirpath.split(os.sep):
            continue
        for fname in files:
            if not fname.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fname), src_root)
            mod = rel[:-3].replace(os.sep, ".")
            if mod.endswith(".__init__"):
                mod = mod[: -len(".__init__")]
            names.append(mod)
    return names


hiddenimports += _matika_submodules(os.path.join(os.path.dirname(SPEC), "src"))

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    ["launcher.py"],
    pathex=[os.path.join(os.path.dirname(SPEC), "src")],
    binaries=_collected_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=f"{APP_NAME}-{APP_VERSION}",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_ICON,
    version_info={
        "version": APP_VERSION,
        "description": "Matika — plugin-agnostic FastAPI desktop framework",
        "product_name": APP_NAME,
    },
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=f"{APP_NAME}-{APP_VERSION}",
)

app = BUNDLE(
    coll,
    name=f"{APP_NAME}-{APP_VERSION}.app",
    icon=_ICON,
    bundle_identifier="com.manomatika.matika",
    version=APP_VERSION,
    info_plist={
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleVersion": APP_VERSION,
        "CFBundleShortVersionString": APP_VERSION,
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
    },
)
