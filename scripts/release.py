"""
release.py — prepare a matika release commit.

What it does:
  1. Verifies VERSION is currently <target>_dev.
  2. Writes the clean version to VERSION.
  3. Calls sync_version.sync() to propagate to all targets.
  4. Runs a drift check — every sync target must exactly match the released version.
  5. Commits VERSION + all sync targets.
  6. Prints next-step reminders.

What it does NOT do:
  Push, tag, create a PR, merge, or create a GitHub release.
  Do those steps manually after reviewing the commit.

Usage:
  python scripts/release.py v0.0.4
  python scripts/release.py 0.0.4
"""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sync_version import REPO_ROOT, drift_check, read_version, sync  # noqa: E402

EXACT_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


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

    target_clean = sys.argv[1].lstrip("v")
    if not EXACT_VERSION_RE.match(target_clean):
        print(f"ERROR: {sys.argv[1]!r} is not a valid version (expected X.Y.Z or vX.Y.Z)")
        sys.exit(1)

    # 1. Verify current VERSION is <target>_dev
    raw, _ = read_version()
    expected_dev = f"{target_clean}_dev"
    if raw != expected_dev:
        print(f"ERROR: VERSION is {raw!r}, expected {expected_dev!r}")
        print("Set VERSION to the correct _dev value before running release.py.")
        sys.exit(1)

    print(f"Releasing {target_clean}  (from {raw})")

    # 2. Write clean version to VERSION
    version_file = REPO_ROOT / "VERSION"
    version_file.write_text(target_clean + "\n")
    print(f"  WROTE   VERSION ← {target_clean!r}")

    # 3. Propagate to all targets
    sync()

    # 4. Drift check
    drift_check(target_clean)

    # 5. Commit
    stage_paths = ["VERSION", "pyproject.toml", "package.json"]
    existing = [p for p in stage_paths if (REPO_ROOT / p).exists()]
    _run(["git", "add"] + existing)
    _run(["git", "commit", "-m", f"chore: release {target_clean}"])

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    print(f"\nRelease commit created on {branch!r}.")
    print("Next steps (manual, after review):")
    print(f"  git push origin {branch}")
    print(f"  gh pr create --title 'Release v{target_clean}' ...")
    print(f"  git tag v{target_clean} && git push origin v{target_clean}")
    print()
    print("Don't forget to update CHANGELOG.md and any version references in docs/.")


if __name__ == "__main__":
    main()
