"""Prepare reusable private dotenv files for one GitHub Actions job."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path
from typing import Mapping, Sequence

RUN_ACTION_SCRIPTS = (
    Path(__file__).resolve().parents[2] / "run-with-bitwarden-env" / "scripts"
)
sys.path.insert(0, str(RUN_ACTION_SCRIPTS))

from prepared_session import write_session_manifest  # noqa: E402
from run_with_env_files import (  # noqa: E402
    ConfigurationError,
    ProjectConfig,
    ScopedMaskFilter,
    dump_project,
    parse_projects,
)


def _scope_key(
    project: ProjectConfig, environ: Mapping[str, str]
) -> tuple[str, str | None, str | None, str | None, str]:
    """Identify one provider request without persisting its access token."""
    return (
        project.backend,
        project.organization_id,
        project.project,
        project.project_id,
        environ[project.token_env],
    )


def _require_private_output(path: Path) -> None:
    """Ensure the provider created a private regular file at the requested path."""
    if path.is_symlink() or not path.is_file():
        raise ConfigurationError(f"Bitwarden did not create a regular env file: {path}")
    path.chmod(0o600)
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ConfigurationError(f"Unable to make Bitwarden env file private: {path}")


def prepare_session(
    projects: Sequence[ProjectConfig],
    session_directory: Path,
    manifest_path: Path,
    environ: Mapping[str, str],
) -> int:
    """Load every distinct project scope once and write its path manifest."""
    mask_filter = ScopedMaskFilter(
        [environ[project.token_env] for project in projects]
    )
    loaded_scopes: dict[tuple[str, str | None, str | None, str | None, str], Path] = {}
    env_files: dict[str, Path] = {}

    for project in projects:
        scope = _scope_key(project, environ)
        output_path = loaded_scopes.get(scope)
        if output_path is None:
            output_path = session_directory / f"project-{len(loaded_scopes)}.env"
            return_code = dump_project(project, output_path, environ, mask_filter)
            if return_code:
                return return_code
            _require_private_output(output_path)
            loaded_scopes[scope] = output_path
        env_files[project.env_file_variable] = output_path

    write_session_manifest(
        manifest_path, env_files, {project.token_env for project in projects}
    )
    return 0


def main() -> int:
    """Validate action inputs and prepare one reusable session."""
    try:
        session_directory = Path(os.environ["BTENV_SESSION_DIRECTORY"]).resolve(
            strict=True
        )
        manifest_path = Path(os.environ["BTENV_SESSION_MANIFEST"])
        if manifest_path.parent.resolve() != session_directory:
            raise ConfigurationError(
                "Session manifest must be inside its session directory"
            )
        projects = parse_projects(
            os.environ["BTENV_PROJECTS_JSON"],
            os.environ,
            os.environ.get("BTENV_ORG_ID") or None,
            os.environ["BTENV_BACKEND"],
        )
        return prepare_session(projects, session_directory, manifest_path, os.environ)
    except (KeyError, OSError, ConfigurationError) as exc:
        print(f"Invalid Bitwarden session configuration: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
