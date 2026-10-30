"""Run one command with temporary dotenv files loaded from Bitwarden projects."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Mapping, Sequence

ACTIONS_PATH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ACTIONS_PATH))

from _bitwarden_runtime.project_files import (
    ConfigurationError,  # noqa: E402
    ProjectConfig,
    dump_project,
    parse_projects,
)
from _bitwarden_runtime.scoped_output import (
    ScopedMaskFilter,  # noqa: E402
    run_with_scoped_masks,
)


def run_with_env_files(
    projects: Sequence[ProjectConfig],
    command: str,
    working_directory: Path,
    environ: Mapping[str, str],
) -> int:
    """Create private dotenv files, run the caller command, and remove the files."""
    mask_filter = ScopedMaskFilter([environ[project.token_env] for project in projects])
    with tempfile.TemporaryDirectory(prefix="vbase-btenv-") as temp_directory:
        child_env = dict(environ)
        for index, project in enumerate(projects):
            output_path = Path(temp_directory, f"project-{index}.env")
            return_code = dump_project(project, output_path, environ, mask_filter)
            if return_code:
                return return_code
            child_env.pop(project.token_env, None)
            child_env[project.env_file_variable] = str(output_path)

        return run_with_scoped_masks(
            ["bash", "-euo", "pipefail", "-c", command],
            cwd=working_directory,
            env=child_env,
            mask_filter=mask_filter,
        )


def main() -> int:
    """Read composite-action inputs from the environment and run the command."""
    try:
        command = os.environ["BTENV_COMMAND"]
        projects = parse_projects(
            os.environ["BTENV_PROJECTS_JSON"],
            os.environ,
            os.environ.get("BTENV_ORG_ID") or None,
            os.environ.get("BTENV_BACKEND") or "api",
        )
    except (ConfigurationError, KeyError) as exc:
        print(f"Invalid Bitwarden env-file configuration: {exc}", file=sys.stderr)
        return 2

    return run_with_env_files(projects, command, Path.cwd(), os.environ)


if __name__ == "__main__":
    raise SystemExit(main())
