"""Commit and push updated webpage files."""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    """Raised when a git command fails."""


def _run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise GitError(f"git {' '.join(args)} failed: {detail}")
    return completed


def commit_and_push(
    repo_root: Path,
    files: list[str],
    message: str,
    remote: str = "origin",
    branch: str | None = None,
) -> dict:
    """
    Stage the given files, commit if they changed, and push.

    Returns:
        {"committed": bool, "pushed": bool, "sha": str | None}
    """
    repo_root = Path(repo_root)
    _run_git(repo_root, "add", "--", *files)

    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=repo_root,
    )
    if diff.returncode == 0:
        return {"committed": False, "pushed": False, "sha": None}

    _run_git(repo_root, "commit", "-m", message)
    sha = _run_git(repo_root, "rev-parse", "HEAD").stdout.strip()

    push_args = ["push", remote]
    if branch:
        push_args.extend(["HEAD:refs/heads/" + branch])
    else:
        push_args.append("HEAD")
    _run_git(repo_root, *push_args)

    return {"committed": True, "pushed": True, "sha": sha}
