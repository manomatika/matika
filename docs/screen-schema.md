> Part of [CLAUDE.md](../CLAUDE.md) — see the main file for orientation.

### Screen Data Schema

The screen schema is a standardized format for describing user-facing routes and their interaction model, consumed by Playwright-based test tooling.

#### `ScreenLoaderService` (`src/matika/core/screen_loader.py`)

`ScreenLoaderService(core_screens_dir, plugins_dir)` discovers and loads `*_screens.json` files from two locations:

| Source | Path | Key |
|---|---|---|
| Core screens | `src/matika/screens/` | `"core"` |
| Plugin screens | `plugins/<id>/<id>_screens.json` | `"<plugin_id>"` |

`load_screens()` returns `{source_id: [list of screen entries]}`. Core screens are assembled by merging all `*_screens.json` files in `core_screens_dir` into a single `"core"` list. Plugin screens expect exactly one `*_screens.json` per plugin directory. Result is cached; call `invalidate_cache()` to reset.

**Fail-loud on duplicate `screen_id`.** Any `screen_id` that appears in more than one source raises `RuntimeError` at load time — startup aborts on any duplicate.

#### `*_screens.json` schema v1.0

```json
{
  "schema_version": "1.0",
  "screens": [
    {
      "screen_id": "unique-id",
      "type": "screen",
      "route": "/path",
      "markers": [".css-selector", "#element-id"],
      "steps": [
        {"verb": "navigate", "target": "/path"}
      ]
    },
    {
      "screen_id": "unique-id",
      "type": "not_a_screen",
      "route": "/path",
      "reason": "POST-only handler; no user-facing HTML"
    }
  ]
}
```

**Entry types:**

| Type | Required fields | Purpose |
|---|---|---|
| `"screen"` | `screen_id`, `markers`, `steps` | A user-facing page; `markers` are CSS selectors that identify it; `steps` are the interaction sequence |
| `"not_a_screen"` | `screen_id`, `reason` | A route explicitly excluded from screen testing (e.g. POST-only handlers) |

**Interaction verb allow-list** (`navigate` / `fill` / `click` / `wait_for` / `assert_present` / `assert_absent` / `assert_value`) — data-driven; no code changes needed to add interaction sequences. Files with `schema_version` other than `"1.0"` are skipped with a warning.

#### `src/matika/screens/matika_screens.json`

Framework-owned core screen definitions. Covers the standard matika routes (`/`, `/about`, `/login`, `/register`, `/settings`, `/admin`, etc.). Plugins contribute their own `*_screens.json` alongside their plugin directory (e.g. `eyerate_screens.json` in the eyerate plugin directory).

#### `[ROUTES:...]` startup log marker

After `AppLugService.discover()` loads plugins, `init_plugins()` (main.py) calls `_collect_screen_routes()` and emits:

```
[ROUTES: /about, /admin, /admin/..., /eyerate/admin, /eyerate/securities, ...]
```

`_collect_screen_routes()` is the non-screen pre-filter: it iterates all registered FastAPI routes and includes only `APIRoute` GET routes, excluding `Mount` routes (like `/static`), paths in `_NON_SCREEN_PATHS` (`/openapi.json`, `/docs`, `/redoc`), and paths ending in `.json`. The logged list is the sorted set of candidate user-facing routes.
