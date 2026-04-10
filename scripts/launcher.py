import sys
import os
import multiprocessing
import traceback
import time

# 1. Setup emergency logging IMMEDIATELY
home = os.path.expanduser("~")
app_dir = os.path.join(home, "Matika")
log_dir = os.path.join(app_dir, "logs")

try:
    os.makedirs(log_dir, exist_ok=True)
    boot_log_path = os.path.join(log_dir, "boot.log")
    boot_log = open(boot_log_path, "a", buffering=1)
except Exception:
    # If we can't even open a log file in home dir, we are in deep trouble
    boot_log = None

def log(msg):
    if boot_log:
        try:
            boot_log.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
        except:
            pass

# Redirect stdout and stderr
if boot_log:
    sys.stdout = boot_log
    sys.stderr = boot_log

log("--- Sequoia-Ready Launcher Bootstrap Starting ---")
log(f"Executable: {sys.executable}")
log(f"CWD: {os.getcwd()}")

def show_error(msg):
    """Shows a macOS or Windows error dialog."""
    log(f"CRITICAL ERROR: {msg}")
    try:
        if sys.platform == 'darwin':
            # Escape for AppleScript
            escaped = msg.replace('"', '\\"').replace("'", "'\"'\"'")
            os.system(f"osascript -e 'display alert \"Matika Error\" message \"{escaped}\" buttons {{\"OK\"}}'")
        elif sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, "Matika Error", 0x10)
    except:
        pass

if __name__ == "__main__":
    # Required for frozen apps using uvicorn
    multiprocessing.freeze_support()
    
    try:
        if getattr(sys, "frozen", False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            
        log(f"Internal Base path: {base_path}")
        
        src_path = os.path.join(base_path, "src")
        if os.path.exists(src_path):
            sys.path.insert(0, src_path)
        else:
            sys.path.insert(0, base_path)

        # Early import to check paths
        from matika.core.paths import ROOT_DIR
        log(f"User Data Root: {ROOT_DIR}")
        
        # Explicitly ensure the data folder exists before anything else
        os.makedirs(os.path.join(ROOT_DIR, "data"), exist_ok=True)
        log(f"Data folder verified")

        from matika.main import app
        import uvicorn
        import webbrowser
        from threading import Timer

        def open_browser():
            log("Attempting to open browser...")
            try:
                webbrowser.open("http://127.0.0.1:8000")
            except Exception as e:
                log(f"Browser open failed: {e}")

        is_testing = "pytest" in os.environ.get("PYTEST_CURRENT_TEST", "")
        if not is_testing:
            Timer(2.5, open_browser).start()

        log("Starting server on 127.0.0.1:8000")
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info", access_log=True)

    except Exception as e:
        tb = traceback.format_exc()
        log(f"FATAL EXCEPTION: {e}\n{tb}")
        show_error(f"Failed to start Matika:\n{str(e)}")
        sys.exit(1)
