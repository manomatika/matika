**Matika** | Version: **v0.0.4** | Copyright (c) 2026 Patrick James Tallman

# Changelog

All notable changes to Matika are documented here.

---

## [0.0.4-rc.1] — 2026-06-17

First release candidate for v0.0.4, part of the **ManoMatika v0.0.1** product
cut. Published as a GitHub prerelease for QA validation. Version core `0.0.4`;
`-rc.1` is a pre-release marker only.

### Added
- Release pipeline: `VERSION` as the single source of truth; `scripts/release.py`;
  `scripts/sync_version.py` with read-only `--check` drift detection and `--json`
  output.
- Strict canonical SemVer 2.0.0 parser (`_parse_semver` / `version_core` /
  `is_prerelease`) in `core/paths.py`, mirrored verbatim in `sync_version.py` and
  `matika.spec`; fail-loud. Establishes the core/suffix contract and the
  `X.Y.Z-dev < X.Y.Z-rc.N < X.Y.Z` ladder.
- `@manomatika/matika-frontend` npm package on GitHub Packages, with a runtime
  import map and a `publish-npm.yml` workflow gated to final bare-SemVer tags
  only (rc/dev tags never publish).
- Tag-triggered notes-only GitHub Release job (`release.yml`) sourcing its body
  from `docs/release-notes/<tag>.md`; pre-release tags flagged `--prerelease`.
- PyInstaller packaging via `matika.spec` + `launcher.py`.
- Husky pre-commit hook + CI staleness check for compiled TypeScript assets.

### Changed
- Unified core menu files onto the consolidated `*_menus.json` schema (v1.0).
- Framework-agnostic `option_sources` dispatch in `maintenance_activity_base.html`.
- Lowercased the `~/matika` app-data directory and `matika.log` filenames.
- Bumped `actions/checkout` and `actions/setup-node` to v6.
- Removed matika's own `RELEASES.md`; the ecosystem audit log now lives in
  `manomatika/manomatika`.
- Refreshed CLAUDE.md and docs for the 3-repo ManoMatika product architecture and
  the version ladder.

### Fixed
- Attach `csrf_token` in `MaintenanceActivityManager` fetch POSTs.
- Create the test-DB parent directory before SQLite connects.
- Skip non-`YYYYMMDD` log filenames silently in `cleanup_logs`.
- Isolate version-check tests from shell state.
- Lowercase GitHub slug references (`manomatika/matika`, `manomatika/eyerate`).

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
