"""
sync_version.py — propagates the canonical version from VERSION into all
version-bearing files in the matika working tree.

Propagation targets (allowlist):
  pyproject.toml  — [project] version field
  package.json    — top-level "version" field

The VERSION file may carry a _dev suffix (e.g. "0.0.4_dev"). That suffix is
stripped before propagation so all targets always hold a clean X.Y.Z string.
VERSION itself is never modified by this script.

  VERSION="0.0.4_dev"  →  pyproject.toml: version = "0.0.4"
                           package.json:   "version": "0.0.4"

Usage:
  python scripts/sync_version.py           # propagate (write files)
  python scripts/sync_version.py --check   # read-only drift check
"""

import argparse
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

# Every file this script touches. drift_check() verifies exactly these.
SYNC_TARGETS: list[tuple[str, str]] = [
    ("pyproject.toml", "pyproject.toml [project].version"),
    ("package.json",   "package.json .version"),
]


def read_version() -> tuple[str, str]:
    """Return (raw, clean): raw is the VERSION file contents; clean has _dev stripped."""
    version_file = REPO_ROOT / "VERSION"
    if not version_file.exists():
        print("ERROR: VERSION file not found", file=sys.stderr)
        sys.exit(1)
    raw = version_file.read_text().strip()
    clean = raw.removesuffix("_dev")
    return raw, clean


# ---------------------------------------------------------------------------
# Per-file computation (pure — no I/O, no branching on mode)
# ---------------------------------------------------------------------------

def _expected_pyproject(content: str, version: str) -> str:
    return re.sub(
        r'^(version\s*=\s*)"[^"]*"',
        rf'\1"{version}"',
        content,
        flags=re.MULTILINE,
    )


def _expected_package_json(content: str, version: str) -> str:
    result, n = re.subn(
        r'^(\s*"version"\s*:\s*)"[^"]*"',
        rf'\1"{version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    return result if n else content


def _extract_pyproject_version(content: str) -> str:
    m = re.search(r'^version\s*=\s*"([^"]*)"', content, re.MULTILINE)
    return m.group(1) if m else "<not found>"


def _extract_package_json_version(content: str) -> str:
    m = re.search(r'^(\s*"version"\s*:\s*)"([^"]*)"', content, re.MULTILINE)
    return m.group(2) if m else "<not found>"


# ---------------------------------------------------------------------------
# Core: propagate or check (single code path, branches only at write step)
# ---------------------------------------------------------------------------

def sync(check_only: bool = False) -> list[str]:
    """
    Propagate VERSION to all targets (check_only=False) or compare without
    writing (check_only=True).

    Returns:
      Normal mode  — list of relative paths that were written.
      Check mode   — list of relative paths that drifted.

    In check mode VERSION may carry _dev; the stripped value is what targets
    are compared against (same as propagation — no special failure for _dev).
    """
    raw, clean = read_version()
    print(
        f"sync_version {'--check: checking against' if check_only else ': ' + repr(raw) + ' → propagating'} "
        f"{clean!r}"
    )

    affected: list[str] = []

    pyproject = REPO_ROOT / "pyproject.toml"
    if pyproject.exists():
        current = pyproject.read_text()
        expected = _expected_pyproject(current, clean)
        rel = str(pyproject.relative_to(REPO_ROOT))
        if current == expected:
            print(f"  OK       {rel}")
        elif check_only:
            found = _extract_pyproject_version(current)
            print(f"DRIFT  {rel}: expected '{clean}', found '{found}'")
            affected.append(rel)
        else:
            pyproject.write_text(expected)
            print(f"  UPDATED  {rel}")
            affected.append(rel)
    else:
        print("  SKIP    pyproject.toml (not found)")

    pkg = REPO_ROOT / "package.json"
    if pkg.exists():
        current = pkg.read_text()
        expected = _expected_package_json(current, clean)
        rel = str(pkg.relative_to(REPO_ROOT))
        if current == expected:
            print(f"  OK       {rel}")
        elif check_only:
            found = _extract_package_json_version(current)
            print(f"DRIFT  {rel}: expected '{clean}', found '{found}'")
            affected.append(rel)
        else:
            pkg.write_text(expected)
            print(f"  UPDATED  {rel}")
            affected.append(rel)
    else:
        print("  SKIP    package.json (not found)")

    return affected


def drift_check(expected: str) -> None:
    """
    Verify every sync target holds exactly expected. Exit 1 on any mismatch.

    Also fails if VERSION still carries _dev, which would mean sync was not
    run in release context (clean version not yet written to VERSION).

    Note: release.py uses sync(check_only=True) as its drift gate instead of
    calling this directly. This function is retained for standalone use.
    """
    version_file = REPO_ROOT / "VERSION"
    raw = version_file.read_text().strip()
    if "_dev" in raw:
        print(
            f"DRIFT: VERSION is {raw!r} — _dev must be removed before drift check",
            file=sys.stderr,
        )
        sys.exit(1)

    errors: list[str] = []

    pyproject = REPO_ROOT / "pyproject.toml"
    if pyproject.exists():
        found = _extract_pyproject_version(pyproject.read_text())
        if found != expected:
            errors.append(f"  pyproject.toml: version={found!r}  (expected {expected!r})")

    pkg = REPO_ROOT / "package.json"
    if pkg.exists():
        found = _extract_package_json_version(pkg.read_text())
        if found != expected:
            errors.append(f"  package.json: version={found!r}  (expected {expected!r})")

    if errors:
        print("DRIFT CHECK FAILED:", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)

    print(f"drift check: all targets are at {expected!r}  ✓")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sync VERSION to all version-bearing files."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Read-only drift check. Exit 0 if clean, 1 if any file drifted.",
    )
    args = parser.parse_args()

    drifted = sync(check_only=args.check)

    if args.check:
        if drifted:
            sys.exit(1)
        else:
            print("sync_version --check: no drift")
