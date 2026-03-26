"""
Git hook for Memora — extracts decisions from commits automatically.

Install as a post-commit hook:
    python -m memora.git_hook install
    python -m memora.git_hook run          # called by the hook itself

The hook reads the latest commit's diff and message, extracts decisions
via AI, and stores them in Memora.
"""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from memora.memory import MemoraMemory

load_dotenv()

HOOK_SCRIPT = """#!/bin/sh
# Memora post-commit hook — extracts decisions from commits
python -m memora.git_hook run 2>/dev/null &
"""


def install_hook(repo_dir: str = "."):
    repo_path = Path(repo_dir).resolve()
    hooks_dir = repo_path / ".git" / "hooks"

    if not hooks_dir.exists():
        print(f"Not a git repository: {repo_path}", file=sys.stderr)
        sys.exit(1)

    hook_file = hooks_dir / "post-commit"

    if hook_file.exists():
        existing = hook_file.read_text(encoding="utf-8")
        if "memora" in existing.lower():
            print("Memora hook already installed.")
            return str(hook_file)
        hook_file.write_text(existing.rstrip() + "\n\n" + HOOK_SCRIPT, encoding="utf-8")
        print(f"Appended Memora hook to existing {hook_file}")
    else:
        hook_file.write_text(HOOK_SCRIPT, encoding="utf-8")
        print(f"Created Memora hook at {hook_file}")

    hook_file.chmod(0o755)
    return str(hook_file)


def uninstall_hook(repo_dir: str = "."):
    repo_path = Path(repo_dir).resolve()
    hook_file = repo_path / ".git" / "hooks" / "post-commit"

    if not hook_file.exists():
        print("No post-commit hook found.")
        return

    content = hook_file.read_text(encoding="utf-8")
    if "memora" not in content.lower():
        print("Memora hook not found in post-commit.")
        return

    cleaned = content.replace(HOOK_SCRIPT, "").strip()
    if cleaned and cleaned != "#!/bin/sh":
        hook_file.write_text(cleaned + "\n", encoding="utf-8")
        print("Removed Memora hook (kept other hooks).")
    else:
        hook_file.unlink()
        print("Removed post-commit hook.")


def run_hook():
    try:
        commit_msg = subprocess.check_output(
            ["git", "log", "-1", "--pretty=%B"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        return

    try:
        diff = subprocess.check_output(
            ["git", "diff", "HEAD~1", "HEAD", "--stat", "-p"], text=True, stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        diff = ""

    if not commit_msg and not diff:
        return

    try:
        repo_name = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        project = Path(repo_name).name
    except subprocess.CalledProcessError:
        project = ""

    max_diff_len = 8000
    if len(diff) > max_diff_len:
        diff = diff[:max_diff_len] + "\n... (truncated)"

    mem = MemoraMemory(
        db_path=os.getenv("MEMORA_DB_PATH"),
        api_key=os.getenv("GROQ_API_KEY"),
    )

    results = mem.extract_from_diff_and_store(
        diff=diff,
        commit_message=commit_msg,
        project=project,
        agent="git-committer",
    )

    if results:
        print(f"Memora: extracted {len(results)} decision(s) from commit")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m memora.git_hook install   Install the post-commit hook")
        print("  python -m memora.git_hook uninstall  Remove the hook")
        print("  python -m memora.git_hook run        Run extraction on latest commit")
        sys.exit(1)

    command = sys.argv[1]
    if command == "install":
        repo = sys.argv[2] if len(sys.argv) > 2 else "."
        install_hook(repo)
    elif command == "uninstall":
        repo = sys.argv[2] if len(sys.argv) > 2 else "."
        uninstall_hook(repo)
    elif command == "run":
        run_hook()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
