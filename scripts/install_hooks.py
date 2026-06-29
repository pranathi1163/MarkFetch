"""
Install local Git hooks for documentation generation.

This creates `pre-commit` and `pre-push` hooks that run
`scripts/pre_commit_doc_updater.py` before committing or pushing.
"""

import os
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GIT_HOOKS = ROOT / ".git" / "hooks"
SCRIPT_PATH = ROOT / "scripts" / "pre_commit_doc_updater.py"

HOOK_TEMPLATE = """#!/usr/bin/env bash
python \"{script}\"
RESULT=$?
if [ $RESULT -ne 0 ]; then
  echo "[doc hook] Documentation update failed. Abort."
  exit $RESULT
fi
"""


def write_hook(name: str) -> None:
    hook_path = GIT_HOOKS / name
    content = HOOK_TEMPLATE.format(script=SCRIPT_PATH.as_posix())
    hook_path.write_text(content, encoding="utf-8")
    mode = hook_path.stat().st_mode
    hook_path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Installed hook: {hook_path.relative_to(ROOT)}")


def main() -> int:
    if not GIT_HOOKS.exists():
        print("Error: .git/hooks directory not found. Run this inside a git repo.")
        return 1

    write_hook("pre-commit")
    write_hook("pre-push")
    print("Git hooks installed. Use 'git commit' or 'git push' normally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
