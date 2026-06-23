> Part of [CLAUDE.md](../CLAUDE.md) — see the main file for orientation.

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
