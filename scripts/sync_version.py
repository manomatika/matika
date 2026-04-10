import os
import re

def sync_version():
    if not os.path.exists("VERSION"):
        print("VERSION file not found.")
        return

    with open("VERSION", "r") as f:
        version_raw = f.read().strip()

    # Remove _dev postfix if present
    version = version_raw.replace("_dev", "")
    print(f"Syncing version to: {version} (from {version_raw})")

    # 1. Update pyproject.toml
    if os.path.exists("pyproject.toml"):
        with open("pyproject.toml", "r") as f:
            content = f.read()
        
        # Replace version = "..."
        new_content = re.sub(r'version\s*=\s*".*?"', f'version = "{version}"', content)
        
        with open("pyproject.toml", "w") as f:
            f.write(new_content)
        print("Updated pyproject.toml")

    # 2. Update doc/DEPLOYMENT.md
    deployment_md = "doc/DEPLOYMENT.md"
    if os.path.exists(deployment_md):
        with open(deployment_md, "r") as f:
            content = f.read()
        
        # We need to find the old version to replace it throughout.
        # But the user says they have version references.
        # Let's replace anything that looks like a version in specific contexts
        # or just replace the known old version if we can find it.
        # Actually, let's just search for 'matika-X.X.X' patterns.
        
        new_content = re.sub(r'matika-\d+\.\d+\.\d+(?:-dev)?', f'matika-{version}', content)
        # Also handle specific mentions of the version number alone if they are obvious
        # but be careful.
        
        # Given the grep results, this handles:
        # matika-X.X.X.tar.gz
        # matika-X.X.X-py3-none-any.whl
        # pip install matika-X.X.X-py3-none-any.whl
        
        with open(deployment_md, "w") as f:
            f.write(new_content)
        print(f"Updated {deployment_md}")

if __name__ == "__main__":
    sync_version()
