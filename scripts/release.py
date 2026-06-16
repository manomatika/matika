"""
release.py — prepare a matika release commit.

What it does:
  1. Verifies VERSION currently shares the target's bare core and is a
     pre-release of it (e.g. target 0.0.4 -> VERSION is 0.0.4-dev / 0.0.4-rc.N).
  2. Writes the target (bare-core final, or the explicit pre-release) to VERSION.
  3. Calls sync_version.sync() to propagate the bare core to all targets.
  4. Runs a drift check — every sync target must exactly match the released core.
  5. Commits VERSION + all sync targets.
  6. Prints next-step reminders.

What it does NOT do:
  Push, tag, create a PR, merge, or create a GitHub release.
  Do those steps manually after reviewing the commit.

Version ladder: X.Y.Z-dev < X.Y.Z-rc.N < X.Y.Z (final). Targets may carry a
pre-release suffix (e.g. v0.0.4-rc.1) to cut a release-candidate, or be bare
core (e.g. v0.0.4) for the final release.

Usage:
  python scripts/release.py v0.0.4         # final release
  python scripts/release.py 0.0.4          # final release
  python scripts/release.py v0.0.4-rc.1    # release candidate
"""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sync_version import REPO_ROOT, read_version, sync, version_core  # noqa: E402

# Accepts a bare core (X.Y.Z) optionally followed by a pre-release suffix
# (-dev, -rc.N, -<anything>). The suffix is a human/audit marker only.
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    if result.returncode != 0:
        print(f"ERROR: {' '.join(cmd)}\n{result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/release.py <version>  (e.g. v0.0.4 or 0.0.4)")
        sys.exit(1)

    target = sys.argv[1].lstrip("v")
    if not VERSION_RE.match(target):
        print(
            f"ERROR: {sys.argv[1]!r} is not a valid version "
            f"(expected X.Y.Z, X.Y.Z-rc.N, X.Y.Z-dev, optionally v-prefixed)"
        )
        sys.exit(1)

    target_core = version_core(target)

    # 1. Verify current VERSION shares the target's bare core and is a
    #    pre-release of it. We only ever release a core that we have been
    #    iterating on under a pre-release suffix.
    raw, raw_core = read_version()
    if raw_core != target_core:
        print(f"ERROR: VERSION core is {raw_core!r}, expected {target_core!r} (from VERSION {raw!r})")
        print(f"Set VERSION to a pre-release of {target_core} (e.g. {target_core}-dev) before running release.py.")
        sys.exit(1)
    if raw == target_core:
        print(f"ERROR: VERSION is already the bare-core final {raw!r} — nothing to release.")
        print(f"Set VERSION to a pre-release of {target_core} (e.g. {target_core}-dev) first.")
        sys.exit(1)

    print(f"Releasing {target}  (from {raw})")

    # 2. Write the target to VERSION (carries the suffix on a pre-release target,
    #    bare core on a final target). Propagation always uses the bare core.
    version_file = REPO_ROOT / "VERSION"
    version_file.write_text(target + "\n")
    print(f"  WROTE   VERSION ← {target!r}")

    # 3. Propagate to all targets
    sync()

    # 4. Drift check — same computation as propagation, read-only
    drifted = sync(check_only=True)
    if drifted:
        print("Drift check failed — aborting release.", file=sys.stderr)
        sys.exit(1)

    # 5. Commit
    stage_paths = ["VERSION", "pyproject.toml", "package.json"]
    existing = [p for p in stage_paths if (REPO_ROOT / p).exists()]
    _run(["git", "add"] + existing)
    _run(["git", "commit", "-m", f"chore: release {target}"])

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    print(f"\nRelease commit created on {branch!r}.")
    print("Next steps (manual, after review):")
    print(f"  git push origin {branch}")
    print(f"  gh pr create --title 'Release v{target}' ...")
    print(f"  git tag v{target} && git push origin v{target}")
    print()
    print("Don't forget to update CHANGELOG.md and any version references in docs/.")


if __name__ == "__main__":
    main()
