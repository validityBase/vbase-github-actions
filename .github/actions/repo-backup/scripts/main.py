"""Entrypoint for the repo-backup composite action."""

from __future__ import annotations

import sys
from pathlib import Path

from .b2_client import B2Client
from .git_backup import (
    build_artifacts,
    create_and_verify_bundle,
    fetch_all_refs,
    require_env,
    smoke_test_restore,
    write_checksum,
    write_github_outputs,
    write_metadata,
)


def run() -> None:
    workspace = Path(require_env("GITHUB_WORKSPACE"))
    artifacts = build_artifacts(
        workspace=workspace,
        backup_prefix=require_env("BACKUP_PREFIX"),
        bundle_name=require_env("BUNDLE_NAME"),
    )

    fetch_all_refs(workspace)
    create_and_verify_bundle(workspace, artifacts.bundle_path)
    bundle_sha256 = write_checksum(artifacts.bundle_path, artifacts.sha256_path)
    write_metadata(workspace, artifacts, bundle_sha256)
    smoke_test_restore(workspace, artifacts.bundle_path)

    b2 = B2Client(
        key_id=require_env("B2_KEY_ID"),
        application_key=require_env("B2_APPLICATION_KEY"),
        bucket_name=require_env("B2_BUCKET_NAME"),
    )
    b2.upload_files(
        [
            (
                artifacts.bundle_path,
                f"{artifacts.remote_prefix}/{artifacts.bundle_path.name}",
            ),
            (
                artifacts.sha256_path,
                f"{artifacts.remote_prefix}/{artifacts.sha256_path.name}",
            ),
            (
                artifacts.metadata_path,
                f"{artifacts.remote_prefix}/{artifacts.metadata_path.name}",
            ),
        ]
    )
    write_github_outputs(artifacts)


def main() -> None:
    try:
        run()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
