"""Shared git-plumbing helpers for publishing files to the `anchors` branch
with a scoped credential that is deliberately NOT the operator's normal
git/GitHub identity (see scripts/push_anchor.py's module docstring for why
that separation matters).

Originally this lived inline in push_anchor.py as a single-file publisher.
It's pulled out here because scripts/timestamp_anchor.py needs to publish a
*second* kind of file (OTS snapshots + proofs) to the same branch, and the
original single-entry `mktree` call built the whole tree from scratch every
time — fine when only one file ever lived there, but it would silently
delete any other file already on the branch the moment a second file type
showed up. `publish_files()` instead reads the branch's current tree and
overlays only the files being published, so unrelated files survive.

Nothing here touches the caller's working tree, index, or currently checked
out branch — it operates entirely via git plumbing (ls-remote / ls-tree /
hash-object / mktree / commit-tree) against the local repo's object
database, then pushes a single ref update directly to the remote.
"""
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str, env: dict | None = None, input_bytes: bytes | None = None) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, input=input_bytes, env=env,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace") if isinstance(result.stderr, bytes) else result.stderr
        raise RuntimeError(f"git {' '.join(args)} failed:\n{stderr}")
    stdout = result.stdout
    return stdout.decode().strip() if isinstance(stdout, bytes) else stdout.strip()


def remote_url_with_token(token: str) -> str:
    origin = _git("remote", "get-url", "origin")
    if not origin.startswith("https://"):
        raise RuntimeError(
            f"origin remote ({origin}) is not an https:// URL; this helper "
            "only knows how to inject a token into an https remote."
        )
    # https://github.com/owner/repo.git -> https://x-access-token:TOKEN@github.com/owner/repo.git
    return origin.replace("https://", f"https://x-access-token:{token}@", 1)


def _remote_branch_tip(remote_url: str, branch: str) -> str | None:
    ls_remote = _git("ls-remote", remote_url, f"refs/heads/{branch}")
    return ls_remote.split()[0] if ls_remote else None


def _existing_tree_entries(commit_sha: str | None) -> dict[str, tuple[str, str]]:
    """{path: (mode, blob_sha)} for every file at commit_sha, or {} if there
    is no parent commit yet (first publish to this branch)."""
    if commit_sha is None:
        return {}
    listing = _git("ls-tree", "-r", commit_sha)
    entries: dict[str, tuple[str, str]] = {}
    for line in listing.splitlines():
        if not line:
            continue
        meta, path = line.split("\t", 1)
        mode, _type, blob_sha = meta.split(" ")
        entries[path] = (mode, blob_sha)
    return entries


def publish_files(
    branch: str,
    files: dict[str, Path],
    author_name: str,
    author_email: str,
    message: str,
    token: str,
) -> str | None:
    """Publish `files` ({branch_path: local_file_path}) to `branch` on the
    remote, preserving any other file already on that branch. Returns the
    new commit sha, or None if nothing changed (tree identical to parent,
    so the push is skipped rather than making an empty commit)."""
    remote_url = remote_url_with_token(token)
    parent_sha = _remote_branch_tip(remote_url, branch)
    entries = _existing_tree_entries(parent_sha)

    for branch_path, local_path in files.items():
        with open(local_path, "rb") as f:
            blob_sha = _git("hash-object", "-w", "--stdin", input_bytes=f.read())
        entries[branch_path] = ("100644", blob_sha)

    mktree_input = "".join(
        f"{mode} blob {blob_sha}\t{path}\n" for path, (mode, blob_sha) in sorted(entries.items())
    )
    tree_sha = _git("mktree", input_bytes=mktree_input.encode())

    if parent_sha:
        parent_tree = _git("rev-parse", f"{parent_sha}^{{tree}}")
        if parent_tree == tree_sha:
            return None

    commit_env = os.environ.copy()
    commit_env.update({
        "GIT_AUTHOR_NAME": author_name,
        "GIT_AUTHOR_EMAIL": author_email,
        "GIT_COMMITTER_NAME": author_name,
        "GIT_COMMITTER_EMAIL": author_email,
    })

    commit_args = ["commit-tree", tree_sha, "-m", message]
    if parent_sha:
        commit_args = ["commit-tree", tree_sha, "-p", parent_sha, "-m", message]
    new_commit_sha = _git(*commit_args, env=commit_env)

    _git("push", remote_url, f"{new_commit_sha}:refs/heads/{branch}")
    return new_commit_sha
