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
whatever branch you currently have checked out (see scripts/_anchor_git.py
for the git-plumbing details and why it preserves other files already on
the `anchors` branch, such as the OpenTimestamps snapshots published by
scripts/timestamp_anchor.py).
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from scripts._anchor_git import REPO_ROOT, publish_files

load_dotenv(REPO_ROOT / ".env")
ANCHOR_FILE = REPO_ROOT / "audit" / "chain_anchors.jsonl"
ANCHOR_BRANCH = "anchors"
ANCHOR_PATH_IN_TREE = "chain_anchors.jsonl"
ANCHOR_AUTHOR_NAME = "agent-governance-anchor-bot"
ANCHOR_AUTHOR_EMAIL = "anchor-bot@users.noreply.github.com"


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

    message = (
        f"Anchor publish: {datetime.now(timezone.utc).isoformat()}\n\n"
        "Pushed by scripts/push_anchor.py using a scoped credential, "
        "deliberately not the operator's normal git identity."
    )

    new_commit_sha = publish_files(
        branch=ANCHOR_BRANCH,
        files={ANCHOR_PATH_IN_TREE: ANCHOR_FILE},
        author_name=ANCHOR_AUTHOR_NAME,
        author_email=ANCHOR_AUTHOR_EMAIL,
        message=message,
        token=token,
    )

    if new_commit_sha is None:
        print("No new anchor entries since the last publish; nothing to push.")
        return 0

    print(f"Pushed {new_commit_sha} to {ANCHOR_BRANCH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
