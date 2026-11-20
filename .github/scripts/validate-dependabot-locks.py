"""Validate regenerated lock files and prepare a guarded commit request."""

import base64
import json
import os
import re
import subprocess
from pathlib import Path

HASH_LINE = rb"^([ \t]+--hash=sha256:[0-9a-f]{64})( \\\n|\n|$)"
HASH_BLOCK = re.compile(rb"(?:" + HASH_LINE + rb")+", re.MULTILINE)
COMMIT_MUTATION = """
mutation Repair($input: CreateCommitOnBranchInput!) {
  createCommitOnBranch(input: $input) { commit { oid url } }
}
"""


def api(endpoint: str) -> dict:
    """Read GitHub metadata using the job's read-only token."""
    return json.loads(subprocess.check_output(["gh", "api", endpoint]))


def deduplicate(block: re.Match[bytes]) -> bytes:
    """Remove repeated hash lines while preserving block order and termination."""
    lines = re.findall(HASH_LINE, block[0], re.MULTILINE)
    unique = list(dict.fromkeys(line for line, _ in lines))
    if len(unique) == len(lines):
        return block[0]
    if any(ending != b" \\\n" for _, ending in lines[:-1]):
        raise SystemExit("Unexpected hash continuation; refusing to publish")
    return b" \\\n".join(unique) + lines[-1][1]


def main() -> None:
    """Validate the artifact without access to the App's write credential."""
    repo = os.environ["GITHUB_REPOSITORY"]
    head = os.environ["PR_HEAD"]
    branch = os.environ["PR_BRANCH"]
    pr = api(f"repos/{repo}/pulls/{os.environ['PR_NUMBER']}")
    if not (
        pr["state"] == "open"
        and pr["user"]["id"] == 49699333
        and (pr["head"]["repo"] or {}).get("full_name") == repo
        and pr["head"]["ref"] == branch
        and branch.startswith("dependabot/pip/")
        and pr["head"]["sha"] == head
        and any(label["name"] == "regenerate-locks" for label in pr["labels"])
    ):
        raise SystemExit("PR is no longer eligible or its head has moved")

    names = os.environ["LOCK_NAMES"].split()
    if not names or len(names) != len(set(names)) or set(names) - {"base", "dev", "tools"}:
        raise SystemExit("Invalid lock file selection")
    folder = Path(os.environ["RUNNER_TEMP"]) / "regenerated-locks"
    if {p.name for p in folder.iterdir()} != {f"{name}.txt" for name in names}:
        raise SystemExit("Unexpected artifact files")
    additions = []
    for name in names:
        artifact = folder / f"{name}.txt"
        if artifact.is_symlink() or not artifact.is_file() or artifact.stat().st_size > 1_000_000:
            raise SystemExit("Invalid lock artifact")
        path = f"requirements/{artifact.name}"
        original = api(f"repos/{repo}/contents/{path}?ref={head}")
        if original["type"] != "file" or original["encoding"] != "base64":
            raise SystemExit(f"Cannot verify {path}")
        before = base64.b64decode(original["content"])
        after = artifact.read_bytes()
        if before == after:
            continue
        if after != HASH_BLOCK.sub(deduplicate, before):
            raise SystemExit(f"{path}: changes are not limited to removing duplicate hashes")
        additions.append({"path": path, "contents": base64.b64encode(after).decode("ascii")})

    if additions:
        request = {
            "query": COMMIT_MUTATION,
            "variables": {
                "input": {
                    "branch": {"repositoryNameWithOwner": repo, "branchName": branch},
                    "expectedHeadOid": head,
                    "message": {"headline": "Remove duplicate dependency lock hashes"},
                    "fileChanges": {"additions": additions},
                },
            },
        }
        target = Path(os.environ["RUNNER_TEMP"]) / "lock-commit.json"
        target.write_text(json.dumps(request), encoding="utf-8")
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            print("changed=true", file=output)
    else:
        print("Locks already match; no commit needed.")


if __name__ == "__main__":
    main()
