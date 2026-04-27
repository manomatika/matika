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
    app_folder = os.path.join(home_dir, "Matika")
    
    # Ensure root folder and data subfolder exist
    if not os.path.exists(app_folder):
        os.makedirs(app_folder, exist_ok=True)
    
    data_folder = os.path.join(app_folder, "data")
    if not os.path.exists(data_folder):
        os.makedirs(data_folder, exist_ok=True)

    # If running as a bundle, ALWAYS use ~/Matika
    if getattr(sys, 'frozen', False):
        return app_folder

    cwd = os.getcwd()
    # If CWD is writable and not system root, use it (for dev)
    if os.access(cwd, os.W_OK) and not cwd == "/":
        return cwd
    
    return app_folder

ROOT_DIR = get_writable_root()


def get_matika_version() -> str:
    """Returns the running Matika version read from the VERSION file."""
    version_file = os.path.join(BASE_DIR, "VERSION")
    try:
        with open(version_file, "r") as f:
            return f.read().strip()
    except OSError:
        return "unknown"
