"""Run repo backup with direct credentials or a Bitwarden project."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Mapping


BITWARDEN_TOKEN_KEY = "REPO_BACKUP_BITWARDEN_ACCESS_TOKEN"
BITWARDEN_PROJECT_KEY = "REPO_BACKUP_BITWARDEN_PROJECT"
BITWARDEN_ORG_ID_KEY = "REPO_BACKUP_BITWARDEN_ORG_ID"
OBJECT_STORAGE_KEYS = (
    "OBJECT_STORAGE_ACCESS_KEY_ID",
    "OBJECT_STORAGE_SECRET_ACCESS_KEY",
    "OBJECT_STORAGE_BUCKET_NAME",
    "OBJECT_STORAGE_ENDPOINT_URL",
    "OBJECT_STORAGE_REGION",
)


class ConfigurationError(ValueError):
    """Raised when the action credential inputs are incomplete or ambiguous."""


@dataclass(frozen=True)
class Execution:
    """Command and environment for one backup execution."""

    command: tuple[str, ...]
    environment: dict[str, str]


def _value(environ: Mapping[str, str], key: str) -> str:
    """Return a stripped environment value."""
    return environ.get(key, "").strip()


def build_execution(
    environ: Mapping[str, str], executable: str = sys.executable
) -> Execution:
    """Build a direct or Bitwarden-backed backup command."""
    token = _value(environ, BITWARDEN_TOKEN_KEY)
    direct_values = {key: _value(environ, key) for key in OBJECT_STORAGE_KEYS}
    populated_direct_keys = [key for key, value in direct_values.items() if value]

    child_env = dict(environ)
    command = [executable, "-m", "scripts.main"]

    if token:
        if populated_direct_keys:
            raise ConfigurationError(
                "Bitwarden and direct object storage credentials cannot be combined."
            )

        project = _value(environ, BITWARDEN_PROJECT_KEY)
        if not project:
            raise ConfigurationError(
                "bitwarden-project is required when bitwarden-access-token is set."
            )

        child_env["BWS_ACCESS_TOKEN"] = token
        command = [
            executable,
            "-m",
            "bw_sm.env",
            "run",
            "--project",
            project,
            "--token-env",
            "BWS_ACCESS_TOKEN",
            "--backend",
            "api",
        ]
        organization_id = _value(environ, BITWARDEN_ORG_ID_KEY)
        if organization_id:
            command.extend(("--org-id", organization_id))
        command.extend(("--", executable, "-m", "scripts.main"))
    else:
        missing_keys = [key for key, value in direct_values.items() if not value]
        if missing_keys:
            raise ConfigurationError(
                "Direct credential mode requires: " + ", ".join(missing_keys)
            )

    return Execution(tuple(command), child_env)


def main() -> int:
    """Validate credentials and execute the backup implementation."""
    try:
        execution = build_execution(os.environ)
    except ConfigurationError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    result = subprocess.run(
        execution.command,
        check=False,
        env=execution.environment,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
