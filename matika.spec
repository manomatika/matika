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

# ---------------------------------------------------------------------------
# Version — read from the VERSION file at spec-build time so the EXE name and
# version metadata always stay in sync with the repo's single source of truth
# without any manual edits to this spec.
#
# APP_VERSION is the BARE CORE (X.Y.Z): everything before the first "-". macOS
# requires CFBundleShortVersionString / CFBundleVersion to be numeric x.y.z, and
# bundle/exe names must match the cross-repo contract `Matika-<bare-core>`. The
# pre-release suffix (-dev, -rc.N) is a human/audit marker only and never enters
# any OS/installer field or artifact name.
#
# This mirrors matika.core.paths.version_core; the spec cannot import the
# installed package, so the one-line "everything before the first '-'" rule is
# inlined here.
# ---------------------------------------------------------------------------
_VERSION_FILE = os.path.join(os.path.dirname(SPEC), "VERSION")
with open(_VERSION_FILE, "r") as _vf:
    _version_raw = _vf.read().strip()
APP_VERSION = _version_raw.split("-", 1)[0].strip()  # bare core, see note above

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
