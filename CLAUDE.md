**Matika** | Version: **v0.0.4** | Copyright (c) 2026 Patrick James Tallman

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working Style & Discipline

This section captures the standing working rules across the manomatika ecosystem. **CLAUDE.md is authoritative for how a fresh Claude Code instance should operate in this repo; keep it current as practices evolve.** The terminal milestone of every release is `Documentation & Release Readiness`, which includes auditing and updating every CLAUDE.md against what actually shipped.

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
- **cc does not run `git merge` locally; never run `rm -rf`.** Integration of branches is done by the user via PR merge in the browser. For any local branch updates cc performs, use `git rebase` or `git cherry-pick`. Use targeted `git rm` if files must be removed.
- **`VERSION` is the single source of truth** for version metadata in this repo. Never hand-edit version literals in other files; release tooling propagates from `VERSION`.
- **The user uses git worktrees** for parallel work (e.g. `~/dev/projects/matika-45/` alongside `~/dev/projects/matika/` on a separate branch). At any moment, the user may be operating in any of several working directories for the same repo. Always check the current branch (`git branch --show-current`) and confirm it matches what you expect before assuming.
- **Multi-instance/parallel discipline.** When operating as one of multiple parallel cc instances, stay strictly within the assigned worktree, branch, and scope of files described in the task. Do not modify files outside the assigned scope, even if issues are noticed elsewhere — surface those issues to the user as separate items to triage rather than fixing in-flight. Cross-cutting changes that touch another agent's work area must be coordinated by the user, not initiated unilaterally.

### Code and test discipline

- **Regression tests are required for every fix.** A bug fix that doesn't include a test that would have caught the bug isn't done.
- **All tests must pass — 0 failed, 0 skipped, 0 xfail.** No exceptions without explicit user approval. In multi-repo changes, every affected repo's full suite must pass before any PR is opened.
- **Never weaken or disable security / correctness checks** (CSRF, permission, auth, validation) as a workaround. If a check is producing a wrong answer, fix the call site to satisfy it correctly — never bypass.

### Repository ecosystem

- **manomatika** is the GitHub org. Three repos compose the ecosystem:
  - **manomatika/Matika** — the framework (plugin-agnostic FastAPI host)
  - **manomatika/EyeRate** — the reference AppLug (financial security tracking)
  - **manomatika/ahimsa** — release / build / recipe-validation tooling
- Local clones live at `~/dev/projects/<repo>/` (sibling directories). Additional worktrees for the same repo live at `~/dev/projects/<repo>-<branch>/`.

### Milestones, Project, and dates

- **Milestone naming is shared and match-when-present** across repos. When a milestone exists in more than one repo, its title is byte-for-byte identical so the org Project rolls it up into a single cross-repo group. Milestone names never contain version numbers or dates.
- **Canonical milestone titles in the current release cycle:**
  - `Deployment & Install`
  - `Cleanup & Tooling`
  - `Registry` (ahimsa only)
  - `Signing & Distribution` (ahimsa only)
  - `QA & System Test` (ahimsa only)
  - `v0.0.5 Planning` (eyerate + ahimsa)
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

`MATIKA_ENV=development` — set this in your local `.env` to allow AppLugs that declare
a released `matika_version` (e.g. `X.Y.Z`) to load when Matika is running at a `_dev`
version (e.g. `X.Y.Z_dev`). This relaxes only the version check — no other validation
changes. Never set this in production. Never commit `.env`.

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
- `export $(cat .env | grep -v '^#' | xargs)` — loads `SECRET_KEY` and `MATIKA_ENV` from `.env` into the shell (`grep -v '^#'` strips comment lines)
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

#### 3. End-user installer (future)
Standalone `.dmg`/`.exe` built with PyInstaller. Bundles the framework + selected plugins. No Python environment required.

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

Plugin menus are loaded via `load_applug_menus()`, which reads `*_menus.json` files (consolidated format). Core menus continue to use individual `*_menu.json` files. The service caches results after the first call (`load_all()` is lazy-cached; call `invalidate_cache()` to reset). Schema version `"1.0"` is enforced — files with other versions are skipped with a warning.

#### Phase 2 — Context building (`AppLugService.get_menus_for_context`)

Called per-request. Applies server-side role filtering and pre-translates labels before sending to the template:

1. Filter menus by `roles` field (menus whose entire item set is filtered away are hidden entirely)
2. Translate `label_key` → display label using the `t` dict
3. Build the **selector** structure (discriminated union: `item | separator | header`)
4. Build **hubs** for each selector entry

Selector ordering is fixed: `Default → (sep) → Favorites → (sep) → [Applications header] → plugins → (sep) → [Roles header] → roles`.

Hub ordering within each entry: plugin menus first → core non-System menus → core System (Help) menus last.

**Role hubs** are built from the `roles` sections of `*_menus.json` files plus core Role-type menus (e.g. `admin_menu.json`). `_build_role_menus` is removed — role menus are static file-driven, not generated from the permissions database.

**Admin dropdown** aggregates System menus and AppLug-contributed items. When two or more sources contribute items, `SectionHeader` items are injected to separate them. A single source never shows section headers.

**`fresh_login` session flag** is set on login and cleared after the first page load. While set, the Default hub is always shown regardless of the user's saved preference — ensuring a consistent landing state after login.

#### `*_menus.json` schema v1.0 (plugin consolidated format)

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
    ]
  }
}
```

Both `application` and `roles` are optional — a plugin may provide one, both, or neither.

`MenuType.DEFAULT` is a **selector entry type**, not a menu type. Default is an aggregated view assembled at runtime.

Core menus (`src/matika/menus/`) continue to use individual `*_menu.json` files with the `menus` array format. Core menus: `admin_menu.json` (type `Role`) and `help_menu.json` (type `System`). System-type menus always render last in every hub.

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
- **Migrations:** Alembic in `migrations/`. Core schema only — plugin tables are plugin-managed via `on_load()` → `create_all()`. Always run `alembic upgrade head` after pulling changes that touch `models.py`.
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
- During development, `VERSION` carries a `_dev` suffix (e.g. `0.0.4_dev`). Propagated files always carry the stripped version (e.g. `0.0.4`) — `_dev` is a marker on `VERSION` only.
- `scripts/release.py <version>` is the release entry point: verifies `VERSION` currently reads `<target>_dev`, strips `_dev`, runs `sync_version.py`, runs the drift pre-flight check, commits. Does **not** push, tag, or create a GitHub release — those steps are manual, after human review.
- `scripts/sync_version.py` propagates `VERSION` into the allowlist of version-bearing files (currently `pyproject.toml` and `package.json`). When adding a new file with a version literal, add it to the script's allowlist.
- `scripts/sync_version.py --check` runs in read-only drift detection mode. Exits 0 (clean), 1 (drift), 2 (configuration error). `--check --json` produces structured output: `{"version": "...", "drift": [{"path": "...", "expected": "...", "found": "..."}]}`. An empty `drift` array (`[]`) means clean.
- Drift output uses double quotes around values, not single quotes (e.g. `DRIFT  pyproject.toml: expected "0.0.4", found "0.0.3"`).
- matika's `VERSION` is the source of truth for downstream applugs declaring `matika_version`. EyeRate resolves matika's `VERSION` via sibling clone at `../matika` or the `MATIKA_VERSION` env var; if neither is available, eyerate's `sync_version.py` exits 2 (hard error, not a warning).
- Drift tests live under `tests/` — no `tests/scripts/` split needed because matika's top-level `conftest.py` doesn't have heavyweight autouse fixtures.

### RELEASES.md Convention

`RELEASES.md` at repo root is the canonical log of every git tag pushed from this repository. The tag↔entry consistency rule is enforced by ahimsa's release-log validation:

- Every git tag matching `vX.Y.Z` or `vX.Y.Z-PRERELEASE` MUST have an entry in `RELEASES.md`.
- Every entry in `RELEASES.md` MUST correspond to an actual git tag — no orphan entries.

**Entry format.** Each entry is an H2 heading whose exact text is the tag name (e.g. `## v0.0.4-dev.1`), followed by required fields: `Date` (ISO `YYYY-MM-DD`), `Status`, `Artifact`, `PRs`, `Summary`. Entries are listed newest-first. Cross-repo references inside `PRs` must be fully qualified — see "PRs field formats" below.

**PRs field formats.** The `PRs` field accepts either of two reference forms:
- **PR-style** (`manomatika/<repo>#N`) — the normal case. Example: `manomatika/matika#35` (used in `v0.0.4-dev.0`'s entry).
- **Direct-commit** (`manomatika/<repo>@<sha>`) — legacy / emergency only, used when a tag-bearing commit landed without going through PR review. Example: `manomatika/matika@23de78d` (used in `v0.0.4-dev.1`'s entry — a direct-to-main lockfile fix).

The convention going forward is PR-required: every tagged commit lands via PR. The direct-commit format remains valid for honestly recording historical exceptions, not as an ongoing escape hatch. Both formats validate cleanly under ahimsa's release-log validator (which checks tag↔entry presence only and does not parse the `PRs` field).

**Status vocabulary.** `published` | `failed` | `superseded`. This is the closed initial vocabulary — do not invent new keywords without updating both this convention and ahimsa's validator in lockstep.

**Failed-then-superseded rule.** When a tag is both failed AND later superseded, its `Status` is `superseded (by <successor-tag>)`, not `failed`. `Status` reflects current state; the original failure reason moves into the `Summary` as historical context. This avoids re-litigating each failed tag's status as the release log evolves.

**Failed-tag breadcrumb rule.** Failed-publish tags are NEVER deleted from the repository. They remain as audit breadcrumbs. Their `RELEASES.md` entries persist even after supersession, with `Status` updated per the rule above.

**Tagging discipline.**
- Tags are pushed to the `main` branch HEAD after the entry-bearing PR has merged. The merge commit is what gets tagged.
- Never tag a feature branch commit. Never tag before merge.
- The convention "the entry must be present on the tagged commit" depends on this discipline — tagging a pre-merge commit would leave the tag pointing at a commit that does not contain its own `RELEASES.md` entry.

**When the entry is added.**
- For full releases (e.g. `v0.0.4`): the entry is added in the same commit that bumps `VERSION` from `<target>_dev` to `<target>` (i.e. the release-finalization commit produced by `scripts/release.py`).
- For prereleases (e.g. `v0.0.4-dev.2`): `VERSION` is unchanged (prereleases are tag-only). The entry is added in the same commit that introduces the change being prereleased. The entry must be present on the commit that ends up tagged.

**Historical-backfill exception.** Tags pushed before this convention was established (`v0.0.1`, `v0.0.2`, `v0.0.3`) carry minimal placeholder entries — `Status: published`, no `Artifact`, no `PRs` ref, identical Summary noting the pre-convention nature. This is informational, not a relaxation of the schema: every entry from `v0.0.4-dev.0` onward follows the full schema density, and future entries must too.

### npm Package Publishing

Matika's frontend is published to GitHub Packages as `@manomatika/matika-frontend`. Triggered automatically by tag pushes via `.github/workflows/publish-npm.yml`:

- **Real releases:** pushing tag `v0.0.4` publishes `@manomatika/matika-frontend@0.0.4`.
- **Prereleases:** pushing tag `v0.0.4-dev.0` publishes `@manomatika/matika-frontend@0.0.4-dev.0`. Used to let applugs integrate before the main version ships.

The publish workflow reads the version from the git tag (not from VERSION or package.json), runs `npm run build`, and publishes using `GITHUB_TOKEN` with `packages: write` permission.

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
- `MATIKA_ENV=development` must never be committed — it belongs only in the local `.env`.
- Standard Python `.gitignore` (GitHub's official Python template) is in place: covers `__pycache__/`, build/dist, `*.egg-info/`, `.pytest_cache/`, `.coverage`, `htmlcov/`, venv variants, `.tox/`, and OS/IDE noise. Never commit compiled artifacts.
