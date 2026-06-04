# -*- mode: python ; coding: utf-8 -*-
"""
matika.spec — PyInstaller spec for the Matika standalone app.

=== Build context (production — set up by ahimsa's build pipeline) ===

  <repo_root>/
    VERSION              — clean X.Y.Z version string (no _dev suffix)
    alembic.ini          — alembic configuration
    migrations/          — alembic migration scripts
    assets/
      icon.icns          — application icon (macOS; required for icon in bundle)
    plugins/
      <name>/            — one directory per bundled applug (e.g. eyerate/)
        applug.json      — applug manifest
        <name>_menus.json
        src/             — applug Python source tree
          <name>/        — package directory

The launcher extracts plugins from sys._MEIPASS/plugins/<name>/ to
~/matika/plugins/<name>/ at first run and adds their src/ to sys.path.
Plugin source is bundled as DATA (not compiled to bytecode) so that
__file__ resolves correctly at runtime from the extracted location.

=== Dev-cycle invocation (no build pipeline) ===

  cd ~/dev/projects/matika
  pyinstaller scripts/matika.spec --noconfirm

In dev mode (plugins/ absent, assets/ absent), the spec builds a
matika-only app: no plugins bundled, no icon, version warning for _dev.
This is expected and intentional for local test builds.

=== Environment variables consumed at spec-load time ===

  MATIKA_APP_BUNDLE_ID   macOS CFBundleIdentifier.
                         Default: "com.matika.framework"
                         Production: set to recipe's application.bundle_id.

  PYI_ARCH               PyInstaller target architecture for cross-compilation.
                         e.g. "arm64" or "x86_64". Optional.
"""

import os
import sys
from pathlib import Path

# PyInstaller sets SPECPATH to the directory containing this spec file.
# This spec lives in scripts/, so BUILD_ROOT is the repo root.
SPEC_DIR   = Path(SPECPATH)         # noqa: F821 — SPECPATH injected by PyInstaller
BUILD_ROOT = SPEC_DIR.parent

PLUGINS_DIR  = BUILD_ROOT / "plugins"
ASSETS_DIR   = BUILD_ROOT / "assets"
VERSION_FILE = BUILD_ROOT / "VERSION"

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
if not VERSION_FILE.exists():
    raise FileNotFoundError(
        f"VERSION file not found: {VERSION_FILE}\n"
        "The build pipeline must provide a clean X.Y.Z VERSION file."
    )

_version_raw = VERSION_FILE.read_text().strip()
# MATIKA_BUILD_RELEASE=1 signals a production build from the ahimsa pipeline.
# In release mode, _dev in VERSION is a hard error — we never ship _dev builds.
# In dev mode (env var absent), _dev is stripped with a warning; the developer
# is intentionally building a local test app, not a release.
_is_release_build = os.environ.get("MATIKA_BUILD_RELEASE", "").strip() == "1"

if "_dev" in _version_raw:
    if _is_release_build:
        raise ValueError(
            f"VERSION is {_version_raw!r} — release builds require a clean X.Y.Z version.\n"
            "The build pipeline must strip _dev from VERSION before invoking PyInstaller."
        )
    else:
        print(
            f"[matika.spec] WARNING: VERSION is {_version_raw!r} — "
            "stripping _dev suffix for local dev build (not a release)"
        )

APP_VERSION = _version_raw.removesuffix("_dev")
print(f"[matika.spec] Building version: {APP_VERSION}")

# ---------------------------------------------------------------------------
# Icon
# ---------------------------------------------------------------------------
_icon_path = ASSETS_DIR / "icon.icns"
if _icon_path.exists():
    ICON = str(_icon_path)
    print(f"[matika.spec] Icon: {_icon_path}")
else:
    ICON = None
    print(f"[matika.spec] NOTE: icon not found at {_icon_path} — building without icon")

# ---------------------------------------------------------------------------
# Bundle identifier
# ---------------------------------------------------------------------------
BUNDLE_ID = os.environ.get("MATIKA_APP_BUNDLE_ID", "com.matika.framework")
print(f"[matika.spec] Bundle ID: {BUNDLE_ID}")

# ---------------------------------------------------------------------------
# Core data files
# ---------------------------------------------------------------------------
_matika_src = BUILD_ROOT / "src" / "matika"

data_files = [
    (str(_matika_src / "static"),    "src/matika/static"),
    (str(_matika_src / "templates"), "src/matika/templates"),
    (str(_matika_src / "locales"),   "src/matika/locales"),
    (str(_matika_src / "menus"),     "src/matika/menus"),    # runtime-required JSON menu files
    (str(VERSION_FILE),              "."),
]

# Alembic config + migration scripts (required for first-run DB init)
_alembic_ini = BUILD_ROOT / "alembic.ini"
_migrations  = BUILD_ROOT / "migrations"
if _alembic_ini.exists():
    data_files.append((str(_alembic_ini), "."))
if _migrations.exists():
    data_files.append((str(_migrations), "migrations"))

# ---------------------------------------------------------------------------
# Dynamic plugin bundling
# ---------------------------------------------------------------------------
# Plugin Python source is bundled as DATA (not via pathex/hiddenimports).
# Rationale: plugins are extracted to ~/matika/plugins/<name>/ at first run
# and imported from there. Bundling source as data preserves __file__
# semantics: os.path.dirname(plugin.__file__) resolves inside ~/matika/plugins/,
# so relative paths to templates/, static/, locales/ all work correctly.
#
# The launcher (launcher.py) handles extraction and sys.path wiring.
if PLUGINS_DIR.exists():
    for _plugin_dir in sorted(PLUGINS_DIR.iterdir()):
        # Skip symlinks — dev setup creates symlinks to local repos (dev_setup.py).
        # Production builds have real cloned directories placed by the build pipeline.
        if _plugin_dir.is_symlink() or not _plugin_dir.is_dir():
            continue
        _name = _plugin_dir.name
        _bundled = False

        _plugin_src = _plugin_dir / "src"
        if _plugin_src.is_dir():
            data_files.append((str(_plugin_src), f"plugins/{_name}/src"))
            _bundled = True

        for _manifest in (
            _plugin_dir / "applug.json",
            _plugin_dir / f"{_name}_menus.json",
        ):
            if _manifest.exists():
                data_files.append((str(_manifest), f"plugins/{_name}"))
                _bundled = True

        if _bundled:
            print(f"[matika.spec] Bundling plugin: {_name}")
        else:
            print(f"[matika.spec] WARNING: plugin dir {_plugin_dir} has no bundleable content")
else:
    print(f"[matika.spec] Dev mode — no plugins/ directory, building matika-only app")

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
block_cipher = None

a = Analysis(
    [str(SPEC_DIR / "launcher.py")],
    pathex=[str(BUILD_ROOT / "src")],
    binaries=[],
    datas=data_files,
    hiddenimports=[
        # Web server & framework
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.protocols.websockets.wsproto_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        "uvicorn.lifespan.auto",
        "fastapi",
        "starlette",
        "starlette.middleware.sessions",
        "anyio.backends._asyncio",
        "multipart",
        "itsdangerous",
        "httpx",

        # Authentication & security
        "authlib",
        "authlib.integrations",
        "authlib.integrations.starlette_client",
        "passlib",
        "passlib.handlers.bcrypt",
        "jose",
        "jose.backends",
        "jose.backends.cryptography_backend",
        "cryptography",
        "bcrypt",

        # Database & migrations
        "sqlalchemy",
        "sqlalchemy.sql.default_comparator",
        "sqlalchemy.dialects.sqlite",
        "alembic",
        "alembic.runtime.migration",
        "alembic.operations",

        # Matika internal modules
        "matika.core.paths",
        "matika.core.utils",
        "matika.core.logging_config",
        "matika.database",
        "matika.i18n",
        "matika.auth.service",
        "matika.auth.dependencies",
        "matika.security.service",
        "matika.data_mgmt.export_import",
        "matika.routers.public",
        "matika.routers.settings",
        "matika.routers.admin",

        # System utilities
        "webbrowser",
        "threading",
        "multiprocessing",
        "pkg_resources.py2_warn",
        "importlib_metadata",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tests"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Matika",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=os.environ.get("PYI_ARCH"),
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Matika",
)

if sys.platform == "darwin":
    app = BUNDLE(  # noqa: F821
        coll,
        name="Matika.app",
        icon=ICON,
        bundle_identifier=BUNDLE_ID,
        info_plist={
            "NSHighResolutionCapable": "True",
            "LSBackgroundOnly": "False",
            "NSAppleEventsUsageDescription": (
                "Matika needs permission to show startup alerts and open your browser."
            ),
            "NSLocalNetworkUsageDescription": (
                "Matika runs a local web server to provide the dashboard."
            ),
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
        },
    )
