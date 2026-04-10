import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_environment():
    """Checks if the environment is ready for production."""
    ready = True
    
    # 1. Check for necessary configuration files
    required_files = [
        "VERSION", 
        "src/matika/locales/translations.json",
        "requirements.txt"
    ]
    for file in required_files:
        if not os.path.exists(file):
            logger.error(f"Missing required file: {file}")
            ready = False
        else:
            logger.info(f"Found required file: {file}")

    # 2. Check for necessary directories
    required_dirs = [
        "src/matika/static", 
        "src/matika/templates", 
        "logs", 
        "data"
    ]
    for directory in required_dirs:
        if not os.path.exists(directory):
            logger.error(f"Missing required directory: {directory}")
            ready = False
        else:
            logger.info(f"Found required directory: {directory}")

    # 4. Check for node modules (since we use TypeScript)
    if not os.path.exists("node_modules"):
        logger.warning("node_modules not found. Did you run 'npm install'?")
        # Not necessarily a failure for all deployment steps, but good to know

    if ready:
        logger.info("Environment check passed!")
    else:
        logger.error("Environment check failed!")
    
    return ready

if __name__ == "__main__":
    if not check_environment():
        sys.exit(1)
    sys.exit(0)
