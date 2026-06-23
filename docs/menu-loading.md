> Part of [CLAUDE.md](../CLAUDE.md) — see the main file for orientation.

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
