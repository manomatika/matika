import os
import logging
import shutil
from datetime import datetime
from sqlalchemy.orm import Session
from .paths import ROOT_DIR
from ..database import get_system_setting

# --- LOGGING & ENVIRONMENT SETUP ---
LOG_DIR = os.path.join(ROOT_DIR, os.environ.get("LOG_DIR", "logs"))
ACTIVE_LOG = os.path.join(LOG_DIR, "Matika.log")
STARTUP_LOG = os.path.join(LOG_DIR, "startup.log")
TEST_LOG = os.path.join(LOG_DIR, "test_Matika.log")

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

logger = logging.getLogger(__name__)

def setup_startup_logging(is_testing: bool):
    """Initializes startup logging to startup.log."""
    if is_testing:
        return
    
    # Rotate old startup log before clearing if it exists
    if os.path.exists(STARTUP_LOG):
        today_str = datetime.now().strftime("%Y%m%d")
        archive_name = os.path.join(LOG_DIR, f"{today_str}_startup.log")
        if not os.path.exists(archive_name):
            shutil.copy(STARTUP_LOG, archive_name)
    
    with open(STARTUP_LOG, "w") as f:
        f.write(f"--- Matika Startup at {datetime.now()} ---\n")
    
    startup_handler = logging.FileHandler(STARTUP_LOG)
    startup_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(startup_handler)
    root_logger.addHandler(logging.StreamHandler())

def rotate_logs(is_testing: bool):
    """Rotates the production log files daily."""
    if is_testing:
        return
    today_str = datetime.now().strftime("%Y%m%d")
    for active, suffix in [(ACTIVE_LOG, "Matika.log"), (STARTUP_LOG, "startup.log"), (TEST_LOG, "test_Matika.log")]:
        archive = os.path.join(LOG_DIR, f"{today_str}_{suffix}")
        if os.path.exists(active) and not os.path.exists(archive):
            shutil.copy(active, archive)
            with open(active, "w") as f:
                f.write(f"--- Log Rotated at {datetime.now()} ---\n")

def cleanup_logs(db: Session, is_testing: bool):
    """Deletes old log archives based on system retention settings."""
    if is_testing:
        return
    retention_map = {
        "Matika.log": "app_log_retention",
        "startup.log": "startup_log_retention",
        "test_Matika.log": "test_log_retention"
    }
    now = datetime.now()
    for filename in os.listdir(LOG_DIR):
        if not filename.endswith(".log") or "_" not in filename:
            continue
        try:
            # Format is YYYYMMDD_suffix.log
            date_str, suffix = filename.split("_", 1)
            setting_name = retention_map.get(suffix)
            if not setting_name:
                continue

            try:
                file_date = datetime.strptime(date_str, "%Y%m%d")
            except ValueError:
                # Filename prefix is not a YYYYMMDD date — skip silently.
                continue

            days = int(get_system_setting(db, setting_name, "10"))
            if (now - file_date).days >= days:
                os.remove(os.path.join(LOG_DIR, filename))
                logger.info(f"Deleted old log: {filename}")
        except Exception as e:
            logger.error(f"Error cleaning {filename}: {e}")

def finalize_logging(is_testing: bool):
    """Switches from startup log to the main application log."""
    if is_testing:
        return
    
    root_logger = logging.getLogger()
    # Remove startup handler
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.FileHandler) and handler.baseFilename.endswith("startup.log"):
            root_logger.removeHandler(handler)
            handler.close()
            
    # Add application log handler
    app_handler = logging.FileHandler(ACTIVE_LOG)
    app_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    root_logger.addHandler(app_handler)
    logger.info("Startup complete. Switching to application log.")
