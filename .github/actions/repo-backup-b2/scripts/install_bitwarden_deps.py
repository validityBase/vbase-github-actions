"""Install Python dependencies needed to read backup credentials from Bitwarden."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path


def require_env(name: str) -> str:
    """Return a required environment variable."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required.")
    return value


def write_netrc(token: str) -> Path:
    """Create a private GitHub netrc file for pip's private repository access."""
    netrc_path = Path.home() / ".netrc"
    netrc_path.write_text(
        f"machine github.com\nlogin x-access-token\npassword {token}\n",
        encoding="utf-8",
    )
    netrc_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return netrc_path


def run_command(command: list[str]) -> None:
    """Run a command and fail fast while keeping token values out of arguments."""
    subprocess.run(command, check=True)


def install_dependencies(vbase_common_ref: str) -> None:
    """Install Bitwarden SDK and vbase-common for the current Python runtime."""
    run_command([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    run_command(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            "bitwarden-sdk>=2.0.0",
            f"git+https://github.com/validityBase/vbase-common.git@{vbase_common_ref}",
        ]
    )


def main() -> int:
    """CLI entry point."""
    netrc_path: Path | None = None
    try:
        token = require_env("VBASE_COMMON_REPO_READ_TOKEN")
        vbase_common_ref = require_env("VBASE_COMMON_REF")

        netrc_path = write_netrc(token)
        install_dependencies(vbase_common_ref)
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    finally:
        if netrc_path is not None:
            netrc_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
