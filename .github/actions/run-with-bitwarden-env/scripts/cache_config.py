"""Configure encrypted bw-sm caching and immutable GitHub Actions cache keys."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Mapping

CACHE_PREFIX = "vbase-btenv-v1"
ENCRYPTED_SUFFIXES = {".enc", ".state"}
SDK_BACKENDS = {"api", "sdk", "bt-sm-api", "sm-api"}
SUPPORTED_CACHE_RUNNERS = {"Linux", "macOS"}


def cache_options(environ: Mapping[str, str]) -> list[str]:
    """Keep the disabled path compatible with older bw-sm installations."""
    enabled = environ.get("BTENV_CACHE_ENABLED", "false")
    refresh = environ.get("BTENV_CACHE_REFRESH", "false")
    if enabled not in {"true", "false"} or refresh not in {"true", "false"}:
        raise ValueError("cache-enabled and cache-refresh must be true or false")
    ttl = int(environ.get("BTENV_CACHE_TTL_SECONDS", "3600"))
    if ttl <= 0:
        raise ValueError("cache-ttl-seconds must be a positive integer")
    if enabled == "false":
        return []
    options = ["--cache-enabled", "--cache-ttl-seconds", str(ttl)]
    if environ.get("BTENV_CACHE_DIR"):
        options.extend(("--cache-dir", environ["BTENV_CACHE_DIR"]))
    if refresh == "true":
        options.append("--cache-refresh")
    return options


def prepare(environ: Mapping[str, str]) -> dict[str, str]:
    """Emit only opaque scope hashes and paths, never tokens or project names."""
    from run_with_env_files import parse_projects

    if not cache_options(environ):
        return {}
    if environ["RUNNER_OS"] not in SUPPORTED_CACHE_RUNNERS:
        raise ValueError("Encrypted caching requires a Linux or macOS runner")
    raw_projects = environ.get("BTENV_PROJECTS_JSON")
    if not raw_projects:
        raw_projects = json.dumps(
            [
                {
                    "project" if environ.get("BTENV_PROJECT") else "project-id": (
                        environ.get("BTENV_PROJECT") or environ.get("BTENV_PROJECT_ID")
                    ),
                    "token-env": "BTENV_ACCESS_TOKEN",
                    "env-file-variable": "BTENV_UNUSED_FILE",
                }
            ]
        )
    projects = parse_projects(
        raw_projects,
        environ,
        environ.get("BTENV_ORG_ID"),
        environ.get("BTENV_BACKEND", "api"),
    )
    scopes = []
    for project in projects:
        if project.backend.strip().lower() not in SDK_BACKENDS:
            raise ValueError("Encrypted caching requires the api/sdk backend")
        scopes.append(
            [
                hashlib.sha256(environ[project.token_env].strip().encode()).hexdigest(),
                project.project,
                project.project_id,
                project.organization_id,
            ]
        )
    scope = hashlib.sha256(json.dumps(sorted(scopes, key=str)).encode()).hexdigest()
    directory = Path(environ["RUNNER_TEMP"]) / CACHE_PREFIX / scope
    if directory.is_symlink() or directory.parent.is_symlink():
        raise ValueError("Cache directories must not be symlinks")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    prefix = f"{CACHE_PREFIX}-{environ['RUNNER_OS']}-{scope}-"
    return {
        "directory": str(directory),
        "prefix": prefix,
        "key": prefix + uuid.uuid4().hex,
        "restore": str(not bool(fingerprint(directory))).lower(),
    }


def fingerprint(directory: Path) -> str:
    """Hash only encrypted files to avoid saving identical snapshots on hits."""
    digest = hashlib.sha256()
    found = False
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("Cache files must not be symlinks")
        if path.is_file() and path.suffix in ENCRYPTED_SUFFIXES:
            found = True
            digest.update(str(path.relative_to(directory)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest() if found else ""


def main() -> None:
    """Write action outputs; cache contents never enter workflow outputs."""
    if sys.argv[1] == "prepare":
        outputs = prepare(os.environ)
    else:
        digest = fingerprint(Path(os.environ["BTENV_CACHE_DIR"]))
        outputs = {
            "digest": digest,
            "changed": str(
                bool(digest) and digest != os.environ.get("BTENV_CACHE_BEFORE", "")
            ).lower(),
        }
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        for key, value in outputs.items():
            output.write(f"{key}={value}\n")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError) as exc:
        print(f"Invalid Bitwarden cache configuration: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
