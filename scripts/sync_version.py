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

Run from the repo root:
  python scripts/sync_version.py
"""

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

# Every file this script touches. The drift_check() verifies exactly these.
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


def _sync_pyproject(path: Path, version: str) -> bool:
    """Write version into pyproject.toml [project] section. Returns True if file changed."""
    content = path.read_text()
    new_content = re.sub(
        r'^(version\s*=\s*)"[^"]*"',
        rf'\1"{version}"',
        content,
        flags=re.MULTILINE,
    )
    if new_content == content:
        return False
    path.write_text(new_content)
    return True


def _sync_package_json(path: Path, version: str) -> bool:
    """Write version into the top-level "version" field. Returns True if file changed."""
    content = path.read_text()
    new_content, n = re.subn(
        r'^(\s*"version"\s*:\s*)"[^"]*"',
        rf'\1"{version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if n == 0 or new_content == content:
        return False
    path.write_text(new_content)
    return True


def sync() -> list[str]:
    """Propagate VERSION to all targets. Return list of relative paths that were written."""
    raw, clean = read_version()
    print(f"sync_version: {raw!r} → propagating {clean!r}")

    written: list[str] = []

    pyproject = REPO_ROOT / "pyproject.toml"
    if pyproject.exists():
        changed = _sync_pyproject(pyproject, clean)
        rel = str(pyproject.relative_to(REPO_ROOT))
        print(f"  {'UPDATED' if changed else 'OK     '}  {rel}")
        if changed:
            written.append(rel)
    else:
        print("  SKIP    pyproject.toml (not found)")

    pkg = REPO_ROOT / "package.json"
    if pkg.exists():
        changed = _sync_package_json(pkg, clean)
        rel = str(pkg.relative_to(REPO_ROOT))
        print(f"  {'UPDATED' if changed else 'OK     '}  {rel}")
        if changed:
            written.append(rel)
    else:
        print("  SKIP    package.json (not found)")

    return written


def drift_check(expected: str) -> None:
    """
    Verify every sync target holds exactly expected. Exit 1 on any mismatch.

    Also fails if VERSION still carries _dev, which would mean sync was not
    run in release context (clean version not yet written to VERSION).
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
        m = re.search(r'^version\s*=\s*"([^"]*)"', pyproject.read_text(), re.MULTILINE)
        found = m.group(1) if m else "<not found>"
        if found != expected:
            errors.append(f"  pyproject.toml: version={found!r}  (expected {expected!r})")

    pkg = REPO_ROOT / "package.json"
    if pkg.exists():
        m = re.search(r'^(\s*"version"\s*:\s*)"([^"]*)"', pkg.read_text(), re.MULTILINE)
        found = m.group(2) if m else "<not found>"
        if found != expected:
            errors.append(f"  package.json: version={found!r}  (expected {expected!r})")

    if errors:
        print("DRIFT CHECK FAILED:", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)

    print(f"drift check: all targets are at {expected!r}  ✓")


if __name__ == "__main__":
    sync()
