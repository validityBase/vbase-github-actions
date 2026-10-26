"""Read and write private manifests for job-lifetime Bitwarden env files."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from _bitwarden_runtime.project_files import ENV_KEY_PATTERN
SESSION_VERSION = 1


class SessionError(ValueError):
    """Raised when a prepared Bitwarden session is invalid or unsafe."""


@dataclass(frozen=True)
class PreparedSession:
    """Validated file paths and sensitive environment names for one session."""

    env_files: dict[str, Path]
    remove_env: frozenset[str]


def _write_private_json(path: Path, payload: object) -> None:
    """Write JSON without following links and with owner-only permissions."""
    if path.is_symlink():
        raise SessionError(f"Refusing to write session manifest to symlink: {path}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    if hasattr(os, "fchmod"):
        os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(payload, output, sort_keys=True)
        output.write("\n")


def write_session_manifest(
    path: Path, env_files: Mapping[str, Path], remove_env: set[str]
) -> None:
    """Write the non-secret mapping from child environment names to files."""
    _write_private_json(
        path,
        {
            "version": SESSION_VERSION,
            "env-files": {key: str(value) for key, value in env_files.items()},
            "remove-env": sorted(remove_env),
        },
    )


def _require_private_regular_file(
    path: Path, session_directory: Path, description: str
) -> Path:
    """Return a validated file contained directly in the session directory."""
    if path.is_symlink():
        raise SessionError(f"{description} must not be a symlink: {path}")
    try:
        resolved = path.resolve(strict=True)
        file_stat = resolved.stat()
    except OSError as exc:
        raise SessionError(f"{description} is unavailable: {path}") from exc
    if resolved.parent != session_directory:
        raise SessionError(f"{description} is outside its session directory: {path}")
    if not stat.S_ISREG(file_stat.st_mode):
        raise SessionError(f"{description} is not a regular file: {path}")
    if stat.S_IMODE(file_stat.st_mode) & 0o077:
        raise SessionError(f"{description} permissions are not private: {path}")
    return resolved


def load_session_manifest(path: Path) -> PreparedSession:
    """Validate and return the env-file mapping from one prepared session."""
    if path.is_symlink():
        raise SessionError(f"Session manifest must not be a symlink: {path}")
    try:
        manifest_path = path.resolve(strict=True)
        session_directory = manifest_path.parent
        directory_stat = session_directory.stat()
        if not stat.S_ISDIR(directory_stat.st_mode):
            raise SessionError("Prepared session parent is not a directory")
        if stat.S_IMODE(directory_stat.st_mode) & 0o077:
            raise SessionError("Prepared session directory permissions are not private")
        manifest_path = _require_private_regular_file(
            manifest_path, session_directory, "Session manifest"
        )
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionError(f"Unable to read prepared session manifest: {path}") from exc

    if not isinstance(payload, dict) or "version" not in payload:
        raise SessionError("Prepared session manifest has an unexpected format")
    if payload["version"] != SESSION_VERSION:
        raise SessionError("Prepared session manifest version is unsupported")
    if set(payload) != {
        "version",
        "env-files",
        "remove-env",
    }:
        raise SessionError("Prepared session manifest has an unexpected format")
    raw_env_files = payload["env-files"]
    if not isinstance(raw_env_files, dict) or not raw_env_files:
        raise SessionError("Prepared session manifest has no env files")
    raw_remove_env = payload["remove-env"]
    if not isinstance(raw_remove_env, list) or any(
        not isinstance(key, str) or not ENV_KEY_PATTERN.fullmatch(key)
        for key in raw_remove_env
    ):
        raise SessionError("Prepared session contains an invalid remove-env list")

    env_files: dict[str, Path] = {}
    for key, raw_file in raw_env_files.items():
        if not isinstance(key, str) or not ENV_KEY_PATTERN.fullmatch(key):
            raise SessionError("Prepared session contains an invalid environment name")
        if not isinstance(raw_file, str) or not raw_file:
            raise SessionError(f"Prepared session path for {key} is invalid")
        env_files[key] = _require_private_regular_file(
            Path(raw_file), session_directory, "Prepared env file"
        )
    return PreparedSession(env_files, frozenset(raw_remove_env))


def read_dotenv(
    path: Path, *, _parser: Callable[[str], dict[str, str]] | None = None
) -> dict[str, str]:
    """Read one canonical bw-sm dotenv file without evaluating shell code."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SessionError(f"Unable to read prepared env file: {path}") from exc

    if _parser is None:
        try:
            from bw_sm.env import parse_dotenv as _parser
        except ImportError as exc:
            raise SessionError(
                "Installed bw-sm does not provide the canonical dotenv parser"
            ) from exc

    try:
        return _parser(content)
    except ValueError as exc:
        raise SessionError(f"Prepared dotenv file has invalid content: {path}") from exc
