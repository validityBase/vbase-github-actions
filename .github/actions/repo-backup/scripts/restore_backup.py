"""Restore a local full bundle and optional daily incremental bundle."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .git_backup import restore_snapshot, sha256_file


def read_metadata(path: Path, backup_type: str) -> dict:
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if metadata.get("backup_type") != backup_type:
        raise ValueError(f"{path} is not {backup_type} backup metadata.")
    refs = metadata.get("refs")
    if not isinstance(refs, dict) or not refs or not all(
        isinstance(ref, str) and ref.startswith("refs/")
        and isinstance(oid, str) and re.fullmatch(r"[0-9a-f]{40,64}", oid)
        for ref, oid in refs.items()
    ):
        raise ValueError(f"{path} has invalid Git refs.")
    return metadata


def check_bundle(path: Path, checksum: str) -> None:
    if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise ValueError("Backup metadata has an invalid bundle SHA-256.")
    if sha256_file(path) != checksum:
        raise ValueError(f"Bundle checksum mismatch: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-bundle", type=Path, required=True)
    parser.add_argument("--full-metadata", type=Path, required=True)
    parser.add_argument("--daily-bundle", type=Path)
    parser.add_argument("--daily-metadata", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    full = read_metadata(args.full_metadata, "full")
    check_bundle(args.full_bundle, full["bundle_sha256"])
    snapshot = full
    if args.daily_metadata:
        snapshot = read_metadata(args.daily_metadata, "incremental")
        if (
            snapshot.get("git_repository") != full.get("git_repository")
            or snapshot.get("base_prefix") != full.get("remote_prefix")
        ):
            raise ValueError(
                "Daily backup does not belong to this monthly full backup."
            )
        if snapshot.get("bundle_file"):
            if args.daily_bundle is None:
                parser.error("--daily-bundle is required for this daily metadata.")
            check_bundle(args.daily_bundle, snapshot["bundle_sha256"])
        elif args.daily_bundle is not None:
            parser.error("This daily metadata has no bundle; omit --daily-bundle.")
    elif args.daily_bundle is not None:
        parser.error("--daily-bundle requires --daily-metadata.")

    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    restore_snapshot(
        Path.cwd(), args.output,
        args.daily_bundle if args.daily_metadata else args.full_bundle,
        snapshot["refs"], args.full_bundle if args.daily_metadata else None,
        snapshot.get("git_head_ref"),
    )
    print(f"Restored {snapshot['git_repository']} to {args.output}")


if __name__ == "__main__":
    main()
