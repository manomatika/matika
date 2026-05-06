import yaml
import subprocess
import sys
import os

def run(cmd, check=True, capture=True):
    result = subprocess.run(cmd, shell=True, text=True, capture_output=capture)
    if result.returncode != 0:
        print(f"\n[ERROR] Command failed: {cmd}")
        if capture and result.stderr:
            print(f"[DETAILS] {result.stderr.strip()}")
        if check:
            sys.exit(1)
        return None
    return result.stdout.strip() if capture else ""

def get_repo_full_name():
    return run("gh repo view --json nameWithOwner -q .nameWithOwner")

def ensure_labels_exist(repo_name, labels):
    existing_raw = run(f'gh label list --repo {repo_name} --json name -q ".[].name" --limit 200')
    existing = set(existing_raw.splitlines()) if existing_raw else set()
    for label in labels:
        if label not in existing:
            print(f"   [label] Creating label '{label}'...")
            run(f'gh label create "{label}" --repo {repo_name} --color "ededed"', check=False)

def main():
    yaml_path = "scripts/milestone_tasks.yaml"
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
    version = config.get("version")
    issues = config.get("issues", [])

    print("\n" + "="*50)
    print("   MATIKA MILESTONE: ARCHITECT START PLAN")
    print("="*50)
    print(f"Repository:  {repo_name}")
    print(f"Milestone:   {milestone_name}")
    print(f"New Branch:  {branch_name}")
    if version:
        print(f"Version:     {version}")
    print(f"Issue Count: {len(issues)}")
    print("-"*50)
    print("Plan of Action:")
    print(f"1.  Create Milestone")
    if version:
        print(f"1b. Bump VERSION to {version}")
    print(f"2.  Create local branch '{branch_name}'")
    print(f"3.  Push branch to origin")
    print(f"4.  Create {len(issues)} issues linked to milestone")
    print("="*50 + "\n")

    confirm = input("Begin milestone initialization? (y/n): ")
    if confirm.lower() != 'y':
        print("[INFO] Start aborted.")
        sys.exit(0)

    # Step 1 — Milestone
    print(f"[1/4] Creating GitHub Milestone '{milestone_name}'...")
    run(f'gh api --method POST repos/{repo_name}/milestones -f title="{milestone_name}" -f description="{milestone_desc}"')

    # Step 1b — VERSION bump
    if version:
        print(f"[1b/4] Bumping VERSION to {version}...")
        with open("VERSION", "w") as vf:
            vf.write(version + "\n")
    else:
        print("[WARN] No 'version' key in YAML — skipping VERSION file update.")

    # Step 2 — Local branch
    print(f"[2/4] Creating local branch '{branch_name}'...")
    run("git checkout main")
    run("git pull origin main")
    run(f"git checkout -b {branch_name}")

    # Step 3 — Push branch
    print(f"[3/4] Pushing branch to origin...")
    run(f"git push -u origin {branch_name}")

    # Step 4 — Issues
    print(f"[4/4] Creating GitHub Issues...")

    all_labels = set()
    for issue in issues:
        for label in issue.get("labels", []):
            all_labels.add(label)

    if all_labels:
        print("   Ensuring labels exist in repo...")
        ensure_labels_exist(repo_name, all_labels)

    created = 0
    failed = 0
    for issue in issues:
        title = issue.get("title", "")
        body = issue.get("body", "").strip()
        labels = issue.get("labels", [])
        print(f"   - Creating: {title}")

        with open(".issue_body.md", "w") as bf:
            bf.write(body)

        label_flags = " ".join(f'--label "{lbl}"' for lbl in labels)
        cmd = f'gh issue create --title "{title}" --body-file .issue_body.md --milestone "{milestone_name}"'
        if label_flags:
            cmd += f" {label_flags}"

        result = run(cmd, check=False)
        if result is None:
            print(f"   [FAILED] Could not create issue: {title}")
            failed += 1
        else:
            created += 1

    if os.path.exists(".issue_body.md"):
        os.remove(".issue_body.md")

    # Summary
    print("\n" + "="*50)
    print("   MILESTONE INITIALIZATION SUMMARY")
    print("="*50)
    print(f"Milestone:      {milestone_name}")
    print(f"Branch:         {branch_name}")
    if version:
        print(f"VERSION set to: {version}")
    print(f"Issues created: {created}")
    if failed:
        print(f"Issues failed:  {failed}")
    print("="*50)

if __name__ == "__main__":
    main()
