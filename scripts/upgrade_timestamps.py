"""Upgrade pending OpenTimestamps proofs under audit/timestamps/ to their
Bitcoin-confirmed form, once the confirmation has had time to land.

An OpenTimestamps stamp (scripts/timestamp_anchor.py) is provisional the
moment it's created: the calendar server has accepted the digest but it
hasn't been included in a Bitcoin block yet (that takes anywhere from
minutes to hours). This script re-queries each calendar for every
still-pending local proof and, if a Bitcoin attestation is now available,
merges it in and rewrites the local .ots file plus re-pushes it to the
`anchors` branch. Safe to run repeatedly - proofs that are already fully
confirmed are skipped, and nothing changes if nothing upgraded this time.

Run this manually after a while, or on a schedule (e.g. a daily cron/task).
Not run automatically by timestamp_anchor.py itself, since the upgrade
almost never succeeds within the few seconds after stamping.

Usage:
  uv run python scripts/upgrade_timestamps.py
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from scripts._anchor_git import REPO_ROOT, publish_files
from scripts._ots import deserialize_ots, is_confirmed, serialize_ots, upgrade

load_dotenv(REPO_ROOT / ".env")
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

    if not TIMESTAMPS_DIR.exists():
        print(f"{TIMESTAMPS_DIR} doesn't exist yet - run scripts/timestamp_anchor.py first.")
        return 0

    ots_paths = sorted(TIMESTAMPS_DIR.glob("*.jsonl.ots"))
    if not ots_paths:
        print("No .ots proofs found under audit/timestamps/.")
        return 0

    upgraded_any = False
    for ots_path in ots_paths:
        data = ots_path.read_bytes()
        detached = deserialize_ots(data)
        digest = detached.file_digest

        if is_confirmed(detached.timestamp):
            print(f"{ots_path.name}: already confirmed, skipping.")
            continue

        print(f"{ots_path.name}: still pending, checking calendars...")
        changed = upgrade(detached.timestamp, digest)
        if not changed:
            print(f"{ots_path.name}: no update available yet.")
            continue

        new_bytes = serialize_ots(digest, detached.timestamp)
        ots_path.write_bytes(new_bytes)
        confirmed_now = is_confirmed(detached.timestamp)
        print(
            f"{ots_path.name}: proof updated "
            f"({'now confirmed' if confirmed_now else 'still pending, but calendar data changed'})."
        )

        message = (
            f"Timestamp upgrade: {datetime.now(timezone.utc).isoformat()}\n\n"
            f"Pushed by scripts/upgrade_timestamps.py for {ots_path.name}."
        )
        publish_files(
            branch=ANCHOR_BRANCH,
            files={ots_path.name: ots_path},
            author_name=ANCHOR_AUTHOR_NAME,
            author_email=ANCHOR_AUTHOR_EMAIL,
            message=message,
            token=token,
        )
        upgraded_any = True

    if not upgraded_any:
        print("Nothing upgraded this run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
