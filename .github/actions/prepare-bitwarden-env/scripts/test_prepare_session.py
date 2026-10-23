"""Tests for job-lifetime Bitwarden session preparation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import prepare_session


class PrepareSessionTests(unittest.TestCase):
    """Load each distinct provider scope once into private files."""

    @mock.patch.object(prepare_session, "dump_project")
    def test_deduplicates_scopes_and_writes_non_secret_manifest(
        self, dump_mock: mock.Mock
    ) -> None:
        """Two outputs for one scope reuse the same provider response."""

        def write_output(_project, path, _environ, _mask_filter):
            path.write_text('VALUE="loaded-secret"\n', encoding="utf-8")
            return 0

        dump_mock.side_effect = write_output
        environment = {"APP_TOKEN": "machine-token"}
        projects = [
            prepare_session.ProjectConfig(
                project="app",
                project_id=None,
                token_env="APP_TOKEN",
                env_file_variable=env_name,
                organization_id="org",
                backend="api",
            )
            for env_name in ("FIRST_ENV_FILE", "SECOND_ENV_FILE")
        ]

        with tempfile.TemporaryDirectory() as directory:
            session_directory = Path(directory)
            manifest = session_directory / "session.json"
            result = prepare_session.prepare_session(
                projects, session_directory, manifest, environment
            )
            payload = json.loads(manifest.read_text(encoding="utf-8"))

        self.assertEqual(0, result)
        dump_mock.assert_called_once()
        self.assertEqual(
            payload["env-files"]["FIRST_ENV_FILE"],
            payload["env-files"]["SECOND_ENV_FILE"],
        )
        self.assertEqual(["APP_TOKEN"], payload["remove-env"])
        self.assertNotIn("machine-token", json.dumps(payload))
        self.assertNotIn("loaded-secret", json.dumps(payload))

    @mock.patch.object(prepare_session, "dump_project", return_value=17)
    def test_does_not_publish_manifest_when_loading_fails(
        self, _dump_mock: mock.Mock
    ) -> None:
        """A partial provider failure cannot produce a reusable session."""
        project = prepare_session.ProjectConfig(
            project="app",
            project_id=None,
            token_env="APP_TOKEN",
            env_file_variable="APP_ENV_FILE",
            organization_id="org",
            backend="api",
        )
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory, "session.json")
            result = prepare_session.prepare_session(
                [project], Path(directory), manifest, {"APP_TOKEN": "token"}
            )
            self.assertFalse(manifest.exists())

        self.assertEqual(17, result)


if __name__ == "__main__":
    unittest.main()
