"""Git bundle creation, verification, metadata, and restore checks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class BackupArtifacts:
    bundle_path: Path
    sha256_path: Path
    metadata_path: Path
    remote_prefix: str


def build_artifacts(workspace: Path, backup_prefix: str, bundle_name: str) -> BackupArtifacts:
    if not bundle_name or "/" in bundle_name or "\\" in bundle_name:
        raise ValueError("bundle-name must be a non-empty file name without slashes.")

    normalized_prefix = backup_prefix.strip("/")
    if not normalized_prefix:
        raise ValueError("backup-prefix must not be empty.")

    repository = require_env("GITHUB_REPOSITORY")
    if "/" not in repository:
        raise ValueError("GITHUB_REPOSITORY must be in owner/repo form.")
    repo_owner, repo_name = repository.split("/", 1)

    output_dir = workspace / "out"
    output_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    date_path = now.strftime("%Y/%m/%d")
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    run_key = "-".join(
        [
            timestamp,
            require_env("GITHUB_RUN_ID"),
            require_env("GITHUB_RUN_ATTEMPT"),
        ]
    )
    remote_prefix = (
        f"{normalized_prefix}/{repo_owner}/{repo_name}/{date_path}/{run_key}"
    )

    return BackupArtifacts(
        bundle_path=output_dir / bundle_name,
        sha256_path=output_dir / f"{bundle_name}.sha256",
        metadata_path=output_dir / "metadata.json",
        remote_prefix=remote_prefix,
    )


def fetch_all_refs(workspace: Path) -> None:
    run_git(
        "fetch",
        "--force",
        "--prune",
        "--tags",
        "origin",
        "+refs/heads/*:refs/remotes/origin/*",
        cwd=workspace,
    )


def create_and_verify_bundle(workspace: Path, bundle_path: Path) -> None:
    run_git("bundle", "create", str(bundle_path), "--all", cwd=workspace)
    run_git("bundle", "verify", str(bundle_path), cwd=workspace)


def write_checksum(path: Path, sha256_path: Path) -> str:
    sha256 = sha256_file(path)
    sha256_path.write_text(f"{sha256}  {path.name}\n", encoding="utf-8")
    return sha256


def write_metadata(
    workspace: Path,
    artifacts: BackupArtifacts,
    bundle_sha256: str,
) -> None:
    metadata = {
        "backup_created_at": datetime.now(timezone.utc).isoformat(),
        "bundle_file": artifacts.bundle_path.name,
        "bundle_size_bytes": artifacts.bundle_path.stat().st_size,
        "bundle_sha256": bundle_sha256,
        "git_head": run_git("rev-parse", "HEAD", cwd=workspace, log_output=False),
        "git_repository": require_env("GITHUB_REPOSITORY"),
        "github_run_attempt": require_env("GITHUB_RUN_ATTEMPT"),
        "github_run_id": require_env("GITHUB_RUN_ID"),
        "github_run_number": require_env("GITHUB_RUN_NUMBER"),
        "remote_prefix": artifacts.remote_prefix,
        "refs": run_git(
            "bundle",
            "list-heads",
            str(artifacts.bundle_path),
            cwd=workspace,
            log_output=False,
        ).splitlines(),
    }
    artifacts.metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def smoke_test_restore(workspace: Path, bundle_path: Path) -> None:
    temp_root = Path(tempfile.mkdtemp(prefix="repo-backup-restore-", dir=workspace))
    try:
        restore_path = temp_root / "repo"
        run("git", "clone", str(bundle_path), str(restore_path), cwd=workspace)
        run_git("-C", str(restore_path), "fsck", "--strict", cwd=workspace)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def write_github_outputs(artifacts: BackupArtifacts) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT", "")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"remote-prefix={artifacts.remote_prefix}\n")
        handle.write(f"bundle-path={artifacts.bundle_path}\n")
        handle.write(f"sha256-path={artifacts.sha256_path}\n")
        handle.write(f"metadata-path={artifacts.metadata_path}\n")


def require_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"{name} is required.")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(*args: str, cwd: Path, log_output: bool = True) -> str:
    return run("git", *args, cwd=cwd, log_output=log_output)


def run(*args: str, cwd: Path, log_output: bool = True) -> str:
    completed = subprocess.run(
        list(args),
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    output = redact_credentials(completed.stdout.strip())
    if output and log_output:
        print(output)
    return output


def redact_credentials(text: str) -> str:
    return re.sub(r"https://[^/@\s]+@", "https://***@", text)
