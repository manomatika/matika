**Matika** | Version: **v0.0.4** | Copyright (c) 2026 Patrick James Tallman

# Changelog

All notable changes to Matika are documented here.

---

## [Unreleased / 0.0.4_dev]

### Added
- *(nothing yet)*

---

## [0.0.2] — 2026-04-27

### Compatibility Contract (baseline)

This release establishes the formal AppLug compatibility contract. **No breaking
changes to `BaseAppLug` or the plugin discovery contract will be made from this
version forward without a major version bump.**

#### Added
- `matika_version` required field in `applug.json`. Every AppLug must declare the
  exact Matika version it was built and tested against.
- `BaseAppLug._validate_compatibility()` — called at construction time. Raises a
  clear `RuntimeError` (and skips the plugin gracefully) when `matika_version` is
  absent or does not match the running Matika version.
- `get_matika_version()` in `core/paths.py` — reads the `VERSION` file at runtime
  so that both the framework and the validator always reference a single source of truth.
- Four new tests in `test_applug_system.py` covering: missing field, version mismatch,
  correct version, and informative error message content.
