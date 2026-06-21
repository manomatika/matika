**Matika** | Version: **v0.0.4-rc.7** | Copyright (c) 2026 Patrick James Tallman

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working Style & Discipline

This section captures the standing working rules across the manomatika ecosystem. **CLAUDE.md is authoritative for how a fresh Claude Code instance should operate in this repo; keep it current as practices evolve.** The terminal milestone of every release is `Documentation & Release Readiness`, which includes auditing and updating every CLAUDE.md against what actually shipped.

### Documentation integrity

CLAUDE.md must never knowingly contain stale information. Whenever CLAUDE.md is edited or regenerated, every factual claim about this repo (workflow/job status, ownership boundaries, file locations, build/release state) must be verified against the actual current repo state before being written. Stale claims are defects. When a claim cannot be verified, omit it rather than guess.

### Collaboration model

- **Human in the loop for every change.** The user holds architecture, code review, and merge decisions. Don't merge PRs; don't push without explicit instruction; don't open PRs without the user's go-ahead.
- **One question or command batch at a time.** When asking a question or proposing actions, stop and wait for the user's answer or for the user to read previous output before continuing. Don't paste a new prompt or run new commands on top of unreviewed output.
- **Investigate-and-report before editing when scope is unclear.** Read the relevant code/docs first, surface what you find, and let the user direct the fix. Never assume; never silently expand scope.
- **Push back on overthinking and scope creep.** Best-practice patterns, never papered-over hacks. Fix issues correctly now — except items the user has explicitly deferred (e.g. follow-on issues filed against a later milestone).
- **Flag best-practice violations before implementing.** If a request would land an anti-pattern (security bypass, hack-around, etc.), surface the concern and let the user decide before writing code.

### Git, branches, references, and worktrees

- **The user does all git review and merges in the browser.** Don't merge PRs, push to main, or tag releases unless explicitly instructed.
- **Don't stage or commit unless explicitly granted.** The user handles `git add` / `git commit` manually by default. When granted, follow the conventional-commit pattern (`docs:`, `fix:`, `feat:`, `refactor:`, etc.) and include `Closes manomatika/<repo>#N` (fully qualified) where applicable.
- **Cross-repo issue/PR references must always be fully qualified.** Write `manomatika/matika#N`, `manomatika/eyerate#N`, `manomatika/ahimsa#N` — never a bare `#N` for an issue that lives in a different repo. Bare refs have caused real damage: a misqualified `Closes #11` / `Closes #12` in matika PR #35 closed unrelated issues in another repo's tracker. Bare refs are only safe when the PR and the issue are in the same repo.
- **cc does not run `git merge` locally.** Integration of branches is done by the user via PR merge in the browser. For any local branch updates cc performs, use `git rebase` or `git cherry-pick`. cc may run `rm -rf` ONLY within a repo working directory under `~/dev/projects/` (a clone `~/dev/projects/<repo>/` or a worktree `~/dev/projects/<repo>-<branch>/`) or under `~/dev/projects/cc_output/` — never anywhere else on the filesystem, and never with an unanchored or variable-expanded path that could resolve outside them. Targeted `git rm` for tracked files remains the norm; `rm -rf` is the constrained exception (rule 23).
- **`VERSION` is the single source of truth** for version metadata in this repo. Never hand-edit version literals in other files; release tooling propagates from `VERSION`.
- **The user uses git worktrees** for parallel work (e.g. `~/dev/projects/matika-45/` alongside `~/dev/projects/matika/` on a separate branch). At any moment, the user may be operating in any of several working directories for the same repo. Always check the current branch (`git branch --show-current`) and confirm it matches what you expect before assuming.
- **Multi-instance/parallel discipline.** When operating as one of multiple parallel cc instances, stay strictly within the assigned worktree, branch, and scope of files described in the task. Do not modify files outside the assigned scope, even if issues are noticed elsewhere — surface those issues to the user as separate items to triage rather than fixing in-flight. Cross-cutting changes that touch another agent's work area must be coordinated by the user, not initiated unilaterally.

### Code and test discipline

- **Regression tests are required for every fix.** A bug fix that doesn't include a test that would have caught the bug isn't done.
- **All tests must RUN IN FULL and pass — 100% clean.** Every affected repo's COMPLETE suite must RUN with nothing excluded, deselected, skipped, or marked integration-only, and pass: 0 failed / 0 skipped / 0 xfail / 0 deselected / 0 warnings. No test may be excluded or filtered and no warning suppressed without the product owner's explicit, per-case approval recorded as a documented rule variation.
- **Full-suite, every change, everywhere — 100% clean (standing rule 21).** ANY code change, in ANY repo, requires the COMPLETE unit-test suite of every affected repo (and any repo whose behavior could be impacted) to RUN IN FULL — nothing excluded, deselected, skipped, or marked integration-only — and pass 100%: 0 failed / 0 skipped / 0 xfail / 0 deselected / 0 warnings. Eliminate every warning at its ROOT (fix the code or bump the dependency); never blanket-suppress with a `filterwarnings` / `-W ignore` / `-m 'not …'` filter. Use each repo's correct test environment (the uv-managed `.venv`) so a green run is never an env artifact. A change is not done until every suite is 100% clean.
- **Escaped-bug regression mandate (standing rule 22).** Any bug that reaches CI, an rc, or install/runtime testing without being caught by the suite MUST, as part of its fix, gain a regression test that would have caught it — added at the layer where it escaped (unit/integration for logic gaps; a feature/E2E check against the FROZEN, pinned artifact for product-behavior gaps). The fix is not done until that test exists, fails without the fix, and passes with it.
- **Never weaken or disable security / correctness checks** (CSRF, permission, auth, validation) as a workaround. If a check is producing a wrong answer, fix the call site to satisfy it correctly — never bypass.

### Repository ecosystem

- **manomatika** is the GitHub org. The shipped PRODUCT is **ManoMatika** — a pinned *triple* of component versions (matika + eyerate + ahimsa), blessed by a single product release. The repos:
  - **manomatika/manomatika** — PRODUCT AUTHORITY. Owns the recipes, the audit log (`release-log.yaml` + `RELEASES.md`), the product release + single hosted installer binary, cross-component umbrella docs, the per-version manifest/BOM (pins each component by tag AND resolved SHA), and the QA gate.
  - **manomatika/matika** — the framework (plugin-agnostic FastAPI host). **This repo.** A component with self-scoped architecture docs and notes-only GitHub releases (no installer binaries).
  - **manomatika/eyerate** — the reference AppLug (financial security tracking). Component; notes-only releases.
  - **manomatika/ahimsa** — the recipe ENGINE: build / validation / release *mechanism* + recipe *schema*. Owns no recipes, no audit-log content, and hosts no product releases of its own.
- Local clones live at `~/dev/projects/<repo>/` (sibling directories). Additional worktrees for the same repo live at `~/dev/projects/<repo>-<branch>/`.

### Milestones, Project, and dates

- **Milestone naming is shared and match-when-present** across repos. When a milestone exists in more than one repo, its title is byte-for-byte identical so the org Project rolls it up into a single cross-repo group. Milestone names never contain version numbers or dates.
- **Canonical milestone titles in the current release cycle:**
  - `Deployment & Install`
  - `Cleanup & Tooling`
  - `Registry` (ahimsa only)
  - `Signing & Distribution` (ahimsa only)
  - `QA & System Test` (ahimsa only)
  - `Planning` (matika + eyerate + ahimsa)
  - `Playwright` (matika only)
  - `Documentation & Release Readiness` — the terminal release gate (all three)
- **Org-level Project: [ManoMatika Roadmap](https://github.com/orgs/manomatika/projects/1)** is the cross-repo backlog view. Its description records which component versions compose each manomatika release (e.g. ManoMatika v0.0.1 = matika v0.0.4 + eyerate v0.0.4 + ahimsa v0.0.1).
- **Milestone due dates are the single source of truth for dates.** The roadmap renders timelines from milestone Markers; do NOT create per-item date fields on the Project for scheduling (Pattern A — milestone-driven).

### Communication and output

- **Put prompts and commands in code blocks** so the user can one-tap copy them.
- The user is on **macOS / iTerm2** (tmux planned). Shell defaults to zsh.
- The user is **expert in software architecture and engineering, novice in git/GitHub specifics.** When git or `gh` commands appear in plans or output, explain plainly what they do, what they touch, and what the user will see.

## Commands

### Development Setup
```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
npm install
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
```

### Plugin Setup (one-time per machine)
```bash
# Copy the example config and edit it to point at your local plugin repos
cp plugins.dev.json.example plugins.dev.json
# Edit plugins.dev.json, then run:
python scripts/dev_setup.py
```
`dev_setup.py` is idempotent — safe to run multiple times. It validates each path contains both `applug.json` and at least one `*_menus.json` before creating symlinks. `plugins.dev.json` is in `.gitignore` and is never committed.

### Required Environment Variables
```bash
# Generate a secure key (required — app refuses to start without it)
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")

# Or create a persistent .env file (copy .env.example first):
cp .env.example .env   # then edit .env
export $(cat .env | xargs)
```

AppLug version compatibility is decided on the bare version **CORE** (`X.Y.Z`):
the pre-release suffix (`-dev`, `-rc.N`) is stripped from BOTH the running
version and the AppLug's declared `matika_version` before comparison. So a
pre-release runtime (e.g. `X.Y.Z-dev` or `X.Y.Z-rc.N`) automatically loads any
AppLug pinned to its bare core `X.Y.Z`. There is no `MATIKA_ENV` escape hatch —
the old development-mode relaxation has been removed. Never commit `.env`.

### Run the Development Server
```bash
source .venv/bin/activate && export $(cat .env | grep -v '^#' | xargs) && PYTHONPATH=src uvicorn matika.main:app --host 127.0.0.1 --port 8000 --reload
```

Or as separate steps for clarity:
```bash
source .venv/bin/activate
export $(cat .env | grep -v '^#' | xargs)
PYTHONPATH=src uvicorn matika.main:app --host 127.0.0.1 --port 8000 --reload
```

Why each part is needed:
- `source .venv/bin/activate` — required; puts `venv/bin/` on PATH so `uvicorn` and all dependencies are found
- `export $(cat .env | grep -v '^#' | xargs)` — loads `SECRET_KEY` (and any other vars) from `.env` into the shell (`grep -v '^#'` strips comment lines)
- `PYTHONPATH=src` — tells Python where to find the `matika` package
- `--reload` — auto-restarts the server on file changes

### Build TypeScript
```bash
npm run build   # compiles src/frontend/*.ts → src/matika/static/js/
```

### Database Migrations (Alembic)
```bash
PYTHONPATH=src alembic upgrade head                              # apply all pending
PYTHONPATH=src alembic current                                   # check revision
PYTHONPATH=src alembic revision --autogenerate -m "description"  # generate from model changes
PYTHONPATH=src alembic downgrade -1                              # roll back one
```

### Tests
```bash
pytest                                                      # all tests
pytest tests/test_auth.py                                   # one module
pytest tests/test_auth.py::test_login_success               # one test
```

---

## Architecture

Matika is a **plugin-agnostic FastAPI framework** — the core has zero knowledge of any business domain. Domain logic lives entirely in plugins called **AppLugs**.

### Installed product identity vs. internal identity

matika is the **component repo/package**; the shipped PRODUCT it composes into is **ManoMatika** (proper noun), named by the recipe's `application.product_name` (owned by `manomatika/manomatika`). The split:

- **User-facing → `ManoMatika`.** The FastAPI runtime title is `title="ManoMatika"` (`src/matika/main.py`), and the en/es locale brand strings are ManoMatika (`src/matika/locales/{en,es}.json` — e.g. `"title": "ManoMatika - Yield Tracker"`). The frozen bundle/exe and shortcuts are `ManoMatika-<product-core>.app` / `.exe` (see *Frozen App*).
- **Internal/runtime → lowercase `matika`.** Repo slug, Python package (`matika`), the `~/matika/` data dir, `MATIKA_*` env vars, and the macOS `bundle_identifier=com.manomatika.matika` all stay lowercase and are NOT renamed. The installed PRODUCT identity is supplied at build time by the recipe — matika's own code never hardcodes `ManoMatika` as a bundle name.

### Core Layers

| Layer | Path | Role |
|---|---|---|
| Plugin engine | `src/matika/core/applug_service.py` | Discovers, loads, and registers AppLugs; builds role menu cache at startup |
| Menu loader | `src/matika/core/menu_loader.py` | `MenuLoaderService` — discovers and parses all `*_menus.json` files |
| Auth | `src/matika/auth/` | bcrypt, JWT, OAuth; `dependencies.py` provides `login_required`, `validate_csrf` |
| Database | `src/matika/database.py`, `models.py` | SQLAlchemy ORM; SQLite (dev) or PostgreSQL/MySQL (prod) |
| Migrations | `migrations/` | Alembic versioned migrations for core schema only |
| RBAC | `src/matika/security/service.py` | Role → Permission checks on every request; composite indexes on `permissions` |
| Rate limiter | `src/matika/core/rate_limiter.py` | In-process login limiter (10 failures / 5 min → 15-min lockout) |
| Routers | `src/matika/routers/` | `public.py` (login/register/home), `settings.py`, `admin.py` |
| Templates | `src/matika/templates/` | Jinja2; `maintenance_activity_base.html` is the standard two-panel admin layout |
| i18n | `src/matika/i18n.py` | Core locale + per-plugin override merging |
| Frontend | `src/frontend/` | Vanilla TypeScript → JS; `csrf.ts` shared helper |

---

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
Standalone `.dmg`/`.exe` built with PyInstaller from `matika.spec` + `launcher.py`. Bundles the framework **and** its plugins; no Python environment required. matika ships **no installer of its own** — the single hosted installer is built by the **ahimsa** engine (`build.yml`) at the recipe-pinned tags and attached to the `manomatika/manomatika` product release. The freeze's runtime contract is detailed in *Frozen App* below.

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

---

### Menu Loading Pipeline

Menu data flows through two distinct phases:

#### Phase 1 — File loading (`MenuLoaderService`)

`MenuLoaderService` (`core/menu_loader.py`) scans two locations:

| Source | Path | Key |
|---|---|---|
| Core menus | `src/matika/menus/` | `"core"` |
| Plugin menus | `plugins/<id>/<id>_menus.json` | `"<plugin_id>"` |

All menus are loaded via the unified `load_menus()` method, which reads `*_menus.json` files from both the core directory and plugin directories. The core directory may contain multiple `*_menus.json` files — their `menus` objects are merged into a single `"core"` result entry. The service caches results after the first call; call `invalidate_cache()` to reset. Schema version `"1.0"` is enforced — files with other versions are skipped with a warning.

#### Phase 2 — Context building (`AppLugService.get_menus_for_context`)

Called per-request. Applies server-side role filtering and pre-translates labels before sending to the template:

1. Filter menus by `roles` field (menus whose entire item set is filtered away are hidden entirely)
2. Translate `label_key` → display label using the `t` dict
3. Build the **selector** structure (discriminated union: `item | separator | header`)
4. Build **hubs** for each selector entry

Selector ordering is fixed: `Default → (sep) → Favorites → (sep) → [Applications header] → plugins → (sep) → [Roles header] → roles`.

Hub ordering within each entry: plugin menus first → core non-System menus → core System (Help) menus last.

**Role hubs** are built from the `roles` sections of `*_menus.json` files. Core contributes role entries from `admin_menus.json`; plugins contribute from their own `*_menus.json`. `_build_role_menus` is removed — role menus are static file-driven, not generated from the permissions database.

**Admin dropdown** aggregates System menus and AppLug-contributed items. When two or more sources contribute items, `SectionHeader` items are injected to separate them. A single source never shows section headers.

**`fresh_login` session flag** is set on login and cleared after the first page load. While set, the Default hub is always shown regardless of the user's saved preference — ensuring a consistent landing state after login.

#### `*_menus.json` schema v1.0

```json
{
  "schema_version": "1.0",
  "menus": {
    "application": {
      "id": "unique-id",
      "label_key": "i18n_key",
      "items": [
        { "type": "Link",      "label_key": "k", "href": "/path", "open_new_tab": false },
        { "type": "Menu",      "label_key": "k", "items": [ ... ] },
        { "type": "Separator" }
      ]
    },
    "roles": [
      {
        "role": "Admin",
        "id": "unique-role-id",
        "label_key": "i18n_key",
        "items": [
          { "type": "Link", "label_key": "k", "href": "/path" }
        ]
      },
      {
        "role": "User",
        "id": "unique-role-id",
        "label_key": "i18n_key",
        "items": [
          { "type": "Menu", "label_key": "section", "items": [
            { "type": "Link", "label_key": "k", "href": "/path" }
          ]}
        ]
      }
    ],
    "system": {
      "id": "unique-id",
      "label_key": "i18n_key",
      "items": [
        { "type": "Link", "label_key": "k", "href": "/path" }
      ]
    }
  }
}
```

All three sections (`application`, `roles`, `system`) are optional — a source may provide any combination.

| Section | Shape | Purpose |
|---|---|---|
| `application` | single dict | App-wide menu visible to all authenticated users |
| `roles` | array of role entries | Per-role menus; each entry has a `role` field |
| `system` | single dict | Framework-level menu rendered last in every hub (e.g. Help) |

`MenuType.DEFAULT` is a **selector entry type**, not a menu type. Default is an aggregated view assembled at runtime.

Core menus (`src/matika/menus/`) use the same schema: `admin_menus.json` provides the `roles` section (Admin role entry); `help_menus.json` provides the `system` section (Help menu). System-type menus always render last in every hub.

#### `menus_data` JSON injected into every page

```html
<script type="application/json" id="matika-menus">
  { "selector": [...], "hubs": { "__default__": [...], "eyerate": [...], ... } }
</script>
<meta name="user-id" content="{{ user.id }}">
<meta name="user-default-menu" content="{{ user_default_menu }}">
```

TypeScript reads these on `DOMContentLoaded`. Hub selection is persisted in `sessionStorage` under a per-user key (`matika_active_hub_<user_id>`) so navigating between pages preserves the selection.

**Default menu preference** is stored in `user_settings` (name=`"default_menu"`, value=hub_id). Priority on page load: `sessionStorage` → user saved preference → system Default.

---

### Deployment Use Cases

| Use Case | Audience | Plugin injection | Auth |
|---|---|---|---|
| Development | Plugin/framework developers | `dev_setup.py` symlinks via `plugins.dev.json` | Local `.env` |
| Server deployment | Technical operators | `MATIKA_PLUGINS_DIR` or `plugins/` clones | Server `.env` / secrets manager |
| End-user installer | Non-technical users | Bundled by vendor at build time | First-login password change |

See `docs/DEPLOYMENT.md` for the full operator guide and `docs/INSTALL.md` for end-user and developer installation steps.

---

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

---

### Key Runtime Patterns

- **Global auth dependency:** `inject_user_to_state` populates `request.state.user` on every request. Roles and settings are eager-loaded via `subqueryload`.
- **CSRF:** Session-based token generated in context processor. `validate_csrf` FastAPI dependency on all authenticated POST routes. JavaScript (`csrf.ts`) auto-injects token on form `submit` events; TypeScript files that call `form.submit()` programmatically must call `injectCsrfToken(form)` explicitly.
- **Session middleware:** `SessionMiddleware` issues cookies (cleared on browser close); 30-day absolute cap even for `is_persistent` (remember-me) sessions.
- **Security headers:** `SecurityHeadersMiddleware` adds `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`.
- **SECRET_KEY:** Hard-required — app refuses to start without it. Never has a default fallback.
- **`MATIKA_PLUGINS_DIR`:** Read in `AppLugService.__init__()`. Overrides `ROOT_DIR/plugins` at runtime. Tests set it to a pytest-managed temp dir via `conftest.py`; the project's `plugins/` directory is never touched during test runs.

---

### Persistence Layer

- **ORM:** Pure SQLAlchemy (zero raw SQL). Switching databases = change `DATABASE_URL`. No code changes required.
- **SQLite** (default): zero-config, single-user, ideal for dev and desktop installs.
- **PostgreSQL/MySQL:** set `DATABASE_URL`; connection pool (`pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`) activates automatically for non-SQLite engines.
- **Migrations:** Alembic in `migrations/`. Core schema only — plugin tables are plugin-managed via `on_load()` → `create_all()`. In **dev**, run `alembic upgrade head` after pulling changes that touch `models.py`. In the **frozen app**, first-run schema init is in-process `create_all()` + `alembic stamp head` (see *Frozen App*), never `upgrade` and never a subprocess.
- **Performance:** `permissions` table has 5 indexes including composites on `(page_path, role_id)` and `(page_path, user_id)` — critical since this table is queried on every authenticated request.
- **N+1 prevention:** List-view routes use `selectinload()` for relationships. Export routes use `selectinload(Role.permissions)` to avoid per-role lazy queries.

---

### Security Model

- All admin POST routes have `check_page_permission` + `validate_csrf` dependencies.
- `check_page_permission` walks up the URL path hierarchy to find a matching permission (e.g. `/admin/roles/create` → checks `/admin/roles` → `/admin`).
- Server-side role filtering in `get_menus_for_context`: admin URLs are **never sent** to non-admin users in the `menus_data` JSON payload.
- Login rate limiting: 10 failures per IP in a 5-min window → 15-min lockout. Bypassed during `IS_TESTING`.
- File uploads: 5 MB cap on photos (magic-byte verified against JPEG/PNG/GIF/WebP); 10 MB cap on JSON imports.
- `CSRF` validation is bypassed when `IS_TESTING` (PYTEST_VERSION env var set). Tests do not need to include CSRF tokens in POST data.

---

### Testing

`tests/conftest.py` wires up a session-scoped test database (`data/test_matika.db`) using `MATIKA_PLUGINS_DIR` to point at a pytest-managed temp dir. The mock plugin in `tests/plugins/mock_plugin/` is copied there at session start — the real `plugins/` directory is never touched. Tests use `TestClient` (no async runner). `SECRET_KEY` is set in `conftest.py` before any app import.

---

## Release Pipeline

- `VERSION` is the single source of truth for version metadata. Never hand-edit version literals in any other file (`pyproject.toml`, `package.json`, etc.) — the release tooling propagates from `VERSION`.
- The version **CORE** (`X.Y.Z`, everything before the first `-`) is the canonical identity for ALL comparison, artifact/bundle naming, and OS/installer/Info.plist version fields. The pre-release **SUFFIX** (`-dev`, `-rc.N`) lives only on human/audit surfaces: the `VERSION` file string, git tags, GitHub release titles/bodies, the audit log. The ladder is `X.Y.Z-dev < X.Y.Z-rc.N < X.Y.Z` (final).
- During development, `VERSION` carries a pre-release suffix (e.g. `0.0.4-dev`). Propagated files (`pyproject.toml`, `package.json`) and all OS/installer/bundle fields always carry the bare core (e.g. `0.0.4`) — the suffix is a marker on `VERSION`, tags, and release titles only.
- **Canonical SemVer parser.** There is exactly ONE strict SemVer 2.0.0 parser for the product: `_parse_semver` (with `version_core()` and `is_prerelease()` built on it). Its single source of truth is `src/matika/core/paths.py`. Because the build/release tooling cannot import the installed package, that parser is mirrored **verbatim** in `scripts/sync_version.py` and `matika.spec` — any change to the canonical copy MUST be applied to both mirrors to keep all three in lockstep. The parser is **fail-loud**: invalid SemVer raises `ValueError` naming the offending value; there is no silent fallback. `get_matika_version()` (in `paths.py`) reads the running version from the `VERSION` file and raises a `RuntimeError` carrying the absolute path on a missing/unreadable file — there is NO `"unknown"` sentinel, so a missing `VERSION` surfaces at its real source rather than as a downstream "invalid SemVer" error.
- `scripts/release.py <version>` is the release entry point: accepts a bare-core final (`v0.0.4`) or a pre-release candidate (`v0.0.4-rc.1`), verifies `VERSION` currently shares the target's core under a pre-release suffix, writes the target, runs `sync_version.py` (propagating the bare core), runs the drift pre-flight check, commits. Does **not** push, tag, or create a GitHub release — those steps are manual, after human review.
- `scripts/sync_version.py` propagates `VERSION` into the allowlist of version-bearing files (currently `pyproject.toml` and `package.json`). When adding a new file with a version literal, add it to the script's allowlist.
- `scripts/sync_version.py --check` runs in read-only drift detection mode. Exits 0 (clean), 1 (drift), 2 (configuration error). `--check --json` produces structured output: `{"version": "...", "drift": [{"path": "...", "expected": "...", "found": "..."}]}`. An empty `drift` array (`[]`) means clean.
- Drift output uses double quotes around values, not single quotes (e.g. `DRIFT  pyproject.toml: expected "0.0.4", found "0.0.3"`).
- matika's `VERSION` is the source of truth for downstream applugs declaring `matika_version`. EyeRate resolves matika's `VERSION` via sibling clone at `../matika` or the `MATIKA_VERSION` env var; if neither is available, eyerate's `sync_version.py` exits 2 (hard error, not a warning).
- Drift tests live under `tests/` — no `tests/scripts/` split needed because matika's top-level `conftest.py` doesn't have heavyweight autouse fixtures.

### Release log & release notes (central log owned by `manomatika/manomatika`)

**matika has no `RELEASES.md` of its own** — it was deleted (manomatika/matika#58). The canonical, ecosystem-wide release log is a *generated* `RELEASES.md`, rendered from `release-log.yaml` (the human-edited source of truth) with `## <repo> <tag>` headings covering all three component repos. That audit log is owned by **manomatika/manomatika** — `release-log.yaml` and `RELEASES.md` live there, rendered by the engine in ahimsa. matika's historical tag entries (`v0.0.1`–`v0.0.4-dev.2`, including the `superseded` breadcrumb for `v0.0.4-dev.0` and the direct-commit `@23de78d` PRs ref) are records in that `release-log.yaml`.

- **To record/adjust a matika tag's log entry:** edit `release-log.yaml` in `manomatika/manomatika` (records keyed `repo: matika`), then regenerate `RELEASES.md` (see ahimsa's CLAUDE.md "Release-Notes System & Central Release Log"). Do NOT recreate a `RELEASES.md` in matika.
- **Status vocabulary, failed-then-superseded rule, breadcrumb rule, tagging discipline** (tag the merge commit, never a pre-merge commit) are unchanged — they apply to the central log wherever it is hosted.
- **Per-tag documentation update.** Every tag — release candidate AND final — updates matika's in-repo docs (this `CLAUDE.md` header/claims and `CHANGELOG.md`) plus the central audit log (`release-log.yaml` → generated `RELEASES.md` in `manomatika/manomatika`). matika keeps no `RELEASES.md` of its own; the central generated `RELEASES.md` is the cross-repo audit surface.

**matika release notes (notes-only).** matika has a tag-triggered release job (`.github/workflows/release.yml`, triggers on `v*.*.*` / `v*.*.*-*`, `contents: write`) that creates a GitHub Release from `docs/release-notes/<tag>.md`, with a minimal fallback body if no per-tag file exists. A tag carrying a suffix (`v*-*`, e.g. `v0.0.4-rc.1` or `v0.0.4-dev.0`) is created with `--prerelease`; a bare-core tag (`v0.0.4`) is a full release. matika ships **no installer artifacts of its own**; the single hosted installer lives on the **manomatika/manomatika** product release (built by ahimsa's `build.yml`), and matika's notes link to it. Author `docs/release-notes/<tag>.md` in the same PR that finalizes the version.

### npm Package Publishing

Matika's frontend is published to GitHub Packages as `@manomatika/matika-frontend`. Triggered automatically by tag pushes via `.github/workflows/publish-npm.yml`:

- **Final releases only.** Pushing a bare-core final tag `v0.0.4` publishes `@manomatika/matika-frontend@0.0.4`.
- **Pre-release tags publish nothing.** Pushing `v0.0.4-rc.1` or `v0.0.4-dev.0` does NOT write to the registry — an npm publish is an irreversible write to GitHub Packages, and an rc's only deliverable is the QA build, not an npm package.

Enforcement is belt-and-suspenders. The trigger glob is `v*.*.*`, but a tag glob cannot express "no hyphen" (`*` spans `-`), so the glob alone still matches `v0.0.4-rc.1`/`v0.0.4-dev.0`. The real gate is the workflow's `gate` job: it publishes only when the tag matches `^v[0-9]+\.[0-9]+\.[0-9]+$` (bare core, no pre-release suffix, no `+build` metadata). For any other tag the `publish` job is skipped, so `npm publish` is structurally unreachable for rc/dev/build-metadata tags. The publish job reads the version from the git tag (not from VERSION or package.json), runs `npm run build`, and publishes using `GITHUB_TOKEN` with `packages: write` permission.

**`package.json` version is a placeholder (`"0.0.0"`).** Never edit it manually — the workflow overrides it from the tag at publish time. `VERSION` (the Python release source of truth) and the npm tag are separate concerns: push a Python release tag to trigger both the PyPI/GitHub release flow and the npm publish.

**Public API — `src/frontend/index.ts`** is the package entry point. Only symbols re-exported from `index.ts` are part of the public surface:

| Export | Source | Purpose |
|---|---|---|
| `MaintenanceActivityManager` | `maintenance_activity.ts` | Base class for applug admin maintenance pages (browse + edit panel). Extend and override `getCreateUrl`, `getUpdateUrl`, `getDeleteUrl`. |
| `ActivityMetadata` | `maintenance_activity.ts` | Type for the metadata object passed to `MaintenanceActivityManager`'s constructor. Describes browse columns and maintenance panel fields. |
| `getCsrfToken()` | `csrf.ts` | Reads the CSRF token from the page's `<meta name="csrf-token">` tag. Use when constructing fetch() calls to matika endpoints. |
| `injectCsrfToken(form)` | `csrf.ts` | Inserts a hidden `csrf_token` input into a form. Call this before any programmatic `form.submit()` — matika validates the token on every authenticated POST. Not needed for JSON-body fetch() calls. |

Adding to or breaking the public API is a release-impacting change that requires a version bump.

**To consume from an applug repo:**
```bash
# Configure npm scope (once per machine or in .npmrc):
echo "@manomatika:registry=https://npm.pkg.github.com" >> ~/.npmrc
# Authenticate with a GitHub PAT (read:packages scope) or GITHUB_TOKEN in CI:
echo "//npm.pkg.github.com/:_authToken=<TOKEN>" >> ~/.npmrc

npm install @manomatika/matika-frontend
```

Then in TypeScript:
```typescript
import { MaintenanceActivityManager, ActivityMetadata } from '@manomatika/matika-frontend';
```

---

### Standing Rules

General working discipline (tests, git, security checks, cross-repo refs, etc.) lives in the *Working Style & Discipline* section at the top of this file. The bullets below are matika-specific.

- Always add unit tests for new functionality; update existing tests for changed behaviour.
- Never hardcode `SECRET_KEY` — read from environment only.
- Never modify the production DB during testing.
- EyeRate-specific dependencies (`yfinance`, `curl_cffi`) belong in `eyerate/requirements.txt`, not in Matika's `requirements.txt`.
- AppLug version compatibility is decided on the bare version core only (suffix stripped from both sides); there is no `MATIKA_ENV` escape hatch.
- Standard Python `.gitignore` (GitHub's official Python template) is in place: covers `__pycache__/`, build/dist, `*.egg-info/`, `.pytest_cache/`, `.coverage`, `htmlcov/`, venv variants, `.tox/`, and OS/IDE noise. Never commit compiled artifacts.
