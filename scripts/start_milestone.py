import yaml
import subprocess
import sys
import os

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

def main():
    yaml_path = "milestone_tasks.yaml"
    if not os.path.exists(yaml_path):
        print(f"[ERROR] {yaml_path} not found.")
        sys.exit(1)

    try:
        with open(yaml_path, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"[ERROR] Failed to parse {yaml_path}: {e}")
        sys.exit(1)

    repo_name = get_repo_full_name()
    milestone_name = config.get("milestone")
    milestone_desc = config.get("description", "")
    branch_name = config.get("branch")
    issues = config.get("issues", [])

    print("\n" + "="*50)
    print("   RATEEYE MILESTONE: ARCHITECT START PLAN")
    print("="*50)
    print(f"Repository: {repo_name}")
    print(f"Milestone:  {milestone_name}")
    print(f"New Branch: {branch_name}")
    print(f"Issue Count: {len(issues)}")
    print("-"*50)
    print("Plan of Action:")
    print(f"1. Create Milestone: gh api --method POST repos/{repo_name}/milestones -f title=\"{milestone_name}\" ...")
    print(f"2. Local Branch: git checkout main && git pull && git checkout -b {branch_name}")
    print(f"3. Push Branch: git push -u origin {branch_name}")
    print(f"4. Create {len(issues)} Issues linked to milestone")
    print("="*50 + "\n")

    confirm = input("Begin milestone initialization? (y/n): ")
    if confirm.lower() != 'y':
        print("[INFO] Start aborted.")
        sys.exit(0)

    # 1. Milestone
    print(f"[1/4] Creating GitHub Milestone '{milestone_name}'...")
    create_cmd = f'gh api --method POST repos/{repo_name}/milestones -f title="{milestone_name}" -f description="{milestone_desc}"'
    run(create_cmd)

    # 2. Local Branch
    print(f"[2/4] Creating local branch '{branch_name}'...")
    run("git checkout main")
    run("git pull origin main")
    run(f"git checkout -b {branch_name}")

    # 3. Push Branch
    print(f"[3/4] Pushing branch to origin...")
    run(f"git push -u origin {branch_name}")

    # 4. Issues
    print(f"[4/4] Creating GitHub Issues...")
    for issue in issues:
        title = issue.get("title")
        body = issue.get("body", "").strip()
        print(f"   - Creating: {title}")
        
        # Use temporary file for multiline body to avoid shell escaping issues
        with open(".issue_body.md", "w") as bf:
            bf.write(body)
        
        # verified command: gh issue create --title "{title}" --body "{body}" --milestone "{milestone_title}"
        run(f'gh issue create --title "{title}" --body-file .issue_body.md --milestone "{milestone_name}"')
        
    if os.path.exists(".issue_body.md"):
        os.remove(".issue_body.md")

    print(f"\n[SUCCESS] Milestone {milestone_name} initialized and branch '{branch_name}' is ready.")

if __name__ == "__main__":
    main()
