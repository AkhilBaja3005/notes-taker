import os
import time
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ENABLE_GIT_SYNC = os.environ.get("ENABLE_GIT_SYNC", "false").lower() in ("true", "1", "yes")
LECTURES_DIR = Path(os.environ.get("LECTURES_DIR", "./lectures")).resolve()
GIT_BRANCH = os.environ.get("GIT_BRANCH", "main")

def run_git_cmd(cmd_list: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        res = subprocess.run(
            cmd_list,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30
        )
        if res.returncode == 0:
            return True, res.stdout.strip()
        else:
            return False, res.stderr.strip()
    except Exception as e:
        return False, str(e)

def init_vault_git():
    """Initializes or configures git in LECTURES_DIR."""
    if not ENABLE_GIT_SYNC:
        return

    LECTURES_DIR.mkdir(parents=True, exist_ok=True)
    git_dir = LECTURES_DIR / ".git"
    repo_url = os.environ.get("GIT_VAULT_REPO_URL", "").strip()

    if not git_dir.exists():
        run_git_cmd(["git", "init"], LECTURES_DIR)
        run_git_cmd(["git", "branch", "-M", GIT_BRANCH], LECTURES_DIR)
        
        # Configure a default git user for automated commits if not set
        run_git_cmd(["git", "config", "user.name", "Notes Assistant Bot"], LECTURES_DIR)
        run_git_cmd(["git", "config", "user.email", "bot@academic-assistant.internal"], LECTURES_DIR)

        if repo_url:
            run_git_cmd(["git", "remote", "add", "origin", repo_url], LECTURES_DIR)
    else:
        if repo_url:
            run_git_cmd(["git", "remote", "set-url", "origin", repo_url], LECTURES_DIR)

    # Ensure a strict vault-level .gitignore exists inside the Obsidian repo
    vault_gitignore = LECTURES_DIR / ".gitignore"
    if not vault_gitignore.exists():
        vault_gitignore.write_text(
            "# Obsidian Vault Git Ignore\n"
            ".DS_Store\n"
            "*.db\n"
            "*.sqlite*\n"
            "vector_db/\n"
            "incoming_audio/\n"
            "optimized_audio/\n"
            "*.bin\n"
            "*.pyc\n",
            encoding="utf-8"
        )

def sync_notes_to_git(commit_message: str = "Add lecture notes [Automated Sync]") -> tuple[bool, str]:
    """Commits and pushes newly created or modified lecture notes to the remote Git repository."""
    if not ENABLE_GIT_SYNC:
        return True, "Git sync disabled"

    init_vault_git()
    print(f"[*] Syncing notes in {LECTURES_DIR} to Git repository...")

    # Stage all markdown notes and assets
    ok_add, out_add = run_git_cmd(["git", "add", "."], LECTURES_DIR)
    if not ok_add:
        return False, f"Git add failed: {out_add}"

    # Commit
    ok_commit, out_commit = run_git_cmd(["git", "commit", "-m", commit_message], LECTURES_DIR)
    
    # Try pushing to remote if configured
    repo_url = os.environ.get("GIT_VAULT_REPO_URL", "").strip()
    if repo_url:
        for attempt in range(1, 4):
            # Fetch and rebase with remote to resolve ref lock race conditions
            run_git_cmd(["git", "fetch", "origin", GIT_BRANCH], LECTURES_DIR)
            run_git_cmd(["git", "pull", "--rebase", "origin", GIT_BRANCH], LECTURES_DIR)
            ok_push, out_push = run_git_cmd(["git", "push", "-u", "origin", GIT_BRANCH], LECTURES_DIR)
            if ok_push:
                print(f"[+] Successfully synced notes to Obsidian Git repo on '{GIT_BRANCH}'!")
                return True, "Synced to remote Git repo"
            else:
                if "cannot lock ref" in out_push or "fetch first" in out_push:
                    time.sleep(2)
                    continue
                print(f"[!] Warning: Remote push pending auth/setup ({out_push}). Local commit saved.")
                return True, f"Committed locally (remote push pending auth): {out_push}"
    
    return True, "Committed locally"

if __name__ == "__main__":
    init_vault_git()
    success, msg = sync_notes_to_git("Initial repository sync")
    print(f"Status: {msg}")
