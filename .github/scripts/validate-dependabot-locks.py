"""Validate regenerated lock files and prepare a guarded commit request."""

import base64
import json
import os
import re
import subprocess
from pathlib import Path

HASH_LINE = rb"^([ \t]+--hash=sha256:[0-9a-f]{64})( \\\n|\n|$)"
HASH_BLOCK = re.compile(rb"(?:" + HASH_LINE + rb")+", re.MULTILINE)
LOCK_HEADER = re.compile(rb"\A(?:#[^\n]*\n)+")
BINARY_ONLY_OPTION = b"--only-binary :all:\n\n"
COMMIT_MUTATION = """
mutation Repair($input: CreateCommitOnBranchInput!) {
  createCommitOnBranch(input: $input) { commit { oid url } }
}
"""


def api(endpoint: str) -> dict:
    """Read GitHub metadata using the workflow token."""
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


def lock_contents(repo: str, path: str, sha: str) -> bytes:
    """Read an existing lock at a specific commit."""
    original = api(f"repos/{repo}/contents/{path}?ref={sha}")
    if original["type"] != "file" or original["encoding"] != "base64":
        raise SystemExit(f"Cannot verify {path}")
    return base64.b64decode(original["content"])


def restores_binary_option(expected: bytes, candidate: bytes, base: bytes) -> bool:
    """Allow restoring only the canonical Linux option present in the base lock."""
    header = LOCK_HEADER.match(expected)
    base_header = LOCK_HEADER.match(base)
    if not header or not base_header or not base[base_header.end() :].startswith(BINARY_ONLY_OPTION):
        return False
    position = header.end()
    return (
        BINARY_ONLY_OPTION.rstrip() not in expected.splitlines()
        and candidate == expected[:position] + BINARY_ONLY_OPTION + expected[position:]
    )


def main() -> None:
    """Validate the artifact before preparing a commit request."""
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
    if not names or len(names) != len(set(names)) or any(
        not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) for name in names
    ):
        raise SystemExit("Invalid lock file selection")
    folder = Path(os.environ["RUNNER_TEMP"]) / "regenerated-locks"
    if {p.name for p in folder.iterdir()} != {f"{name}.txt" for name in names}:
        raise SystemExit("Unexpected artifact files")
    additions = []
    removed_duplicates = False
    for name in names:
        artifact = folder / f"{name}.txt"
        if artifact.is_symlink() or not artifact.is_file() or artifact.stat().st_size > 1_000_000:
            raise SystemExit("Invalid lock artifact")
        path = f"requirements/{artifact.name}"
        before = lock_contents(repo, path, head)
        after = artifact.read_bytes()
        expected = HASH_BLOCK.sub(deduplicate, before)
        if after != expected and not (
            os.environ.get("COMPILE_PROFILE") == "linux-wheel-cp311"
            and restores_binary_option(expected, after, lock_contents(repo, path, pr["base"]["sha"]))
        ):
            raise SystemExit(f"{path}: unexpected changes in regenerated lock")
        if before != after:
            removed_duplicates |= before != expected
            additions.append({"path": path, "contents": base64.b64encode(after).decode("ascii")})

    if removed_duplicates:
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
        print("No duplicate hashes to repair; no commit needed.")


if __name__ == "__main__":
    main()
