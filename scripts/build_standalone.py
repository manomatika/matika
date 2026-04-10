import os
import subprocess
import shutil
import sys
import platform

def run_command(cmd, shell=True):
    print(f"Executing: {cmd}")
    subprocess.check_call(cmd, shell=shell)

def main():
    print("--- Starting Standalone Build ---")
    
    # 1. Build Frontend
    print("\n[1/4] Building Frontend assets...")
    run_command("npm install")
    run_command("npm run build")
    
    # 2. Run PyInstaller
    print("\n[2/4] Running PyInstaller...")
    # Ensure PYTHONPATH is set so PyInstaller can find src/matika
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    
    # Run pyinstaller using the spec file
    run_command(".venv/bin/pyinstaller --clean matika.spec")
    
    # 3. Verify Build
    print("\n[3/4] Verifying build output...")
    exe_name = "matika"
    if platform.system() == "Windows":
        exe_name += ".exe"
    
    dist_path = os.path.join("dist", exe_name)
    if os.path.exists(dist_path):
        print(f"SUCCESS: Executable created at {dist_path}")
    else:
        print(f"FAILED: Executable not found at {dist_path}")
        sys.exit(1)
        
    # 4. Packaging
    print("\n[4/4] Creating ZIP package...")
    version = "unknown"
    if os.path.exists("VERSION"):
        with open("VERSION", "r") as f:
            version = f.read().strip()
    
    system_name = platform.system().lower()
    arch_name = platform.machine().lower()
    zip_filename = f"matika-{version}-{system_name}-{arch_name}"
    
    # Create a clean folder for the ZIP
    pkg_dir = os.path.join("dist", "package")
    if os.path.exists(pkg_dir):
        shutil.rmtree(pkg_dir)
    os.makedirs(pkg_dir)
    
    # Copy executable
    shutil.copy2(dist_path, os.path.join(pkg_dir, exe_name))
    
    # Copy README if exists
    if os.path.exists("README.md"):
        shutil.copy2("README.md", os.path.join(pkg_dir, "README.md"))
        
    # Create ZIP
    shutil.make_archive(os.path.join("dist", zip_filename), 'zip', pkg_dir)
    print(f"SUCCESS: Package created at dist/{zip_filename}.zip")

if __name__ == "__main__":
    main()
