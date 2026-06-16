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


def version_core(version: str) -> str:
    """Strip any pre-release suffix, returning the bare X.Y.Z core.

    The version CORE (everything before the first "-") is the canonical
    identity used for ALL comparison, artifact/bundle naming, and
    OS/installer/Info.plist version fields. The pre-release SUFFIX
    (``-dev``, ``-rc.N``, ...) lives only on human/audit surfaces (the
    VERSION file string, git tags, release titles, the audit log).

    Examples:
      "0.0.4-dev"  -> "0.0.4"
      "0.0.4-rc.1" -> "0.0.4"
      "0.0.4"      -> "0.0.4"

    This is the single canonical "strip to core" helper for the runtime.
    scripts/sync_version.py mirrors it for the build/release tooling, which
    cannot import the installed package.
    """
    return version.split("-", 1)[0].strip()


def is_prerelease(version: str) -> bool:
    """True if version carries a pre-release suffix (contains a "-")."""
    return "-" in version


def get_matika_version() -> str:
    """Returns the running Matika version read from the VERSION file."""
    version_file = os.path.join(BASE_DIR, "VERSION")
    try:
        with open(version_file, "r") as f:
            return f.read().strip()
    except OSError:
        return "unknown"
