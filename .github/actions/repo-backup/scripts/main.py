"""Entrypoint for the repo-backup composite action."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .git_backup import (
    base_prerequisites,
    build_artifacts,
    create_and_verify_bundle,
    fetch_all_refs,
    has_new_objects,
    head_reference,
    monthly_full_prefix,
    require_env,
    run_git,
    sha256_file,
    snapshot_refs,
    smoke_test_restore,
    write_checksum,
    write_github_outputs,
    write_metadata,
)
from .object_storage_uploader import ObjectStorageUploader


@dataclass(frozen=True)
class MonthlyBase:
    remote_prefix: str
    bundle_path: Path
    refs: dict[str, str]


def find_monthly_base(
    storage: ObjectStorageUploader,
    workspace: Path,
    full_prefix: str,
    bundle_name: str,
    directory: Path,
) -> MonthlyBase | None:
    """Select the newest complete, restorable full backup for this month."""
    metadata_keys = sorted(
        (
            key for key in storage.list_keys(full_prefix)
            if key.startswith(full_prefix)
            and key.endswith("/metadata.json")
            and key[len(full_prefix):].count("/") == 1
        ),
        reverse=True,
    )
    for key in metadata_keys:
        remote_prefix = key.removesuffix("/metadata.json")
        try:
            metadata_path = directory / "base-metadata.json"
            bundle_path = directory / "base.bundle"
            storage.download_file(key, metadata_path)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not isinstance(metadata, dict):
                raise ValueError("Invalid monthly base metadata.")
            refs = metadata["refs"]
            checksum = metadata["bundle_sha256"]
            if (
                metadata.get("backup_type") != "full"
                or metadata.get("git_repository") != require_env("GITHUB_REPOSITORY")
                or metadata.get("remote_prefix") != remote_prefix
                or metadata.get("bundle_file") != bundle_name
                or (
                    metadata.get("git_head_ref") is not None
                    and not isinstance(metadata.get("git_head_ref"), str)
                )
                or not isinstance(refs, dict)
                or not refs
                or not all(
                    isinstance(ref, str) and ref.startswith("refs/")
                    and isinstance(oid, str) and re.fullmatch(r"[0-9a-f]{40,64}", oid)
                    for ref, oid in refs.items()
                )
                or not isinstance(checksum, str)
                or not re.fullmatch(r"[0-9a-f]{64}", checksum)
            ):
                raise ValueError("Invalid monthly base metadata.")
            storage.download_file(f"{remote_prefix}/{bundle_name}", bundle_path)
            if sha256_file(bundle_path) != checksum:
                raise ValueError("Monthly base checksum does not match.")
            run_git(
                "bundle", "verify", str(bundle_path),
                cwd=workspace, log_output=False,
            )
            smoke_test_restore(
                workspace, bundle_path, refs, head_ref=metadata.get("git_head_ref")
            )
            return MonthlyBase(remote_prefix, bundle_path, refs)
        except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
            print(f"[WARN] Skipping unusable monthly base {remote_prefix}: {exc}")
    return None


def run() -> None:
    workspace = Path(require_env("GITHUB_WORKSPACE"))
    backup_prefix = require_env("BACKUP_PREFIX")
    bundle_name = require_env("BUNDLE_NAME")
    if not bundle_name or "/" in bundle_name or "\\" in bundle_name:
        raise ValueError("bundle-name must be a non-empty file name without slashes.")
    now = datetime.now(timezone.utc)
    fetch_all_refs(workspace)
    refs = snapshot_refs(workspace)
    object_storage = ObjectStorageUploader(
        access_key_id=require_env("OBJECT_STORAGE_ACCESS_KEY_ID"),
        secret_access_key=require_env("OBJECT_STORAGE_SECRET_ACCESS_KEY"),
        bucket_name=require_env("OBJECT_STORAGE_BUCKET_NAME"),
        endpoint_url=require_env("OBJECT_STORAGE_ENDPOINT_URL"),
        region=require_env("OBJECT_STORAGE_REGION"),
    )
    with tempfile.TemporaryDirectory(
        prefix="repo-backup-base-", dir=workspace
    ) as temp_dir:
        base = find_monthly_base(
            object_storage,
            workspace,
            monthly_full_prefix(backup_prefix, now),
            bundle_name,
            Path(temp_dir),
        )
        prerequisites: tuple[str, ...] = ()
        if base is not None:
            try:
                prerequisites = base_prerequisites(workspace, base.refs)
            except ValueError as exc:
                print(f"[WARN] Monthly base cannot be used for an incremental: {exc}")
                base = None

        backup_type = "incremental" if base is not None else "full"
        artifacts = build_artifacts(
            workspace, backup_prefix, bundle_name, backup_type, now
        )
        bundle_sha256 = None
        if base is None or has_new_objects(workspace, prerequisites):
            create_and_verify_bundle(workspace, artifacts.bundle_path, prerequisites)
            bundle_sha256 = write_checksum(artifacts.bundle_path, artifacts.sha256_path)

        smoke_test_restore(
            workspace,
            artifacts.bundle_path if bundle_sha256 else None,
            refs,
            base.bundle_path if base else None,
            head_reference(workspace),
        )
        write_metadata(
            workspace, artifacts, bundle_sha256, backup_type,
            base.remote_prefix if base else None, refs,
        )
        if bundle_sha256:
            object_storage.upload_file(
                artifacts.bundle_path,
                f"{artifacts.remote_prefix}/{artifacts.bundle_path.name}",
            )
            object_storage.upload_file(
                artifacts.sha256_path,
                f"{artifacts.remote_prefix}/{artifacts.sha256_path.name}",
            )
        object_storage.upload_file(
            artifacts.metadata_path,
            f"{artifacts.remote_prefix}/{artifacts.metadata_path.name}",
        )
        write_github_outputs(artifacts, bundle_sha256 is not None)


def main() -> None:
    try:
        run()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
