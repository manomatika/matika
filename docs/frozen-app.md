> Part of [CLAUDE.md](../CLAUDE.md) — see the main file for orientation.

### Frozen App (PyInstaller desktop build)

The desktop build is a real, shipping artifact, not a future plan. Two files own it: **`matika.spec`** (the PyInstaller spec) freezes **`launcher.py`** (the repo-root entry script). The DMG/EXE wrapper around the freeze is built by **ahimsa** (`build.yml`); matika owns the spec + launcher, not the installer.

**Build-provided product identity.** The bundle is named from env, never hardcoded:
- `MATIKA_PRODUCT_NAME` → `APP_NAME` (falls back to `"Matika"` for a bare dev build); `MATIKA_PRODUCT_VERSION` → `APP_VERSION`, run through the bundled `version_core` so it is always **bare core** (falls back to the `VERSION` file core).
- The EXE/`.app`/COLLECT are named `f"{APP_NAME}-{APP_VERSION}"` → e.g. `ManoMatika-0.0.1.app`. `CFBundleName`/`CFBundleDisplayName` = `APP_NAME`; `CFBundleVersion`/`CFBundleShortVersionString` = `APP_VERSION`; `bundle_identifier="com.manomatika.matika"`.
- **CI fail-loud guard:** if `CI` is set but `MATIKA_PRODUCT_NAME` is not, the spec `sys.exit`s — a product build must carry the recipe's `application.product_name`.

**What `matika.spec` collects** (so the frozen app actually boots and Lookup works):
- `collect_all("alembic")` + `collect_all("sqlalchemy")`, plus `alembic.ini` and `migrations/` as datas — migrations run inside the freeze.
- `collect_all("yfinance")` + `collect_all("curl_cffi")` (and matching hiddenimports) — eyerate's `YahooScraperEndpoint` lazy-imports these at Lookup time; without them, Lookup fails only in the freeze.
- The **whole `matika` package** is force-bundled as hiddenimports (dynamic submodule imports the analyzer misses).
- The `plugins/` directory is bundled as datas (when present) — this is how plugins reach the freeze.
- `matika.spec` carries a **verbatim mirror** of the canonical `_parse_semver`/`version_core` parser (the third mirror, alongside `src/matika/core/paths.py` and `scripts/sync_version.py`) — keep all three in lockstep.

**First-run / boot contract (`launcher.py` `main()`):**
1. **Durable logging is set up FIRST**, to `~/matika/logs/matika-<date>.log`, and a `sys.excepthook` is installed so even an import-time crash leaves a log on disk.
2. **Schema init is in-process:** first run does `create_all()` then `alembic_command.stamp(cfg, "head")` — NOT `alembic upgrade`, and NOT a subprocess. In a freeze, `sys.executable` IS the app binary, so shelling out to `python -m alembic` fork-bombs the launcher; alembic is driven via its in-process Python API instead. (`migrations/env.py` is guarded so its `fileConfig` can't clobber the launcher's logging.)
3. **Data lives under `~/matika/`** (`logs/`, `data/matika.db`, `plugins/`); the launcher sets `MATIKA_PLUGINS_DIR=~/matika/plugins` so `AppLugService` discovers the extracted plugins.

**Plugin lifecycle in the freeze — every-launch, gated, data-preserving refresh** (`_extract_bundled_plugins`, runs on EVERY launch, *not* first-run-only):
- Each installed plugin carries a per-plugin marker `~/matika/plugins/<name>/.matika_plugin_install.json` recording the installed `version` + a sha256 code **fingerprint** (the dotfile prefix keeps `AppLugService`'s `applug.json` scan from treating it as a plugin).
- On each launch the launcher compares the bundled plugin's version and fingerprint to the marker. Refresh fires when **either** differs (`version_changed or code_changed`); otherwise it skips. This is the upgrade-refresh that fixes the **stale-plugin regression** — an upgraded app no longer runs last version's plugin code.
- Refresh is **data-preserving**: it copies only files in the bundle's code manifest and deletes only files recorded in the *previous* marker. User/runtime data (never in any marker) is untouched. Legacy installs with no marker are overwrite-only (nothing deleted).

This boot path is exercised in CI by ahimsa's `build.yml` (smoke-launch + tier-a/tier-b frozen feature verification on BOTH fresh-install and upgrade-over-stale paths — see `manomatika/ahimsa`).
