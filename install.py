import os
import sys
import subprocess
import platform
import logging
import shutil
from datetime import datetime

# --- CONFIGURATION ---
LOG_DIR = "logs"
INSTALL_LOG = os.path.join(LOG_DIR, "install.log")
VENV_DIR = ".venv"
REQUIREMENTS_FILE = "requirements.txt"

# --- LOGGING SETUP ---
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Configure logging to both file and console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(INSTALL_LOG),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def run_command(cmd, shell=True, env=None):
    """Executes a command and logs output."""
    logger.info(f"Executing: {cmd}")
    try:
        process = subprocess.Popen(
            cmd,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env
        )
        
        output_lines = []
        for line in process.stdout:
            line_str = line.strip()
            if line_str:
                logger.debug(line_str)
                output_lines.append(line_str)
        
        process.wait()
        if process.returncode != 0:
            logger.error(f"Command failed with exit code {process.returncode}")
            # Log the last few lines of output on failure for context
            for line in output_lines[-10:]:
                logger.error(f"  [Last Output] {line}")
            return False
        return True
    except Exception as e:
        logger.error(f"Exception during command execution: {e}")
        return False

def check_prerequisite(cmd, name):
    """Checks if a prerequisite command exists in the path."""
    logger.info(f"Checking for {name}...")
    if shutil.which(cmd):
        logger.info(f"Found {name}.")
        return True
    logger.error(f"{name} not found in PATH. Please install it before proceeding.")
    return False

def main():
    start_time = datetime.now()
    logger.info("="*60)
    logger.info("MATIKA AUTOMATED INSTALLATION & DEPLOYMENT")
    logger.info("="*60)
    
    # 0. Sync Version
    logger.info("--- Step 0: Synchronizing Version from VERSION file ---")
    if os.path.exists("scripts/sync_version.py"):
        if not run_command(f"{sys.executable} scripts/sync_version.py"):
            logger.error("Version synchronization failed. Proceeding with caution.")
    else:
        logger.warning("scripts/sync_version.py not found. Skipping version sync.")

    os_name = platform.system()
    logger.info(f"Detected OS: {os_name}")

    # 1. Prerequisite Checks
    prereqs = [
        ("git", "Git"),
        ("node", "Node.js"),
        ("npm", "NPM")
    ]
    
    all_prereqs_ok = True
    for cmd, name in prereqs:
        if not check_prerequisite(cmd, name):
            all_prereqs_ok = False
    
    if not all_prereqs_ok:
        logger.error("Prerequisite checks failed. Aborting installation.")
        sys.exit(1)

    # 2. Environment Setup (Step 2)
    logger.info("--- Step 2: Setting up Python Environment ---")
    
    # Use uv if available, fallback to venv
    has_uv = shutil.which("uv")
    if has_uv:
        logger.info("Found 'uv'. Using it for environment setup.")
        if not run_command("uv venv"): sys.exit(1)
    else:
        logger.info("'uv' not found. Falling back to standard 'venv'.")
        if not run_command(f"{sys.executable} -m venv {VENV_DIR}"): sys.exit(1)

    # Determine Python/Pip paths based on OS
    if os_name == "Windows":
        venv_python = os.path.join(VENV_DIR, "Scripts", "python.exe")
        venv_pip = os.path.join(VENV_DIR, "Scripts", "pip.exe")
    else:
        venv_python = os.path.join(VENV_DIR, "bin", "python")
        venv_pip = os.path.join(VENV_DIR, "bin", "pip")

    # Install Python Dependencies
    if has_uv:
        if not run_command("uv pip install -r requirements.txt"): sys.exit(1)
    else:
        if not run_command(f"{venv_pip} install --upgrade pip"): sys.exit(1)
        if not run_command(f"{venv_pip} install -r {REQUIREMENTS_FILE}"): sys.exit(1)

    # 3. Build Frontend (Step 3)
    logger.info("--- Step 3: Building Frontend Assets ---")
    if not run_command("npm install"): sys.exit(1)
    if not run_command("npm run build"): sys.exit(1)

    # 4. Validation (Unit Tests)
    logger.info("--- Step 4: Running Unit Tests ---")
    # We use the venv python to run pytest
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    if not run_command(f"{venv_python} -m pytest", env=env):
        logger.error("Unit tests failed. Matika will not be launched.")
        logger.error(f"Check {INSTALL_LOG} for details.")
        sys.exit(1)
    
    logger.info("All tests passed successfully!")

    # 5. Launch (Step 5)
    logger.info("--- Step 5: Launching Matika ---")
    end_time = datetime.now()
    duration = end_time - start_time
    logger.info(f"Installation completed in {duration.total_seconds():.2f} seconds.")
    logger.info("Starting the server...")
    
    # Final instruction to user
    print("\n" + "*"*60)
    print("SUCCESS: Matika is now running at http://localhost:8000")
    print(f"Log file available at: {INSTALL_LOG}")
    print("*"*60 + "\n")

    # Start the server (this will take over the process)
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
        subprocess.run([venv_python, "-m", "matika.main"], env=env)
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")

if __name__ == "__main__":
    main()
