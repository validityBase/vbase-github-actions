"""Run one command with temporary dotenv files loaded from Bitwarden projects."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ALLOWED_PROJECT_KEYS = {
    "backend",
    "env-file-variable",
    "org-id",
    "project",
    "project-id",
    "token-env",
}


class ConfigurationError(ValueError):
    """Raised when projects-json does not satisfy the action interface."""


@dataclass(frozen=True)
class ProjectConfig:
    """Validated configuration for one temporary Bitwarden dotenv file."""

    project: str | None
    project_id: str | None
    token_env: str
    env_file_variable: str
    organization_id: str | None
    backend: str


def _optional_string(value: object, field: str, index: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(
            f"projects-json[{index}].{field} must be a non-empty string"
        )
    return value.strip()


def _required_string(value: object, field: str, index: int) -> str:
    normalized = _optional_string(value, field, index)
    if normalized is None:
        raise ConfigurationError(f"projects-json[{index}].{field} is required")
    return normalized


def _validate_env_key(value: str, field: str, index: int) -> None:
    if not ENV_KEY_PATTERN.fullmatch(value):
        raise ConfigurationError(
            f"projects-json[{index}].{field} must be a valid environment variable name"
        )


def parse_project(
    item: dict[object, object],
    index: int,
    environ: Mapping[str, str],
    default_org_id: str | None,
    default_backend: str,
) -> ProjectConfig:
    """Parse and validate one multi-project action entry."""
    unknown_keys = set(item) - ALLOWED_PROJECT_KEYS
    if unknown_keys:
        unknown = ", ".join(sorted(str(key) for key in unknown_keys))
        raise ConfigurationError(
            f"projects-json[{index}] contains unsupported field(s): {unknown}"
        )

    project = _optional_string(item.get("project"), "project", index)
    project_id = _optional_string(item.get("project-id"), "project-id", index)
    if bool(project) == bool(project_id):
        raise ConfigurationError(
            f"projects-json[{index}] must define exactly one of project or project-id"
        )

    token_env = _required_string(item.get("token-env"), "token-env", index)
    env_file_variable = _required_string(
        item.get("env-file-variable"), "env-file-variable", index
    )
    _validate_env_key(token_env, "token-env", index)
    _validate_env_key(env_file_variable, "env-file-variable", index)
    if not environ.get(token_env, "").strip():
        raise ConfigurationError(
            f"projects-json[{index}].token-env references an empty or missing variable: "
            f"{token_env}"
        )

    organization_id = _optional_string(item.get("org-id"), "org-id", index)
    backend = _optional_string(item.get("backend"), "backend", index)
    return ProjectConfig(
        project=project,
        project_id=project_id,
        token_env=token_env,
        env_file_variable=env_file_variable,
        organization_id=organization_id or default_org_id,
        backend=backend or default_backend,
    )


def parse_projects(
    raw_projects: str,
    environ: Mapping[str, str],
    default_org_id: str | None,
    default_backend: str,
) -> list[ProjectConfig]:
    """Parse and validate the multi-project action input."""
    try:
        parsed = json.loads(raw_projects)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(
            f"projects-json must be valid JSON: {exc.msg}"
        ) from exc

    if not isinstance(parsed, list) or not parsed:
        raise ConfigurationError("projects-json must be a non-empty JSON array")

    projects: list[ProjectConfig] = []
    env_file_variables: set[str] = set()
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise ConfigurationError(f"projects-json[{index}] must be an object")
        project = parse_project(item, index, environ, default_org_id, default_backend)
        if project.env_file_variable in env_file_variables:
            raise ConfigurationError(
                "projects-json contains duplicate env-file-variable: "
                f"{project.env_file_variable}"
            )
        env_file_variables.add(project.env_file_variable)
        projects.append(project)

    return projects


def add_github_mask(value: str) -> None:
    """Mask one value without allowing workflow-command injection."""
    escaped = value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::add-mask::{escaped}")


def dump_project(
    project: ProjectConfig,
    output_path: Path,
    environ: Mapping[str, str],
) -> int:
    """Ask the installed bw-sm CLI to write one private dotenv file."""
    command = [
        sys.executable,
        "-m",
        "bw_sm.env",
        "dump",
        "--token-env",
        project.token_env,
        "--backend",
        project.backend,
    ]
    if project.project:
        command.extend(("--project", project.project))
    else:
        command.extend(("--project-id", project.project_id or ""))
    if project.organization_id:
        command.extend(("--org-id", project.organization_id))
    command.extend(("--output", str(output_path)))

    result = subprocess.run(command, check=False, env=dict(environ))
    return result.returncode


def run_with_env_files(
    projects: Sequence[ProjectConfig],
    command: str,
    working_directory: Path,
    environ: Mapping[str, str],
) -> int:
    """Create private dotenv files, run the caller command, and remove the files."""
    with tempfile.TemporaryDirectory(prefix="vbase-btenv-") as temp_directory:
        child_env = dict(environ)
        for index, project in enumerate(projects):
            add_github_mask(environ[project.token_env])
            output_path = Path(temp_directory, f"project-{index}.env")
            return_code = dump_project(project, output_path, environ)
            if return_code:
                return return_code
            child_env.pop(project.token_env, None)
            child_env[project.env_file_variable] = str(output_path)

        result = subprocess.run(
            ["bash", "-euo", "pipefail", "-c", command],
            check=False,
            cwd=working_directory,
            env=child_env,
        )
        return result.returncode


def main() -> int:
    """Read composite-action inputs from the environment and run the command."""
    try:
        command = os.environ["BTENV_COMMAND"]
        working_directory = Path.cwd()
        projects = parse_projects(
            os.environ["BTENV_PROJECTS_JSON"],
            os.environ,
            os.environ.get("BTENV_ORG_ID") or None,
            os.environ.get("BTENV_BACKEND") or "api",
        )
    except (ConfigurationError, KeyError) as exc:
        print(f"Invalid Bitwarden env-file configuration: {exc}", file=sys.stderr)
        return 2

    return run_with_env_files(projects, command, working_directory, os.environ)


if __name__ == "__main__":
    raise SystemExit(main())
