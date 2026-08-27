"""Unit tests for the multi-project Bitwarden action runner."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run_with_env_files


class ParseProjectsTests(unittest.TestCase):
    """Validate the projects-json interface before secrets are fetched."""

    def test_parses_multiple_projects_with_defaults_and_overrides(self) -> None:
        """Project entries inherit defaults while allowing local overrides."""
        raw_projects = json.dumps(
            [
                {
                    "project": "app-docker",
                    "token-env": "APP_TOKEN",
                    "env-file-variable": "APP_ENV_FILE",
                },
                {
                    "project-id": "project-id",
                    "token-env": "API_TOKEN",
                    "env-file-variable": "API_ENV_FILE",
                    "org-id": "other-org",
                    "backend": "cli",
                },
            ]
        )

        projects = run_with_env_files.parse_projects(
            raw_projects,
            {"APP_TOKEN": "app-token", "API_TOKEN": "api-token"},
            "default-org",
            "api",
        )

        self.assertEqual(2, len(projects))
        self.assertEqual("default-org", projects[0].organization_id)
        self.assertEqual("api", projects[0].backend)
        self.assertEqual("other-org", projects[1].organization_id)
        self.assertEqual("cli", projects[1].backend)

    def test_rejects_missing_token_environment_variable(self) -> None:
        """A token reference must identify a populated environment variable."""
        raw_projects = json.dumps(
            [
                {
                    "project": "app-docker",
                    "token-env": "APP_TOKEN",
                    "env-file-variable": "APP_ENV_FILE",
                }
            ]
        )

        with self.assertRaisesRegex(
            run_with_env_files.ConfigurationError, "empty or missing variable"
        ):
            run_with_env_files.parse_projects(raw_projects, {}, None, "api")

    def test_rejects_duplicate_env_file_variables(self) -> None:
        """Each generated dotenv path must have a unique child env key."""
        raw_projects = json.dumps(
            [
                {
                    "project": "app-docker",
                    "token-env": "APP_TOKEN",
                    "env-file-variable": "DOCKER_ENV_FILE",
                },
                {
                    "project": "api-docker",
                    "token-env": "API_TOKEN",
                    "env-file-variable": "DOCKER_ENV_FILE",
                },
            ]
        )

        with self.assertRaisesRegex(
            run_with_env_files.ConfigurationError, "duplicate env-file-variable"
        ):
            run_with_env_files.parse_projects(
                raw_projects,
                {"APP_TOKEN": "app-token", "API_TOKEN": "api-token"},
                None,
                "api",
            )


class RunWithEnvFilesTests(unittest.TestCase):
    """Verify file-path scoping and cleanup around the caller command."""

    @mock.patch.object(run_with_env_files.subprocess, "run")
    def test_dump_project_keeps_access_token_out_of_command_arguments(
        self, run_mock: mock.Mock
    ) -> None:
        """The helper references token env names instead of embedding secrets."""
        run_mock.return_value.returncode = 0
        project = run_with_env_files.ProjectConfig(
            project="app-docker",
            project_id=None,
            token_env="APP_TOKEN",
            env_file_variable="APP_ENV_FILE",
            organization_id="organization-id",
            backend="api",
        )

        return_code = run_with_env_files.dump_project(
            project,
            Path("app.env"),
            {"APP_TOKEN": "sensitive-token"},
        )

        self.assertEqual(0, return_code)
        command = run_mock.call_args.args[0]
        self.assertIn("APP_TOKEN", command)
        self.assertNotIn("sensitive-token", command)

    @mock.patch.object(run_with_env_files, "add_github_mask")
    @mock.patch.object(run_with_env_files, "dump_project")
    @mock.patch.object(run_with_env_files.subprocess, "run")
    def test_runs_command_with_env_file_paths_and_removes_them(
        self,
        run_mock: mock.Mock,
        dump_mock: mock.Mock,
        mask_mock: mock.Mock,
    ) -> None:
        """The child gets paths but not access tokens, and files are temporary."""

        def write_env_file(
            _project: run_with_env_files.ProjectConfig,
            path: Path,
            _environ: dict[str, str],
        ) -> int:
            path.write_text('VALUE="secret"\n', encoding="utf-8")
            return 0

        dump_mock.side_effect = write_env_file
        run_mock.return_value.returncode = 0
        projects = [
            run_with_env_files.ProjectConfig(
                project="app-docker",
                project_id=None,
                token_env="APP_TOKEN",
                env_file_variable="APP_ENV_FILE",
                organization_id=None,
                backend="api",
            )
        ]

        with tempfile.TemporaryDirectory() as working_directory:
            return_code = run_with_env_files.run_with_env_files(
                projects,
                "docker compose up",
                Path(working_directory),
                {"APP_TOKEN": "app-token"},
            )

        self.assertEqual(0, return_code)
        command_env = run_mock.call_args.kwargs["env"]
        env_file = Path(command_env["APP_ENV_FILE"])
        self.assertNotIn("APP_TOKEN", command_env)
        self.assertFalse(env_file.exists())
        run_mock.assert_called_once()
        mask_mock.assert_called_once_with("app-token")


if __name__ == "__main__":
    unittest.main()
