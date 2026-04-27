import argparse
import subprocess
import sys
import os
import json
import glob

def run(cmd, check=True, capture=True):
    """Executes a shell command and returns output or handles errors."""
    try:
        result = subprocess.run(cmd, shell=True, check=check, text=True, capture_output=capture)
        return result.stdout.strip() if capture else None
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Command failed: {cmd}")
        if e.stderr: print(f"[DETAILS] {e.stderr}")
        if check: sys.exit(1)
        return None

def get_repo_full_name():
    return run("gh repo view --json nameWithOwner -q .nameWithOwner")

def get_current_branch():
    return run("git rev-parse --abbrev-ref HEAD")

def get_open_milestones(repo_full_name):
    """Fetches open milestones using the verified GET command."""
    cmd = f'gh api --method GET repos/{repo_full_name}/milestones -f state=open --jq ".[] | {{title: .title, number: .number}}"'
    output = run(cmd)
    if not output:
        return []
    
    milestones = []
    for line in output.splitlines():
        try:
            milestones.append(json.loads(line))
        except:
            pass
    return milestones

def update_version_file(version):
    """Updates the root VERSION file."""
    # Remove 'v' prefix if present for the VERSION file content
    clean_version = version.lstrip('v')
    with open("VERSION", "w") as f:
        f.write(clean_version + "\n")
    print(f"[INFO] Updated VERSION file to {clean_version}")

def update_markdown_headers(version):
    """Updates the header of all markdown files in the project."""
    header = f"**Matika** | Version: **{version}** | Copyright (c) 2026 Patrick James Tallman\n\n"
    md_files = glob.glob("**/*.md", recursive=True)
    
    for md_path in md_files:
        if ".gemini" in md_path or "node_modules" in md_path or ".venv" in md_path or "plugins" in md_path:
            continue
            
        with open(md_path, "r") as f:
            content = f.read()
            
        # Check if header already exists (starts with **Matika**)
        if content.startswith("**Matika**"):
            # Replace existing header line
            lines = content.splitlines(keepends=True)
            if lines:
                lines[0] = header
                new_content = "".join(lines)
            else:
                new_content = header
        else:
            # Prepend header
            new_content = header + content
            
        with open(md_path, "w") as f:
            f.write(new_content)
        print(f"[INFO] Updated header in {md_path}")

def main():
    parser = argparse.ArgumentParser(description="Matika Release Automation (Architect Version)")
    parser.add_argument("--version", required=True, help="Version to release (e.g., v1.0.5)")
    args = parser.parse_args()

    # Normalize version: ensure it starts with 'v' for tagging/release
    version = args.version if args.version.startswith('v') else f"v{args.version}"

    repo_name = get_repo_full_name()
    current_branch = get_current_branch()
    
    if current_branch == "main":
        print("[ERROR] You are already on 'main'. Run this from your feature/milestone branch.")
        sys.exit(1)

    milestones = get_open_milestones(repo_name)
    selected_milestone = None

    if milestones:
        if len(milestones) == 1:
            selected_milestone = milestones[0]
        else:
            print("\nMultiple open milestones found:")
            for i, m in enumerate(milestones, 1):
                print(f"{i}. {m['title']} (Number: {m['number']})")
            
            while True:
                try:
                    choice = input(f"\nSelect milestone to close (1-{len(milestones)}) or 'n' for none: ")
                    if choice.lower() == 'n': break
                    idx = int(choice) - 1
                    if 0 <= idx < len(milestones):
                        selected_milestone = milestones[idx]
                        break
                except ValueError:
                    pass
                print("Invalid selection.")

    print("\n" + "="*50)
    print("   MATIKA RELEASE: ARCHITECT PLAN OF ACTION")
    print("="*50)
    print(f"Repository:       {repo_name}")
    print(f"Current Branch:   {current_branch}")
    print(f"Target Version:   {version}")
    print(f"Closing Milestone: {selected_milestone['title'] if selected_milestone else 'None'}")
    print("-"*50)
    print("Steps to Execute:")
    print(f"1. Update VERSION file and Markdown headers locally")
    print(f"2. Commit version changes to {current_branch}")
    print(f"3. gh pr create --title \"Release {version}\" --body \"Merging {current_branch} to main\"")
    print(f"4. gh pr merge --merge --delete-branch")
    print(f"5. Local Cleanup: checkout main, pull, delete branch")
    print(f"6. uv build")
    print(f"7. gh release create {version} ./dist/*.whl --generate-notes")
    if selected_milestone:
        print(f"8. Close Milestone: gh api --method PATCH repos/{repo_name}/milestones/{selected_milestone['number']} -f state=closed")
    print("="*50 + "\n")

    confirm = input("Execute release? (y/n): ")
    if confirm.lower() != 'y':
        print("[INFO] Release aborted.")
        sys.exit(0)

    # 0. Update local files
    print(f"[0/6] Updating local version files...")
    update_version_file(version)
    update_markdown_headers(version)
    run(f"git add VERSION")
    run(f"git add -u") # Safely adds all modified tracked files (like the .md files)
    run(f'git commit -m "Bump version to {version} and update headers"')
    run(f"git push origin {current_branch}")

    # 1. PR
    print(f"[1/6] Creating Pull Request...")
    run(f'gh pr create --title "Release {version}" --body "Merging {current_branch} to main"', check=False)

    # 2. Merge
    print(f"[2/6] Merging Pull Request...")
    run(f"gh pr merge --merge --delete-branch")

    # 3. Cleanup
    print(f"[3/6] Cleaning up local environment...")
    run("git checkout main")
    run("git pull origin main")
    run(f"git branch -d {current_branch}", check=False)

    # 3.5 Sync Version (ensure backend reflects new VERSION)
    print(f"[3.5/6] Synchronizing version from VERSION file...")
    run(f"{sys.executable} scripts/sync_version.py")

    # 4. Build
    print(f"[4/6] Building distribution package...")
    if os.path.exists("dist"):
        import shutil
        shutil.rmtree("dist")
    run("uv build")

    # 5. Release
    print(f"[5/6] Creating GitHub Release {version}...")
    run(f"gh release create {version} ./dist/*.whl --generate-notes")

    # 6. Milestone
    if selected_milestone:
        print(f"[6/6] Closing Milestone '{selected_milestone['title']}'...")
        run(f"gh api --method PATCH repos/{repo_name}/milestones/{selected_milestone['number']} -f state=closed")
    else:
        print("[6/6] No milestone selected to close.")

    print(f"\n[SUCCESS] Release {version} completed successfully.")

if __name__ == "__main__":
    main()
