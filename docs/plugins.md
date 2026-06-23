> Part of [CLAUDE.md](../CLAUDE.md) — see the main file for orientation.

### Plugin Management System

The `plugins/` directory is **intentionally empty in git**. Plugins are injected at setup time, never committed. There are three injection patterns:

#### 1. Development (symlinks via `dev_setup.py`)
```
plugins.dev.json.example   ← template, committed
plugins.dev.json           ← per-developer config, gitignored
scripts/dev_setup.py       ← validates + creates symlinks
plugins/eyerate → /path/to/eyerate   ← result
```
`dev_setup.py` validates each entry has `applug.json` AND at least one `*_menus.json` before symlinking. It is idempotent and handles broken/wrong-target symlinks interactively.

#### 2. Server deployment (git clone or `MATIKA_PLUGINS_DIR`)
```bash
# Option A — clone into plugins/ (simple single-server)
cd plugins && git clone https://github.com/org/eyerate.git eyerate

# Option B — separate directory (recommended for production)
MATIKA_PLUGINS_DIR=/opt/matika/plugins  # set in .env
# clone plugins into /opt/matika/plugins/
```
`MATIKA_PLUGINS_DIR` is read in `AppLugService.__init__()` (`applug_service.py:34`) before falling back to `ROOT_DIR/plugins`. It works at full runtime — not test-only.

#### 3. End-user installer (shipped)
Standalone `.dmg`/`.exe` built with PyInstaller from `matika.spec` + `launcher.py`. Bundles the framework **and** its plugins; no Python environment required. matika ships **no installer of its own** — the single hosted installer is built by the **ahimsa** engine (`build.yml`) at the recipe-pinned tags and attached to the `manomatika/manomatika` product release. The freeze's runtime contract is detailed in [docs/frozen-app.md](frozen-app.md).

#### AppLug contract
Every plugin directory must contain:
- `applug.json` — manifest: `id`, `version`, `name`, `matika_version` (required — exact Matika version this AppLug was built and tested against), optional `display_name`, `entry_point`, `permissions`
- `<id>_menus.json` — consolidated menu file (schema v1.0) with two optional top-level sections:
  - `application` (optional) — an Application-type menu rendered as a dropdown in the plugin's hub
  - `roles` (optional) — array of role menus; each entry has `role`, `id`, `label_key`, and `items`
    - Admin role items: flat `Link` entries (no `Menu` wrapper)
    - Other role items: `Menu` wrapper containing nested links (dropdown behavior)
- Python class extending `BaseAppLug` with `on_load(db)` and `on_unload(db)`

`matika_version` (required) is checked at startup by `BaseAppLug._validate_compatibility()`. If absent or mismatched the AppLug is refused and skipped — a clear `RuntimeError` is logged. This is the compatibility contract baseline introduced in Matika 0.0.2; no breaking changes to `BaseAppLug` or the plugin discovery contract from this version forward.

`display_name` (optional) is the short UI label shown in the menu selector. Falls back to `name` if absent.

All plugin POST routes must add `check_page_permission` and `validate_csrf` dependencies.
