"""
sync_version.py — propagates the canonical version from VERSION into all
version-bearing files in the matika working tree.

Propagation targets (allowlist):
  pyproject.toml  — [project] version field
  package.json    — top-level "version" field

The VERSION file may carry a pre-release suffix (e.g. "0.0.4-dev" or
"0.0.4-rc.1"). The version CORE (everything before the first "-") is what gets
propagated, so all targets always hold a bare X.Y.Z string. VERSION itself is
never modified by this script.

  VERSION="0.0.4-dev"   →  pyproject.toml: version = "0.0.4"
                            package.json:   "version": "0.0.4"
  VERSION="0.0.4-rc.1"  →  pyproject.toml: version = "0.0.4"

Usage:
  python scripts/sync_version.py                # propagate (write files)
  python scripts/sync_version.py --check        # read-only drift check, human output
  python scripts/sync_version.py --check --json # read-only drift check, JSON output
"""

import argparse
import json as _json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


# ===========================================================================
# CANONICAL SEMVER PARSER (mirror)
#
# This is an IDENTICAL copy of the strict SemVer 2.0.0 parser whose canonical
# source is src/matika/core/paths.py (_parse_semver / version_core /
# is_prerelease). This build/release tooling cannot import the installed
# package, so the parser is mirrored here verbatim. Any change in paths.py MUST
# be applied here (and in matika.spec) to keep the three in lockstep.
# ===========================================================================

# MAJOR.MINOR.PATCH: each a non-negative integer with NO leading zeros.
_SEMVER_CORE = r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
# A pre-release identifier: numeric (no leading zeros) OR alphanumeric-with-hyphen.
_SEMVER_PRE_IDENT = r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
# Dot-separated pre-release identifiers, after the first '-'.
_SEMVER_PRERELEASE = rf"(?:{_SEMVER_PRE_IDENT}(?:\.{_SEMVER_PRE_IDENT})*)"
# Build metadata: dot-separated alphanumeric-with-hyphen identifiers, after '+'.
_SEMVER_BUILD = r"(?:[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)"

_SEMVER_RE = re.compile(
    rf"^(?P<core>{_SEMVER_CORE})"
    rf"(?:-(?P<prerelease>{_SEMVER_PRERELEASE}))?"
    rf"(?:\+(?P<build>{_SEMVER_BUILD}))?$"
)


def _parse_semver(raw):
    """Strictly parse a SemVer 2.0.0 string of the form
    ``[v]MAJOR.MINOR.PATCH[-prerelease][+build]``.

    Mirror of src/matika/core/paths.py:_parse_semver. Returns
    ``(core, prerelease, build)``; raises ValueError naming the offending value
    on any invalid input.
    """
    if not isinstance(raw, str):
        raise ValueError(
            f"invalid version {raw!r}: expected a string of the form "
            f"[v]MAJOR.MINOR.PATCH[-prerelease][+build]"
        )
    candidate = raw.strip()
    if candidate.startswith("v"):
        candidate = candidate[1:]
    m = _SEMVER_RE.match(candidate)
    if not m:
        raise ValueError(
            f"invalid version {raw!r}: expected SemVer of the form "
            f"[v]MAJOR.MINOR.PATCH[-prerelease][+build] "
            f"(three dot-separated non-negative integers without leading zeros, "
            f"optional pre-release and build metadata)"
        )
    return m.group("core"), m.group("prerelease"), m.group("build")


def version_core(version: str) -> str:
    """Return the bare MAJOR.MINOR.PATCH core of a SemVer string.

    Mirror of src/matika/core/paths.py:version_core. The CORE is the canonical
    identity propagated to all targets; the pre-release suffix and build metadata
    are human/audit-only.

      "0.0.4-dev"     -> "0.0.4"
      "0.0.4-rc.1"    -> "0.0.4"
      "v0.0.4+build"  -> "0.0.4"
      "0.0.4"         -> "0.0.4"

    Raises ValueError (naming the offending value) on non-SemVer input.
    """
    core, _prerelease, _build = _parse_semver(version)
    return core


def is_prerelease(version: str) -> bool:
    """True iff a SemVer string carries a pre-release component.

    Mirror of src/matika/core/paths.py:is_prerelease. Build metadata alone is NOT
    a pre-release. Raises ValueError (naming the offending value) on non-SemVer
    input.
    """
    _core, prerelease, _build = _parse_semver(version)
    return prerelease is not None

# Every file this script touches. drift_check() verifies exactly these.
SYNC_TARGETS: list[tuple[str, str]] = [
    ("pyproject.toml", "pyproject.toml [project].version"),
    ("package.json",   "package.json .version"),
]


def read_version() -> tuple[str, str]:
    """Return (raw, clean): raw is the VERSION file contents; clean is the bare core.

    'clean' is the bare X.Y.Z core — ANY pre-release suffix (-dev, -rc.N, ...)
    is stripped, not just the legacy "_dev".
    """
    version_file = REPO_ROOT / "VERSION"
    if not version_file.exists():
        print("ERROR: VERSION file not found", file=sys.stderr)
        sys.exit(1)
    raw = version_file.read_text().strip()
    clean = version_core(raw)
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

def sync(check_only: bool = False, quiet: bool = False) -> list:
    """
    Propagate VERSION to all targets (check_only=False) or compare without
    writing (check_only=True).

    Returns:
      Normal mode  — list[str]  of relative paths that were written.
      Check mode   — list[dict] of drift entries: {"path", "expected", "found"}.
                     Empty list means clean.

    quiet=True suppresses all print output (use for JSON consumers).

    In check mode VERSION may carry a pre-release suffix; the bare core is what
    targets are compared against (same as propagation — no special failure for a
    pre-release suffix here).
    """
    raw, clean = read_version()

    if not quiet:
        print(
            f"sync_version {'--check: checking against' if check_only else ': ' + repr(raw) + ' → propagating'} "
            f"{clean!r}"
        )

    affected: list = []

    pyproject = REPO_ROOT / "pyproject.toml"
    if pyproject.exists():
        current = pyproject.read_text()
        expected = _expected_pyproject(current, clean)
        rel = str(pyproject.relative_to(REPO_ROOT))
        if current == expected:
            if not quiet:
                print(f"  OK       {rel}")
        elif check_only:
            found = _extract_pyproject_version(current)
            if not quiet:
                print(f'DRIFT  {rel}: expected "{clean}", found "{found}"')
            affected.append({"path": rel, "expected": clean, "found": found})
        else:
            pyproject.write_text(expected)
            if not quiet:
                print(f"  UPDATED  {rel}")
            affected.append(rel)
    else:
        if not quiet:
            print("  SKIP    pyproject.toml (not found)")

    pkg = REPO_ROOT / "package.json"
    if pkg.exists():
        current = pkg.read_text()
        expected = _expected_package_json(current, clean)
        rel = str(pkg.relative_to(REPO_ROOT))
        if current == expected:
            if not quiet:
                print(f"  OK       {rel}")
        elif check_only:
            found = _extract_package_json_version(current)
            if not quiet:
                print(f'DRIFT  {rel}: expected "{clean}", found "{found}"')
            affected.append({"path": rel, "expected": clean, "found": found})
        else:
            pkg.write_text(expected)
            if not quiet:
                print(f"  UPDATED  {rel}")
            affected.append(rel)
    else:
        if not quiet:
            print("  SKIP    package.json (not found)")

    return affected


def verify_release_tag(tag: str) -> None:
    """Check that VERSION matches the given release tag before cutting.

    Strips a leading 'v' from *tag* (e.g. 'v0.0.4-rc.10' → '0.0.4-rc.10'),
    then compares against the raw VERSION string. Returns normally (exit 0
    from the caller) on a match; prints a loud, path-bearing error to stderr
    and exits 1 on any mismatch.

    Invariant enforced: VERSION must equal the tag being cut. Cutting a tag
    without VERSION matching it causes the frozen binary to report the wrong
    version.
    """
    if tag.startswith("v"):
        tag = tag[1:]

    raw, _clean = read_version()

    if raw == tag:
        print(f"INFO: version reconciled: {raw!r}")
        return

    version_file = REPO_ROOT / "VERSION"
    print(
        f'ERROR "VERSION {raw!r} != release tag {tag!r} — refusing release"\n'
        f"(VERSION file: {version_file})",
        file=sys.stderr,
    )
    sys.exit(1)


def drift_check(expected: str) -> None:
    """
    Verify every sync target holds exactly expected. Exit 1 on any mismatch.

    Also fails if VERSION still carries ANY pre-release suffix (-dev, -rc.N, ...),
    which means VERSION is not yet release-ready: the bare-core final version has
    not been written to VERSION.

    Note: release.py uses sync(check_only=True) as its drift gate instead of
    calling this directly. This function is retained for standalone use.
    """
    version_file = REPO_ROOT / "VERSION"
    raw = version_file.read_text().strip()
    if is_prerelease(raw):
        print(
            f"DRIFT: VERSION is {raw!r} — the pre-release suffix must be removed "
            f"(bare core {version_core(raw)!r}) before drift check; VERSION is not "
            f"release-ready",
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
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output (requires --check). Exit 0 if clean, 1 if drift.",
    )
    parser.add_argument(
        "--verify-tag",
        metavar="TAG",
        help="Verify VERSION matches the given release tag (e.g. v0.0.4-rc.10). "
             "Exit 0 on match, 1 on mismatch. Use before cutting a tag.",
    )
    args = parser.parse_args()

    if args.verify_tag:
        verify_release_tag(args.verify_tag)
        sys.exit(0)

    if args.json and not args.check:
        print("ERROR: --json requires --check", file=sys.stderr)
        sys.exit(2)

    drifted: list = sync(check_only=args.check, quiet=args.json)

    if args.check:
        if args.json:
            _, clean = read_version()
            print(_json.dumps({"version": clean, "drift": drifted}))
        if drifted:
            sys.exit(1)
        elif not args.json:
            print("sync_version --check: no drift")
