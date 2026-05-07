# Releases

Canonical log of every git tag pushed from this repository and its
corresponding published artifact. Every tag of the form `vX.Y.Z` or
`vX.Y.Z-PRERELEASE` has an entry below. Failed-publish tags are kept
as breadcrumbs; an entry's `Status` is updated to `superseded` once a
successor tag publishes successfully (failure context moves into the
Summary).

The tag↔entry consistency rule is enforced by ahimsa's release-log
validation. Entries are listed newest-first.

---

## v0.0.4-dev.1

- **Date:** 2026-05-06
- **Status:** published
- **Artifact:** `@manomatika/matika-frontend@0.0.4-dev.1` (GitHub Packages)
- **PRs:** manomatika/matika@23de78d (direct-to-main lockfile fix; no PR opened)
- **Summary:** First successful publish of `@manomatika/matika-frontend`.
  Establishes the public TypeScript surface for applugs to consume:
  `MaintenanceActivityManager`, `ActivityMetadata`, `getCsrfToken`,
  `injectCsrfToken`. Tagged from a direct-to-main commit that committed
  the previously-missing `package-lock.json`. Future lockfile changes
  must follow standard branch + PR discipline.

## v0.0.4-dev.0

- **Date:** 2026-05-06
- **Status:** superseded (by v0.0.4-dev.1)
- **Artifact:** none (publish failed; breadcrumb only)
- **PRs:** manomatika/matika#35
- **Summary:** First attempted publish of `@manomatika/matika-frontend`.
  The publish workflow failed in `npm ci` because `package-lock.json`
  was not committed to the repository. Tag retained as audit breadcrumb;
  superseded by v0.0.4-dev.1 which committed the lockfile and republished
  successfully.
