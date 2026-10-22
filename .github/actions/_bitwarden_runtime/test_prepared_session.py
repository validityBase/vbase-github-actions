"""Tests for private Bitwarden session manifests."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from _bitwarden_runtime import prepared_session


class PreparedSessionTests(unittest.TestCase):
    """Validate manifest integrity, permissions, and dotenv decoding."""

    @staticmethod
    def _parser_modules(parse_dotenv):
        """Return minimal bw-sm modules exposing the canonical parser contract."""
        package = types.ModuleType("bw_sm")
        package.__path__ = []
        env_module = types.ModuleType("bw_sm.env")
        env_module.parse_dotenv = parse_dotenv
        return {"bw_sm": package, "bw_sm.env": env_module}

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
            modules = self._parser_modules(
                lambda content: {"VALUE": "secret\nvalue"}
            )
            with mock.patch.dict(sys.modules, modules):
                self.assertEqual(
                    ["secret\nvalue"], prepared_session.read_dotenv_values(env_file)
                )

    def test_uses_bw_sm_canonical_dotenv_parser(self) -> None:
        """The action delegates dotenv decoding to the installed bw-sm package."""
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory, "project.env")
            env_file.write_text('REFERENCE="${OTHER_VALUE}"\n', encoding="utf-8")
            parse_dotenv = mock.Mock(
                return_value={"REFERENCE": "${OTHER_VALUE}", "EMPTY": ""}
            )

            with mock.patch.dict(
                sys.modules, self._parser_modules(parse_dotenv)
            ):
                self.assertEqual(
                    ["${OTHER_VALUE}"],
                    prepared_session.read_dotenv_values(env_file),
                )
            parse_dotenv.assert_called_once_with('REFERENCE="${OTHER_VALUE}"\n')

    def test_rejects_malformed_dotenv_content(self) -> None:
        """Malformed lines cannot be silently skipped while masks are registered."""
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory, "project.env")
            env_file.write_text('VALID="secret"\nmalformed line\n', encoding="utf-8")

            parse_dotenv = mock.Mock(side_effect=ValueError("invalid"))
            with mock.patch.dict(
                sys.modules, self._parser_modules(parse_dotenv)
            ):
                with self.assertRaisesRegex(
                    prepared_session.SessionError, "invalid content"
                ):
                    prepared_session.read_dotenv_values(env_file)

    def test_reads_an_empty_project(self) -> None:
        """A project with no secrets requires no command-scoped masks."""
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory, "project.env")
            env_file.write_text("", encoding="utf-8")

            with mock.patch.dict(
                sys.modules, self._parser_modules(lambda content: {})
            ):
                self.assertEqual([], prepared_session.read_dotenv_values(env_file))

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
