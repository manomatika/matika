import argparse
import re
import subprocess
import sys
import os
import json

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
    clean_version = version.lstrip('v')
    with open("VERSION", "w") as f:
        f.write(clean_version + "\n")
    print(f"[INFO] Updated VERSION file to {clean_version}")

def update_markdown_headers(version):
    """Updates the header and replaces version strings in all markdown files."""
    clean_version = version.lstrip('v')
    header = f"**Matika** | Version: **{version}** | Copyright (c) 2026 Patrick James Tallman\n\n"
    skip_dirs = {".gemini", "node_modules", ".venv", "plugins", "__pycache__"}

    for dirpath, dirnames, filenames in os.walk(".", followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
        for filename in filenames:
            if not filename.endswith(".md"):
                continue
            md_path = os.path.join(dirpath, filename)
            with open(md_path, "r") as f:
                content = f.read()

            # Apply full-content version replacements to original content first,
            # so counts reflect actual substitutions (not the header we're about to set).
            new_content = content
            replacements = 0

            # Replace v\d+\.\d+\.\d+ throughout (e.g. v0.0.3 → v0.0.4)
            new_content, n = re.subn(r'v\d+\.\d+\.\d+', version, new_content)
            replacements += n

            # Replace bare versions in matika_version: "0.0.2" or matika_version: 0.0.2
            new_content, n = re.subn(
                r'(matika_version:\s*["\']?)\d+\.\d+\.\d+(["\']?)',
                rf'\g<1>{clean_version}\2',
                new_content
            )
            replacements += n

            # Replace bare versions in version: 0.0.2 (yaml/json key at line start)
            new_content, n = re.subn(
                r'^(\s*version:\s*["\']?)\d+\.\d+\.\d+(["\']?)',
                rf'\g<1>{clean_version}\2',
                new_content,
                flags=re.MULTILINE
            )
            replacements += n

            # Replace bare versions in Version: **0.0.3** markdown bold context
            new_content, n = re.subn(
                r'(Version:\s*\*\*)\d+\.\d+\.\d+(\*\*)',
                rf'\g<1>{clean_version}\2',
                new_content
            )
            replacements += n

            # Update or prepend the Matika header line
            if new_content.startswith("**Matika**"):
                lines = new_content.splitlines(keepends=True)
                if lines:
                    lines[0] = header
                    new_content = "".join(lines)
                else:
                    new_content = header
            else:
                new_content = header + new_content

            if new_content != content:
                with open(md_path, "w") as f:
                    f.write(new_content)
                print(f"[INFO] Updated {md_path} ({replacements} version replacement(s))")

def main():
    parser = argparse.ArgumentParser(description="Matika Release Automation (Architect Version)")
    parser.add_argument("--version", required=True, help="Version to release (e.g., v1.0.5)")
    args = parser.parse_args()

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
    print(f"6. gh release create {version} --generate-notes --title \"{version}\"")
    if selected_milestone:
        print(f"7. Close Milestone: gh api --method PATCH repos/{repo_name}/milestones/{selected_milestone['number']} -f state=closed")
    print("="*50 + "\n")

    confirm = input("Execute release? (y/n): ")
    if confirm.lower() != 'y':
        print("[INFO] Release aborted.")
        sys.exit(0)

    # 0. Update local files
    print(f"[0/5] Updating local version files...")
    update_version_file(version)
    update_markdown_headers(version)
    run(f"git add VERSION")
    run(f"git add -u")
    run(f'git commit -m "Bump version to {version} and update headers"')
    run(f"git push origin {current_branch}")

    # 1. PR
    print(f"[1/5] Creating Pull Request...")
    run(f'gh pr create --title "Release {version}" --body "Merging {current_branch} to main"', check=False)

    # 2. Merge
    print(f"[2/5] Merging Pull Request...")
    run(f"gh pr merge --merge --delete-branch")

    # 3. Cleanup
    print(f"[3/5] Cleaning up local environment...")
    run("git checkout main")
    run("git pull origin main")
    run(f"git branch -d {current_branch}", check=False)

    # 3.5. Sync Version
    print(f"[3.5/5] Synchronizing version from VERSION file...")
    run(f"{sys.executable} scripts/sync_version.py")

    # 4. Release
    print(f"[4/5] Creating GitHub Release {version}...")
    run(f'gh release create {version} --generate-notes --title "{version}"')

    # 5. Milestone
    if selected_milestone:
        print(f"[5/5] Closing Milestone '{selected_milestone['title']}'...")
        run(f"gh api --method PATCH repos/{repo_name}/milestones/{selected_milestone['number']} -f state=closed")
    else:
        print("[5/5] No milestone selected to close.")

    print(f"\n[SUCCESS] Release {version} completed successfully.")

if __name__ == "__main__":
    main()
