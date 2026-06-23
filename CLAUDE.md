# CLAUDE.md — matika (plugin-agnostic FastAPI framework)

matika is the **plugin-agnostic FastAPI framework** — the core has zero knowledge of any business domain. Domain logic lives entirely in plugins called **AppLugs**. The shipped PRODUCT it composes into is **ManoMatika** (proper noun), named by the recipe's `application.product_name` (owned by `manomatika/manomatika`). User-facing runtime surfaces use `ManoMatika`; the internal repo, Python package, data dir (`~/matika/`), and env vars (`MATIKA_*`) stay lowercase `matika`. matika ships notes-only GitHub releases — no installer; the single hosted installer is built by ahimsa and attached to the `manomatika/manomatika` product release.

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
- **Cross-repo issue/PR references must always be fully qualified.** Write `manomatika/matika#N`, `manomatika/eyerate#N`, `manomatika/ahimsa#N` — never a bare `#N` for an issue that lives in a different repo. Bare refs are only safe when the PR and the issue are in the same repo. Cross-repo `Closes` references only cross-link — they do NOT auto-close; close manually after merge.
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
  - **manomatika/matika** — the framework (plugin-agnostic FastAPI host). Component; notes-only releases. **This repo.**
  - **manomatika/eyerate** — the reference AppLug (financial security tracking). Component; notes-only releases.
  - **manomatika/ahimsa** — the recipe ENGINE: build / validation / release *mechanism* + recipe *schema*. Owns no recipes, no audit-log content, and hosts no product releases of its own.
- Local clones live at `~/dev/projects/<repo>/` (sibling directories). Additional worktrees for the same repo live at `~/dev/projects/<repo>-<branch>/`.

### Milestones, Project, and dates

- **Milestone naming is shared and match-when-present** across repos. When a milestone exists in more than one repo, its title is byte-for-byte identical so the org Project rolls it up into a single cross-repo group. Milestone names never contain version numbers or dates.
- **Canonical milestone titles in the current release cycle:**
  - `Deployment & Install`
  - `Cleanup & Tooling` (matika + eyerate + ahimsa)
  - `Registry` (ahimsa only)
  - `Signing & Distribution` (ahimsa only)
  - `QA & System Test` (ahimsa only)
  - `Planning` (matika + eyerate + ahimsa)
  - `Playwright` (matika only)
  - `Documentation & Release Readiness` — the terminal release gate (all four)
- **Org-level Project: [ManoMatika Roadmap](https://github.com/orgs/manomatika/projects/1)** is the cross-repo backlog view. Its description records which component versions compose each manomatika release (e.g. ManoMatika v0.0.1 = matika v0.0.4 + eyerate v0.0.4 + ahimsa v0.0.1).
- **Milestone due dates are the single source of truth for dates.** The roadmap renders timelines from milestone Markers; do NOT create per-item date fields on the Project for scheduling (Pattern A — milestone-driven).

### Communication and output

- **Put prompts and commands in code blocks** so the user can one-tap copy them.
- The user is on **macOS** and uses **Ghostty** and **tmux** for terminal work (shell defaults to zsh). The user also runs a **Dell Latitude** (64 GB RAM, no high-performance GPU) for local models via **Ollama**, currently favoring **qwen**. All configs are managed with **chezmoi**; any change to any config must follow chezmoi best practice and standards. chezmoi usage is captured in a separate handoff file, `chezmoi-dotfiles-handoff.md`. The user edits in **neovim**, and may also use **VSC**.
- The user is **expert in software architecture and engineering, novice in git/GitHub specifics.** When git or `gh` commands appear in plans or output, explain plainly what they do, what they touch, and what the user will see.

## Commands

### Development Setup
```bash
uv sync
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
uv run pytest tests/                                        # all tests
uv run pytest tests/test_auth.py                            # one module
uv run pytest tests/test_auth.py::test_login_success        # one test
```

---

## Architecture

### Installed product identity vs. internal identity

matika is the **component repo/package**; the shipped PRODUCT it composes into is **ManoMatika** (proper noun), named by the recipe's `application.product_name` (owned by `manomatika/manomatika`). The split:

- **User-facing → `ManoMatika`.** The FastAPI runtime title is `title="ManoMatika"` (`src/matika/main.py`), and the en/es locale brand strings are ManoMatika (`src/matika/locales/{en,es}.json` — e.g. `"title": "ManoMatika - Yield Tracker"`). The frozen bundle/exe and shortcuts are `ManoMatika-<product-core>.app` / `.exe` (see [docs/frozen-app.md](docs/frozen-app.md)).
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

For Plugin Management System detail, see [docs/plugins.md](docs/plugins.md).

For Menu Loading Pipeline detail, see [docs/menu-loading.md](docs/menu-loading.md).

For Screen Data Schema detail, see [docs/screen-schema.md](docs/screen-schema.md).

### Deployment Use Cases

| Use Case | Audience | Plugin injection | Auth |
|---|---|---|---|
| Development | Plugin/framework developers | `dev_setup.py` symlinks via `plugins.dev.json` | Local `.env` |
| Server deployment | Technical operators | `MATIKA_PLUGINS_DIR` or `plugins/` clones | Server `.env` / secrets manager |
| End-user installer | Non-technical users | Bundled by vendor at build time | First-login password change |

See `docs/DEPLOYMENT.md` for the full operator guide and `docs/INSTALL.md` for end-user and developer installation steps.

For Frozen App (boot/plugin-lifecycle) detail, see [docs/frozen-app.md](docs/frozen-app.md). For Key Runtime Patterns, Persistence Layer, and Security Model, see [docs/runtime-patterns.md](docs/runtime-patterns.md).

### Testing

`tests/conftest.py` wires up a session-scoped test database (`data/test_matika.db`) using `MATIKA_PLUGINS_DIR` to point at a pytest-managed temp dir. The mock plugin in `tests/plugins/mock_plugin/` is copied there at session start — the real `plugins/` directory is never touched. Tests use `TestClient` (no async runner). `SECRET_KEY` is set in `conftest.py` before any app import.

For Release Pipeline, see [docs/release-pipeline.md](docs/release-pipeline.md). For npm Package Publishing, see [docs/npm-publishing.md](docs/npm-publishing.md).

### Standing Rules

General working discipline (tests, git, security checks, cross-repo refs, etc.) lives in the *Working Style & Discipline* section at the top of this file. The bullets below are matika-specific.

- Always add unit tests for new functionality; update existing tests for changed behaviour.
- Never hardcode `SECRET_KEY` — read from environment only.
- Never modify the production DB during testing.
- EyeRate-specific dependencies (`yfinance`, `curl_cffi`) belong in `eyerate/requirements.txt`, not in Matika's `requirements.txt`.
- AppLug version compatibility is decided on the bare version core only (suffix stripped from both sides); there is no `MATIKA_ENV` escape hatch.
- Standard Python `.gitignore` (GitHub's official Python template) is in place: covers `__pycache__/`, build/dist, `*.egg-info/`, `.pytest_cache/`, `.coverage`, `htmlcov/`, venv variants, `.tox/`, and OS/IDE noise. Never commit compiled artifacts.
