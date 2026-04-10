**Matika** | Version: **0.0.1** | Copyright (c) 2026 Patrick James Tallman



# Matika Automation Scripts

This folder contains scripts to automate the development lifecycle of Matika, specifically for releasing versions and initializing new milestones.

## Prerequisites

- **GitHub CLI (`gh`):** Must be installed and authenticated (`gh auth login`).
- **Git:** Must be configured locally.
- **uv:** Required for building the distribution package.
- **Python 3.x:** With `PyYAML` installed (`pip install PyYAML`).

---

## 1. Starting a New Milestone

The `start_milestone.py` script automates the creation of a GitHub Milestone, a dedicated feature branch, and all associated issues defined in `milestone_tasks.yaml`.

### Instructions:
1. **Update `milestone_tasks.yaml`:**
   - Set the `milestone` name.
   - Set the `branch` name.
   - Update the `description`.
   - List all `issues` with their respective `title` and `body`.
2. **Update `VERSION`:**
   - Update the root `VERSION` file to the target version for this milestone (e.g., `1.0.5_dev`).
3. **Run the script:**
   ```bash
   # On Mac/Linux:
   export PYTHONPATH=$PYTHONPATH:$(pwd)/src
   .venv/bin/python scripts/start_milestone.py

   # On Windows:
   $env:PYTHONPATH += ";$(Get-Location)\src"
   .venv\Scripts\python scripts/start_milestone.py
   ```

4. **Action:** Follow the prompts to confirm the initialization.

---

## 2. Releasing a Version

The `release.py` script automates the final steps of a milestone: creating a Pull Request to `main`, merging it, cleaning up local branches, building the package, and creating a GitHub Release.

### Instructions:
1. **Ensure you are on your milestone branch.**
2. **Run the script:**
   ```bash
   # On Mac/Linux:
   export PYTHONPATH=$PYTHONPATH:$(pwd)/src
   .venv/bin/python scripts/release.py --version <version number>

   # On Windows:
   $env:PYTHONPATH += ";$(Get-Location)\src"
   .venv\Scripts\python scripts/release.py --version <version number>
   ```

   *(Replace `<version number>` with your target release version, e.g., `v1.0.7`)*.
3. **Action:**
   - The script will show a "Plan of Action".
   - Confirm with `y` to execute.
   - It will automatically:
     - Create a PR from your current branch to `main`.
     - Merge the PR and delete the remote branch.
     - Switch your local environment to `main` and pull.
     - Build the project using `uv build`.
     - Create a GitHub Release with the build artifacts.
     - Prompt you to close the associated GitHub Milestone.

---

## Summary of Files to Update for Next Milestone

| File | Purpose |
| :--- | :--- |
| `VERSION` | Update to the next development version (e.g., `1.0.5_dev`). |
| `milestone_tasks.yaml` | Define the new milestone name, branch, and all issues to be tracked. |
| `translations.json` | (If applicable) Add any new UI strings required for the upcoming features. |
| `metadata/*.json` | (If applicable) Update any activity metadata required for new features. |
