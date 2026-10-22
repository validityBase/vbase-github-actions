"""Tests for private Bitwarden session manifests."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import prepared_session


class PreparedSessionTests(unittest.TestCase):
    """Validate manifest integrity, permissions, and dotenv decoding."""

    def test_writes_and_loads_private_session_manifest(self) -> None:
        """A valid manifest maps env names and records tokens to remove."""
        with tempfile.TemporaryDirectory() as directory:
            session_directory = Path(directory)
            env_file = session_directory / "project-0.env"
            env_file.write_text('VALUE="secret\\nvalue"\n', encoding="utf-8")
            env_file.chmod(0o600)
            manifest = session_directory / "session.json"

            prepared_session.write_session_manifest(
                manifest, {"APP_ENV_FILE": env_file}, {"APP_TOKEN"}
            )
            loaded = prepared_session.load_session_manifest(manifest)

            self.assertEqual({"APP_ENV_FILE": env_file.resolve()}, loaded.env_files)
            self.assertEqual(frozenset({"APP_TOKEN"}), loaded.remove_env)
            self.assertEqual(0o600, os.stat(manifest).st_mode & 0o777)
            self.assertEqual(
                ["secret\nvalue"], prepared_session.read_dotenv_values(env_file)
            )

    def test_rejects_non_private_manifest(self) -> None:
        """Other users must not be able to read the path manifest."""
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory, "session.json")
            manifest.write_text(
                json.dumps({"version": 1, "env-files": {}, "remove-env": []}),
                encoding="utf-8",
            )
            manifest.chmod(0o644)

            with self.assertRaisesRegex(
                prepared_session.SessionError, "permissions are not private"
            ):
                prepared_session.load_session_manifest(manifest)

    def test_rejects_non_private_session_directory(self) -> None:
        """Other users must not be able to traverse the prepared session."""
        with tempfile.TemporaryDirectory() as directory:
            session_directory = Path(directory, "session")
            session_directory.mkdir(mode=0o755)
            env_file = session_directory / "project-0.env"
            env_file.write_text('VALUE="secret"\n', encoding="utf-8")
            env_file.chmod(0o600)
            manifest = session_directory / "session.json"
            prepared_session.write_session_manifest(
                manifest, {"APP_ENV_FILE": env_file}, {"APP_TOKEN"}
            )

            with self.assertRaisesRegex(
                prepared_session.SessionError,
                "directory permissions are not private",
            ):
                prepared_session.load_session_manifest(manifest)

    def test_rejects_env_file_outside_session_directory(self) -> None:
        """A modified manifest cannot expose an arbitrary runner file."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session_directory = root / "session"
            session_directory.mkdir(mode=0o700)
            outside = root / "outside.env"
            outside.write_text('VALUE="secret"\n', encoding="utf-8")
            outside.chmod(0o600)
            manifest = session_directory / "session.json"
            prepared_session.write_session_manifest(
                manifest, {"APP_ENV_FILE": outside}, {"APP_TOKEN"}
            )

            with self.assertRaisesRegex(
                prepared_session.SessionError, "outside its session directory"
            ):
                prepared_session.load_session_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
