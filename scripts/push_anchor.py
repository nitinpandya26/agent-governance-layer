"""Publish audit/chain_anchors.jsonl to a dedicated `anchors` branch using a
credential that is deliberately NOT the operator's normal git/GitHub identity.

Why this exists (see docs/linkedin_feedback.md, Siddharth Chudasama's
follow-up on the Phase 2 post): an anchor only protects against tampering by
an actor who can't also rewrite the anchor. If the same person/credentials
that can write the database also push the anchor commits, the anchor proves
nothing against that person. This script pushes with a separate, narrowly
scoped GitHub token (ANCHOR_GIT_TOKEN) instead of your normal `git`/`gh`
credentials, and commits as a distinct author identity, so the DB-access
path and the anchor-write path are genuinely different credentials.

What it does NOT solve: a full compromise of this machine (the one place
both the DB and this token live) can still get both. See the README's
"Why the hash chain matters" section for that caveat stated explicitly -
don't oversell this script as closing that gap, it only closes the
narrower one (a leaked/abused DB credential, or a bug that only reaches
the DB, cannot also rewrite the anchor).

Setup (one-time):
  1. Create a fine-grained GitHub personal access token scoped ONLY to this
     repo, with "Contents: Read and write" permission and nothing else.
     Do not reuse your normal PAT/OAuth session for this - a token with
     broader scope or access to other repos defeats the point.
  2. Set it as ANCHOR_GIT_TOKEN in your environment (or .env; already
     gitignored). Never commit it, never log it.

Usage:
  uv run python scripts/push_anchor.py

Safe to run anytime: it never touches your working tree, index, or
whatever branch you currently have checked out. It operates entirely via
git plumbing (hash-object / mktree / commit-tree) against the local repo's
object database and pushes a single ref update directly to the remote.
"""
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")
ANCHOR_FILE = REPO_ROOT / "audit" / "chain_anchors.jsonl"
ANCHOR_BRANCH = "anchors"
ANCHOR_PATH_IN_TREE = "chain_anchors.jsonl"
ANCHOR_AUTHOR_NAME = "agent-governance-anchor-bot"
ANCHOR_AUTHOR_EMAIL = "anchor-bot@users.noreply.github.com"


def _git(*args: str, env: dict | None = None) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout.strip()


def _remote_url_with_token(token: str) -> str:
    origin = _git("remote", "get-url", "origin")
    if not origin.startswith("https://"):
        raise RuntimeError(
            f"origin remote ({origin}) is not an https:// URL; this script "
            "only knows how to inject a token into an https remote."
        )
    # https://github.com/owner/repo.git -> https://x-access-token:TOKEN@github.com/owner/repo.git
    return origin.replace("https://", f"https://x-access-token:{token}@", 1)


def main() -> int:
    token = os.environ.get("ANCHOR_GIT_TOKEN")
    if not token:
        print(
            "ANCHOR_GIT_TOKEN is not set. See scripts/push_anchor.py's module "
            "docstring for how to create a scoped token. Refusing to fall "
            "back to your normal git credentials, since that would defeat "
            "the point of this script.",
            file=sys.stderr,
        )
        return 1

    if not ANCHOR_FILE.exists():
        print(f"{ANCHOR_FILE} does not exist yet; nothing to publish.", file=sys.stderr)
        return 1

    remote_url = _remote_url_with_token(token)

    # Find the current tip of the anchors branch on the remote, if it
    # already exists. Empty string means this is the first push.
    ls_remote = _git("ls-remote", remote_url, f"refs/heads/{ANCHOR_BRANCH}")
    parent_sha = ls_remote.split()[0] if ls_remote else None

    # Build a blob for the anchor file's current content.
    with open(ANCHOR_FILE, "rb") as f:
        blob_sha = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=REPO_ROOT, input=f.read(), capture_output=True, check=True,
        ).stdout.decode().strip()

    # Build a tree containing just that one file.
    mktree_input = f"100644 blob {blob_sha}\t{ANCHOR_PATH_IN_TREE}\n"
    tree_sha = subprocess.run(
        ["git", "mktree"],
        cwd=REPO_ROOT, input=mktree_input.encode(), capture_output=True, check=True,
    ).stdout.decode().strip()

    # If the tree is identical to the parent commit's tree, there's nothing
    # new to anchor - skip the push instead of making an empty commit.
    if parent_sha:
        parent_tree = _git("rev-parse", f"{parent_sha}^{{tree}}")
        if parent_tree == tree_sha:
            print("No new anchor entries since the last publish; nothing to push.")
            return 0

    commit_env = os.environ.copy()
    commit_env.update({
        "GIT_AUTHOR_NAME": ANCHOR_AUTHOR_NAME,
        "GIT_AUTHOR_EMAIL": ANCHOR_AUTHOR_EMAIL,
        "GIT_COMMITTER_NAME": ANCHOR_AUTHOR_NAME,
        "GIT_COMMITTER_EMAIL": ANCHOR_AUTHOR_EMAIL,
    })

    message = (
        f"Anchor publish: {datetime.now(timezone.utc).isoformat()}\n\n"
        "Pushed by scripts/push_anchor.py using a scoped credential, "
        "deliberately not the operator's normal git identity."
    )

    commit_args = ["commit-tree", tree_sha, "-m", message]
    if parent_sha:
        commit_args = ["commit-tree", tree_sha, "-p", parent_sha, "-m", message]

    new_commit_sha = _git(*commit_args, env=commit_env)

    _git("push", remote_url, f"{new_commit_sha}:refs/heads/{ANCHOR_BRANCH}")

    print(f"Pushed {new_commit_sha} to {ANCHOR_BRANCH} (parent: {parent_sha or 'none, first push'}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
