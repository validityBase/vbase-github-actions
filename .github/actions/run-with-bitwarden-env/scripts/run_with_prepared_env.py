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
    read_dotenv_values,
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
) -> int:
    """Expose prepared file paths and redact their values for one command."""
    session = load_session_manifest(manifest_path)
    mask_filter = ScopedMaskFilter()
    for env_file in set(session.env_files.values()):
        for value in read_dotenv_values(env_file):
            mask_filter.add_mask(value)

    child_env = dict(environ)
    for key in session.remove_env:
        child_env.pop(key, None)
    child_env.update({key: str(value) for key, value in session.env_files.items()})
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
        return run_with_prepared_env(manifest_path, command, Path.cwd(), os.environ)
    except (KeyError, SessionError) as exc:
        print(f"Invalid prepared Bitwarden session: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
