> Part of [CLAUDE.md](../CLAUDE.md) — see the main file for orientation.

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
- **Migrations:** Alembic in `migrations/`. Core schema only — plugin tables are plugin-managed via `on_load()` → `create_all()`. In **dev**, run `alembic upgrade head` after pulling changes that touch `models.py`. In the **frozen app**, first-run schema init is in-process `create_all()` + `alembic stamp head` (see [docs/frozen-app.md](frozen-app.md)), never `upgrade` and never a subprocess.
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
