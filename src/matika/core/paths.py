import os
import sys

def get_base_dir():
    """Returns the base directory for the application, handling PyInstaller bundles."""
    if getattr(sys, 'frozen', False):
        # Running as a bundled executable
        # sys._MEIPASS is the root of the temporary bundle folder
        return sys._MEIPASS
    else:
        # Running as a normal Python script
        # __file__ is src/matika/core/paths.py
        # root is 4 levels up
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

BASE_DIR = get_base_dir()

def get_writable_root():
    """Returns a writable directory for logs and data."""
    home_dir = os.path.expanduser("~")
    app_folder = os.path.join(home_dir, "matika")
    
    # Ensure root folder and data subfolder exist
    if not os.path.exists(app_folder):
        os.makedirs(app_folder, exist_ok=True)
    
    data_folder = os.path.join(app_folder, "data")
    if not os.path.exists(data_folder):
        os.makedirs(data_folder, exist_ok=True)

    # If running as a bundle, ALWAYS use ~/matika
    if getattr(sys, 'frozen', False):
        return app_folder

    cwd = os.getcwd()
    # If CWD is writable and not system root, use it (for dev)
    if os.access(cwd, os.W_OK) and not cwd == "/":
        return cwd
    
    return app_folder

ROOT_DIR = get_writable_root()


# ===========================================================================
# CANONICAL SEMVER PARSER
#
# _parse_semver is the SINGLE strict SemVer 2.0.0 parser for the whole product.
# version_core() and is_prerelease() both build on it so there is exactly ONE
# parser in the runtime. The build/release tooling cannot import this installed
# package, so an IDENTICAL copy of this parser is mirrored, verbatim, in:
#   - scripts/sync_version.py
#   - matika.spec (PyInstaller spec at repo root)
# Any change here MUST be applied to those mirrors as well.
# ===========================================================================

# MAJOR.MINOR.PATCH: each a non-negative integer with NO leading zeros.
_SEMVER_CORE = r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
# A pre-release identifier: numeric (no leading zeros) OR alphanumeric-with-hyphen.
_SEMVER_PRE_IDENT = r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
# Dot-separated pre-release identifiers, after the first '-'.
_SEMVER_PRERELEASE = rf"(?:{_SEMVER_PRE_IDENT}(?:\.{_SEMVER_PRE_IDENT})*)"
# Build metadata: dot-separated alphanumeric-with-hyphen identifiers, after '+'.
_SEMVER_BUILD = r"(?:[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)"

import re as _re

_SEMVER_RE = _re.compile(
    rf"^(?P<core>{_SEMVER_CORE})"
    rf"(?:-(?P<prerelease>{_SEMVER_PRERELEASE}))?"
    rf"(?:\+(?P<build>{_SEMVER_BUILD}))?$"
)


def _parse_semver(raw):
    """Strictly parse a SemVer 2.0.0 string of the form
    ``[v]MAJOR.MINOR.PATCH[-prerelease][+build]``.

    A single optional leading 'v' is tolerated and stripped. MAJOR/MINOR/PATCH
    are non-negative integers with no leading zeros (so '01.2.3' is invalid),
    exactly three of them. Pre-release identifiers are dot-separated; numeric
    identifiers carry no leading zeros; identifiers are alphanumerics and hyphens
    (so a pre-release identifier MAY contain hyphens, e.g. 'alpha-1'). Build
    metadata after '+' is NOT part of the core and is NOT a pre-release signal.
    An empty pre-release ('1.2.3-') or empty build is invalid.

    Returns ``(core, prerelease, build)`` where prerelease/build are the
    substrings after '-'/'+' or None when absent. Raises ValueError naming the
    offending value and the expected shape on any invalid input.
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

    The version CORE is the canonical identity used for ALL comparison,
    artifact/bundle naming, and OS/installer/Info.plist version fields. The
    pre-release SUFFIX (``-dev``, ``-rc.N``, ...) and build metadata live only on
    human/audit surfaces (the VERSION file string, git tags, release titles, the
    audit log).

    Examples:
      "0.0.4-dev"        -> "0.0.4"
      "0.0.4-rc.1"       -> "0.0.4"
      "v0.0.4-rc.1"      -> "0.0.4"
      "0.0.4+build.5"    -> "0.0.4"
      "1.2.3-alpha-1"    -> "1.2.3"
      "0.0.4"            -> "0.0.4"

    Raises ValueError (naming the offending value) on any non-SemVer input.
    """
    core, _prerelease, _build = _parse_semver(version)
    return core


def is_prerelease(version: str) -> bool:
    """True iff a SemVer string carries a pre-release component.

    Build metadata alone (e.g. ``0.0.4+build``) is NOT a pre-release. Raises
    ValueError (naming the offending value) on any non-SemVer input.
    """
    _core, prerelease, _build = _parse_semver(version)
    return prerelease is not None


def get_matika_version() -> str:
    """Return the running Matika version read from the VERSION file.

    Raises RuntimeError with the absolute path on a missing/unreadable VERSION
    file. There is NO "unknown" sentinel: a missing/unreadable VERSION is a
    serious bug and must surface at its real source, not as a downstream
    "invalid SemVer: 'unknown'" error.
    """
    version_file = os.path.join(BASE_DIR, "VERSION")
    try:
        with open(version_file, "r") as f:
            return f.read().strip()
    except OSError as exc:
        raise RuntimeError(
            f"Matika VERSION file missing or unreadable at "
            f"{os.path.abspath(version_file)}: {exc}"
        ) from exc
