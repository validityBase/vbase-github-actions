"""Resolve Backblaze B2 backup credentials from Bitwarden Secrets Manager."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from bw_sm.core import BitwardenSecretManager


REQUIRED_SECRET_NAMES = ("B2_KEY_ID", "B2_APPLICATION_KEY", "B2_BUCKET_NAME")


def require_env(name: str) -> str:
    """Return a required environment variable."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required.")
    return value


def add_github_mask(value: str) -> None:
    """Register a value with GitHub Actions masking."""
    escaped = (
        value.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )
    print(f"::add-mask::{escaped}")


def append_github_env(name: str, value: str) -> None:
    """Write one environment variable for later workflow steps."""
    github_env = require_env("GITHUB_ENV")
    delimiter = f"EOF_{uuid.uuid4().hex}"
    with Path(github_env).open("a", encoding="utf-8") as handle:
        handle.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


def run() -> None:
    """Fetch required B2 secrets and expose them to later workflow steps."""
    project_name = require_env("BW_PROJECT")
    organization_id = require_env("BW_ORG_ID")
    access_token = require_env("BWS_ACCESS_TOKEN")

    manager = BitwardenSecretManager(
        bw_token=access_token,
        project_name=project_name,
        organization_id=organization_id,
    )
    project = manager.resolve_project()
    secrets = manager.get_project_secrets()

    missing = [name for name in REQUIRED_SECRET_NAMES if not secrets.get(name)]
    if missing:
        raise ValueError(
            "Missing required Bitwarden project secret(s): " + ", ".join(missing)
        )

    for name in REQUIRED_SECRET_NAMES:
        value = secrets[name]
        add_github_mask(value)
        append_github_env(name, value)

    print(f"Resolved B2 backup credentials from Bitwarden project: {project.name}")


def main() -> None:
    """CLI entry point."""
    try:
        run()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
