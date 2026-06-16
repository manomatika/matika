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
#   - This spec bundles Matika's static assets, templates, locales, menus, and
#     the Alembic migration tree.  Plugins are NOT bundled here — they are
#     extracted to ~/matika/plugins/ by launcher.py on first run.
#   - The app icon is a PNG (matika_icon_128.png).  Swap for a platform-native
#     .icns (macOS) or .ico (Windows) when those assets are available.

import os
import re as _re

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
_SEMVER_PRERELEASE = r"(?:%s(?:\.%s)*)" % (_SEMVER_PRE_IDENT, _SEMVER_PRE_IDENT)
# Build metadata: dot-separated alphanumeric-with-hyphen identifiers, after '+'.
_SEMVER_BUILD = r"(?:[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)"

_SEMVER_RE = _re.compile(
    r"^(?P<core>%s)(?:-(?P<prerelease>%s))?(?:\+(?P<build>%s))?$"
    % (_SEMVER_CORE, _SEMVER_PRERELEASE, _SEMVER_BUILD)
)


def _parse_semver(raw):
    """Strictly parse a SemVer 2.0.0 string of the form
    [v]MAJOR.MINOR.PATCH[-prerelease][+build].

    Mirror of src/matika/core/paths.py:_parse_semver. Returns
    (core, prerelease, build); raises ValueError naming the offending value on
    any invalid input.
    """
    if not isinstance(raw, str):
        raise ValueError(
            "invalid version %r: expected a string of the form "
            "[v]MAJOR.MINOR.PATCH[-prerelease][+build]" % (raw,)
        )
    candidate = raw.strip()
    if candidate.startswith("v"):
        candidate = candidate[1:]
    m = _SEMVER_RE.match(candidate)
    if not m:
        raise ValueError(
            "invalid version %r: expected SemVer of the form "
            "[v]MAJOR.MINOR.PATCH[-prerelease][+build] (three dot-separated "
            "non-negative integers without leading zeros, optional pre-release "
            "and build metadata)" % (raw,)
        )
    return m.group("core"), m.group("prerelease"), m.group("build")


def version_core(version):
    """Return the bare MAJOR.MINOR.PATCH core. Mirror of paths.py:version_core."""
    core, _prerelease, _build = _parse_semver(version)
    return core


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

# ---------------------------------------------------------------------------
# Hidden imports — packages that PyInstaller's static analysis misses
# ---------------------------------------------------------------------------
hiddenimports = [
    # SQLAlchemy dialects used at runtime
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.postgresql",
    "sqlalchemy.dialects.mysql",
    # Alembic internals
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
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    ["launcher.py"],
    pathex=[os.path.join(os.path.dirname(SPEC), "src")],
    binaries=[],
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
    name=f"Matika-{APP_VERSION}",
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
    icon="src/matika/static/img/matika_icon_128.png",
    version_info={
        "version": APP_VERSION,
        "description": "Matika — plugin-agnostic FastAPI desktop framework",
        "product_name": "Matika",
    },
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=f"Matika-{APP_VERSION}",
)

app = BUNDLE(
    coll,
    name=f"Matika-{APP_VERSION}.app",
    icon="src/matika/static/img/matika_icon_128.png",
    bundle_identifier="com.manomatika.matika",
    version=APP_VERSION,
    info_plist={
        "CFBundleName": "Matika",
        "CFBundleDisplayName": "Matika",
        "CFBundleVersion": APP_VERSION,
        "CFBundleShortVersionString": APP_VERSION,
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
    },
)
