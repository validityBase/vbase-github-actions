"""Run one command with a single Bitwarden project and scoped log masking."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping

from scoped_output import run_with_scoped_masks


def run_with_env(environ: Mapping[str, str], working_directory: Path) -> int:
    """Load one Bitwarden project and redact only the wrapped command output."""
    token_env = environ["BTENV_TOKEN_ENV"]
    access_token = environ["BTENV_ACCESS_TOKEN"]
    command = [
        sys.executable,
        "-m",
        "bw_sm.env",
        "run",
        "--token-env",
        token_env,
        "--backend",
        environ["BTENV_BACKEND"],
    ]

    project = environ.get("BTENV_PROJECT", "")
    project_id = environ.get("BTENV_PROJECT_ID", "")
    if project:
        command.extend(("--project", project))
    elif project_id:
        command.extend(("--project-id", project_id))
    else:
        raise ValueError("project or project-id must be provided")

    organization_id = environ.get("BTENV_ORG_ID", "")
    if organization_id:
        command.extend(("--org-id", organization_id))

    command.extend(
        (
            "--",
            "bash",
            "-euo",
            "pipefail",
            "-c",
            environ["BTENV_COMMAND"],
        )
    )
    child_env = dict(environ)
    child_env[token_env] = access_token
    return run_with_scoped_masks(
        command,
        cwd=working_directory,
        env=child_env,
        initial_masks=[access_token],
    )


def main() -> int:
    """Run the action inputs from the current process environment."""
    try:
        return run_with_env(os.environ, Path.cwd())
    except (KeyError, ValueError) as exc:
        print(f"Invalid Bitwarden environment configuration: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
