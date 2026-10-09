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
from typing import Mapping


@dataclass(frozen=True)
class BackupArtifacts:
    bundle_path: Path
    sha256_path: Path
    metadata_path: Path
    remote_prefix: str


def repository_prefix(backup_prefix: str) -> str:
    normalized_prefix = backup_prefix.strip("/")
    if not normalized_prefix:
        raise ValueError("backup-prefix must not be empty.")
    repository = require_env("GITHUB_REPOSITORY")
    if "/" not in repository:
        raise ValueError("GITHUB_REPOSITORY must be in owner/repo form.")
    return f"{normalized_prefix}/{repository}"


def monthly_full_prefix(backup_prefix: str, now: datetime) -> str:
    return f"{repository_prefix(backup_prefix)}/{now:%Y/%m}/full/"


def build_artifacts(
    workspace: Path,
    backup_prefix: str,
    bundle_name: str,
    backup_type: str,
    now: datetime,
) -> BackupArtifacts:
    if not bundle_name or "/" in bundle_name or "\\" in bundle_name:
        raise ValueError("bundle-name must be a non-empty file name without slashes.")
    if backup_type not in {"full", "incremental"}:
        raise ValueError("backup_type must be full or incremental.")

    output_dir = workspace / "out"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    run_key = "-".join(
        [
            timestamp,
            require_env("GITHUB_RUN_ID"),
            require_env("GITHUB_RUN_ATTEMPT"),
        ]
    )
    parent = (
        monthly_full_prefix(backup_prefix, now).rstrip("/")
        if backup_type == "full"
        else f"{repository_prefix(backup_prefix)}/{now:%Y/%m/%d}"
    )
    remote_prefix = f"{parent}/{run_key}"

    return BackupArtifacts(
        bundle_path=output_dir / bundle_name,
        sha256_path=output_dir / f"{bundle_name}.sha256",
        metadata_path=output_dir / "metadata.json",
        remote_prefix=remote_prefix,
    )


def fetch_all_refs(workspace: Path) -> None:
    is_shallow = run_git(
        "rev-parse",
        "--is-shallow-repository",
        cwd=workspace,
        log_output=False,
    ).strip()
    if is_shallow == "true":
        run_git("fetch", "--unshallow", "--tags", "origin", cwd=workspace)

    run_git(
        "fetch",
        "--force",
        "--prune",
        "--tags",
        "origin",
        "+refs/heads/*:refs/remotes/origin/*",
        cwd=workspace,
    )


def snapshot_refs(workspace: Path) -> dict[str, str]:
    output = run_git(
        "for-each-ref",
        "--format=%(objectname) %(refname)",
        cwd=workspace,
        log_output=False,
    )
    return {
        ref: oid for oid, ref in (line.split(" ", 1) for line in output.splitlines())
    }


def base_prerequisites(workspace: Path, refs: Mapping[str, str]) -> tuple[str, ...]:
    """Return base commits, or raise if the current clone lacks a base object."""
    commits: set[str] = set()
    for oid in set(refs.values()):
        kind = subprocess.run(
            ["git", "cat-file", "-t", oid],
            cwd=workspace,
            check=False,
            capture_output=True,
            text=True,
        )
        if kind.returncode != 0:
            raise ValueError(f"Monthly base object {oid} is not available locally.")
        if kind.stdout.strip() == "commit":
            commits.add(oid)
        elif kind.stdout.strip() == "tag":
            peeled = subprocess.run(
                ["git", "rev-parse", "--verify", f"{oid}^{{commit}}"],
                cwd=workspace,
                check=False,
                capture_output=True,
                text=True,
            )
            if peeled.returncode != 0:
                raise ValueError(f"Monthly base tag {oid} does not point to a commit.")
            commits.add(peeled.stdout.strip())
    if not commits:
        raise ValueError("Monthly base has no commit prerequisites.")
    return tuple(f"^{oid}" for oid in sorted(commits))


def has_new_objects(workspace: Path, prerequisites: tuple[str, ...]) -> bool:
    return bool(
        run_git(
            "rev-list", "--objects", "--all", *prerequisites,
            cwd=workspace,
            log_output=False,
        )
    )


def create_and_verify_bundle(
    workspace: Path, bundle_path: Path, prerequisites: tuple[str, ...] = ()
) -> None:
    run_git(
        "bundle", "create", str(bundle_path), "--all", *prerequisites,
        cwd=workspace,
    )
    run_git("bundle", "verify", str(bundle_path), cwd=workspace)


def write_checksum(path: Path, sha256_path: Path) -> str:
    sha256 = sha256_file(path)
    sha256_path.write_text(f"{sha256}  {path.name}\n", encoding="utf-8")
    return sha256


def write_metadata(
    workspace: Path,
    artifacts: BackupArtifacts,
    bundle_sha256: str | None,
    backup_type: str,
    base_prefix: str | None,
    refs: Mapping[str, str],
) -> None:
    metadata = {
        "backup_type": backup_type,
        "base_prefix": base_prefix,
        "backup_created_at": datetime.now(timezone.utc).isoformat(),
        "bundle_file": artifacts.bundle_path.name if bundle_sha256 else None,
        "bundle_size_bytes": (
            artifacts.bundle_path.stat().st_size if bundle_sha256 else 0
        ),
        "bundle_sha256": bundle_sha256,
        "git_head": run_git("rev-parse", "HEAD", cwd=workspace, log_output=False),
        "git_head_ref": head_reference(workspace),
        "git_repository": require_env("GITHUB_REPOSITORY"),
        "github_run_attempt": require_env("GITHUB_RUN_ATTEMPT"),
        "github_run_id": require_env("GITHUB_RUN_ID"),
        "github_run_number": require_env("GITHUB_RUN_NUMBER"),
        "remote_prefix": artifacts.remote_prefix,
        "refs": dict(refs),
    }
    artifacts.metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def head_reference(workspace: Path) -> str | None:
    result = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "HEAD"],
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def restore_snapshot(
    workspace: Path,
    restore_path: Path,
    bundle_path: Path | None,
    expected_refs: Mapping[str, str],
    base_bundle_path: Path | None = None,
    head_ref: str | None = None,
) -> None:
    source = base_bundle_path or bundle_path
    if source is None:
        raise ValueError("A full bundle is required for restoration.")
    run("git", "clone", "--mirror", str(source), str(restore_path), cwd=workspace)
    if base_bundle_path is not None and bundle_path is not None:
        run_git(
            "-C", str(restore_path), "bundle", "verify", str(bundle_path),
            cwd=workspace,
        )
        run_git(
            "-C", str(restore_path), "fetch", "--force", str(bundle_path),
            "+refs/*:refs/*",
            cwd=workspace,
        )

    restored_refs = snapshot_refs(restore_path)
    for ref in restored_refs.keys() - expected_refs.keys():
        run_git(
            "-C", str(restore_path), "update-ref", "--no-deref", "-d", ref,
            cwd=workspace,
        )
    for ref, oid in expected_refs.items():
        if restored_refs.get(ref) != oid:
            run_git(
                "-C", str(restore_path), "update-ref", "--no-deref", ref, oid,
                cwd=workspace,
            )
    if snapshot_refs(restore_path) != expected_refs:
        raise ValueError("Restored refs differ from the backup snapshot.")
    if head_ref and head_ref in expected_refs:
        run_git(
            "-C", str(restore_path), "symbolic-ref", "HEAD", head_ref,
            cwd=workspace,
        )
    run_git("-C", str(restore_path), "fsck", "--strict", cwd=workspace)


def smoke_test_restore(
    workspace: Path,
    bundle_path: Path | None,
    expected_refs: Mapping[str, str],
    base_bundle_path: Path | None = None,
    head_ref: str | None = None,
) -> None:
    temp_root = Path(tempfile.mkdtemp(prefix="repo-backup-restore-", dir=workspace))
    try:
        restore_snapshot(
            workspace, temp_root / "repo", bundle_path, expected_refs,
            base_bundle_path, head_ref,
        )
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def write_github_outputs(artifacts: BackupArtifacts, has_bundle: bool) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT", "")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"remote-prefix={artifacts.remote_prefix}\n")
        handle.write(f"bundle-path={artifacts.bundle_path if has_bundle else ''}\n")
        handle.write(f"sha256-path={artifacts.sha256_path if has_bundle else ''}\n")
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
    try:
        completed = subprocess.run(
            list(args),
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        output = redact_credentials((exc.stdout or "").strip())
        if output:
            print(output)
        raise
    output = redact_credentials(completed.stdout.strip())
    if output and log_output:
        print(output)
    return output


def redact_credentials(text: str) -> str:
    return re.sub(r"(https?)://[^/@\s]+@", r"\1://***@", text)
