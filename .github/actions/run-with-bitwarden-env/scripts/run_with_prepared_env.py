"""Run one command with env files from a prepared Bitwarden job session."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping

ACTIONS_PATH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ACTIONS_PATH))

from _bitwarden_runtime.prepared_session import (
    SessionError,  # noqa: E402
    load_session_manifest,
    read_dotenv,
)
from _bitwarden_runtime.scoped_output import (
    ScopedMaskFilter,  # noqa: E402
    run_with_scoped_masks,
)


def run_with_prepared_env(
    manifest_path: Path,
    command: str,
    working_directory: Path,
    environ: Mapping[str, str],
    load_env_file_variable: str | None = None,
) -> int:
    """Expose prepared files and optionally load one into the command env."""
    session = load_session_manifest(manifest_path)
    mask_filter = ScopedMaskFilter()
    parsed_files: dict[Path, dict[str, str]] = {}
    for env_file in set(session.env_files.values()):
        values = read_dotenv(env_file)
        parsed_files[env_file] = values
        for value in values.values():
            mask_filter.add_mask(value)

    child_env = dict(environ)
    for key in session.remove_env:
        child_env.pop(key, None)
    child_env.update({key: str(value) for key, value in session.env_files.items()})
    if load_env_file_variable:
        env_file = session.env_files.get(load_env_file_variable)
        if env_file is None:
            raise SessionError(
                "Prepared session has no env file variable named "
                f"{load_env_file_variable}"
            )
        child_env.pop(load_env_file_variable, None)
        child_env.update(parsed_files[env_file])
    return run_with_scoped_masks(
        ["bash", "-euo", "pipefail", "-c", command],
        cwd=working_directory,
        env=child_env,
        mask_filter=mask_filter,
    )


def main() -> int:
    """Read action inputs from the process environment and run the command."""
    try:
        manifest_path = Path(os.environ["BTENV_SESSION_MANIFEST"])
        command = os.environ["BTENV_COMMAND"]
        return run_with_prepared_env(
            manifest_path,
            command,
            Path.cwd(),
            os.environ,
            os.environ.get("BTENV_LOAD_ENV_FILE_VARIABLE") or None,
        )
    except (KeyError, SessionError) as exc:
        print(f"Invalid prepared Bitwarden session: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
