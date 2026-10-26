"""Stamp the current chain-anchor file with an independent OpenTimestamps
proof, on top of (not instead of) the git anchor from scripts/push_anchor.py.

Why this exists (see docs/linkedin_feedback.md, Siddharth Chudasama's third
round of feedback): a git anchor proves a chain head existed in git history
as of a given commit - which is only as trustworthy as GitHub's own
timestamps and the repo's history not being rewritten. OpenTimestamps adds a
genuinely independent layer: proof the head existed before a specific,
Bitcoin-anchored point in time that nobody with any amount of access to this
repo or its GitHub account can retroactively alter. Free, no account needed,
no RFC 3161 trusted-timestamp-authority relationship required.

Design note: audit/chain_anchors.jsonl keeps growing as new runs finish, so
stamping that live file directly would be meaningless - the proof would only
ever cover whatever happened to be in the file at that instant, with no
record of what that was. Instead this script takes an immutable snapshot
(a timestamped copy of the file as of right now) and stamps *that*, so the
snapshot + its .ots proof together are a permanent, self-contained record:
"this exact set of chain heads existed by this point in time." Multiple
snapshots accumulate over time in audit/timestamps/, both locally and on the
`anchors` branch.

Usage:
  uv run python scripts/timestamp_anchor.py

Requires ANCHOR_GIT_TOKEN (same scoped credential as push_anchor.py) to push
the snapshot + proof to the `anchors` branch, and makes real network calls to
public OpenTimestamps calendar servers. Safe to run anytime - like
push_anchor.py, it never touches your working tree, index, or currently
checked out branch when pushing; it does write two new files under
audit/timestamps/ locally, which you should commit to this branch yourself
(same as audit/chain_anchors.jsonl) so the local record matches what's on
`anchors`.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from scripts._anchor_git import REPO_ROOT, publish_files
from scripts._ots import is_confirmed, pending_calendar_urls, serialize_ots, sha256_file, stamp_digest

load_dotenv(REPO_ROOT / ".env")
ANCHOR_FILE = REPO_ROOT / "audit" / "chain_anchors.jsonl"
TIMESTAMPS_DIR = REPO_ROOT / "audit" / "timestamps"
ANCHOR_BRANCH = "anchors"
ANCHOR_AUTHOR_NAME = "agent-governance-anchor-bot"
ANCHOR_AUTHOR_EMAIL = "anchor-bot@users.noreply.github.com"


def main() -> int:
    token = os.environ.get("ANCHOR_GIT_TOKEN")
    if not token:
        print(
            "ANCHOR_GIT_TOKEN is not set. See scripts/push_anchor.py's module "
            "docstring for how to create a scoped token.",
            file=sys.stderr,
        )
        return 1

    if not ANCHOR_FILE.exists():
        print(f"{ANCHOR_FILE} does not exist yet; nothing to snapshot.", file=sys.stderr)
        return 1

    TIMESTAMPS_DIR.mkdir(parents=True, exist_ok=True)

    stamp_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_name = f"anchors_{stamp_name}.jsonl"
    snapshot_path = TIMESTAMPS_DIR / snapshot_name
    snapshot_bytes = ANCHOR_FILE.read_bytes()
    snapshot_path.write_bytes(snapshot_bytes)

    digest = sha256_file(snapshot_path)
    print(f"Stamping {snapshot_name} ({len(snapshot_bytes)} bytes)...")
    try:
        timestamp = stamp_digest(digest)
    except RuntimeError as exc:
        print(f"Stamping failed: {exc}", file=sys.stderr)
        return 1

    ots_bytes = serialize_ots(digest, timestamp)
    ots_path = TIMESTAMPS_DIR / f"{snapshot_name}.ots"
    ots_path.write_bytes(ots_bytes)

    print(
        f"Stamped by: {sorted(pending_calendar_urls(timestamp)) or '(already confirmed)'}"
    )
    print(
        "Confirmed yet: "
        + ("yes" if is_confirmed(timestamp) else "no (pending - run scripts/upgrade_timestamps.py later)")
    )

    message = (
        f"Timestamp publish: {datetime.now(timezone.utc).isoformat()}\n\n"
        "Pushed by scripts/timestamp_anchor.py using the same scoped "
        "credential as scripts/push_anchor.py."
    )
    new_commit_sha = publish_files(
        branch=ANCHOR_BRANCH,
        files={snapshot_name: snapshot_path, f"{snapshot_name}.ots": ots_path},
        author_name=ANCHOR_AUTHOR_NAME,
        author_email=ANCHOR_AUTHOR_EMAIL,
        message=message,
        token=token,
    )

    if new_commit_sha is None:
        print("Nothing changed on the anchors branch (unexpected for a new snapshot).")
        return 0

    print(f"Pushed {new_commit_sha} to {ANCHOR_BRANCH}.")
    print(
        f"Local files written: {snapshot_path.relative_to(REPO_ROOT)}, "
        f"{ots_path.relative_to(REPO_ROOT)} - commit these to this branch too."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
