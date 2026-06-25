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

#### Marker-match semantics

`markers` uses **ANY-PRESENT** semantics by default: the screen check passes if
at least one declared marker is found in the rendered page. This is intentional —
some markers are layout-conditional.

To require that specific markers are ALL present, add an optional
`required_markers` list — a subset of `markers`:

```json
{
  "screen_id": "eyerate:admin",
  "markers": ["#eyerate-admin-form", ".admin-provider-section"],
  "required_markers": ["#eyerate-admin-form"],
  ...
}
```

`required_markers` must be a (possibly empty) subset of `markers`. Any selector
listed there MUST be present for the screen check to pass. Omitting
`required_markers` (the default) leaves all markers under ANY-PRESENT semantics.

#### `src/matika/screens/matika_screens.json`

Framework-owned core screen definitions. Covers the standard matika routes (`/`, `/about`, `/login`, `/register`, `/settings`, `/admin`, etc.). Plugins contribute their own `*_screens.json` alongside their plugin directory (e.g. `eyerate_screens.json` in the eyerate plugin directory).

#### `[ROUTES:...]` startup log marker

After `AppLugService.discover()` loads plugins, `init_plugins()` (main.py) calls `_collect_screen_routes()` and emits:

```
[ROUTES: /about, /admin, /admin/..., /eyerate/admin, /eyerate/securities, ...]
```

`_collect_screen_routes()` is the non-screen pre-filter: it iterates all registered FastAPI routes and includes only `APIRoute` GET routes, excluding `Mount` routes (like `/static`), paths in `_NON_SCREEN_PATHS` (`/openapi.json`, `/docs`, `/redoc`), and paths ending in `.json`. The logged list is the sorted set of candidate user-facing routes.

### Layer 3 – Applug functional tests

Layer-3 functional tests let an applug declare behaviors that the generic
product gate can invoke against the frozen, booted product — without the gate
naming any applug.

#### Contract constants (canonical in `src/matika/core/functional_test_contract.py`)

| Constant | Value | Purpose |
|---|---|---|
| `FUNCTIONAL_TEST_SCHEMA` | `"1.0"` | JSON manifest schema version |
| `FUNCTIONAL_TESTS_SUFFIX` | `"_functional_tests.json"` | Discovery file suffix |

#### `<applug>_functional_tests.json` schema

```json
{
  "schema_version": "1.0",
  "functional_tests": [
    {
      "test_id": "<applug>:<test_name>",
      "description": "Human-readable description of what is verified",
      "module": "<applug>_functional_tests",
      "function": "test_<name>",
      "tags": ["network"]
    }
  ]
}
```

Required fields: `test_id`, `description`, `module`, `function`. `tags` is optional.

#### `<applug>_functional_tests.py` — Python implementation

```python
def test_<name>(base_url: str, session) -> None:
    """Assertion raises AssertionError on failure."""
    resp = session.get(f"{base_url}/some/route")
    assert resp.status_code == 200
```

- `base_url`: the frozen product's base URL (e.g. `http://127.0.0.1:PORT`)
- `session`: a `requests.Session` pre-authenticated as the QA admin user
- Raise `AssertionError` (or let a failing `assert` propagate) on failure
- Standard library + `requests` only; no product-runtime imports

#### Discovery and invocation (gate side — ahimsa)

1. Walk source clone for `*_functional_tests.json` (same discovery pattern as `*_screens.json`)
2. Parse each JSON; enumerate `test_id` / `module` / `function` declarations
3. Import `module` from the source clone using `importlib`
4. Call `function(base_url=product_url, session=auth_session)`
5. Any `AssertionError` → gate fails with non-zero exit

The gate runs ONLY declared tests (those listed in the JSON manifest). Test
functions present in the `.py` file but not declared in the JSON are NOT
invoked — the JSON is the authoritative contract.
