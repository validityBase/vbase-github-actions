"""Unit tests for the single-project Bitwarden action runner."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import run_with_env


class RunWithEnvTests(unittest.TestCase):
    """Build the bw-sm command without leaking masks to the whole job."""

    @mock.patch.object(run_with_env, "run_with_scoped_masks")
    def test_runs_named_project_with_command_scoped_masks(
        self, run_mock: mock.Mock
    ) -> None:
        """The token and bw-sm masks stay inside the wrapped command output."""
        run_mock.return_value = 0
        environ = {
            "BTENV_COMMAND": "python task.py",
            "BTENV_PROJECT": "project-name",
            "BTENV_PROJECT_ID": "",
            "BTENV_ORG_ID": "organization-id",
            "BTENV_TOKEN_ENV": "PROJECT_TOKEN",
            "BTENV_ACCESS_TOKEN": "access-token",
            "BTENV_BACKEND": "api",
        }

        return_code = run_with_env.run_with_env(environ, Path("/workspace"))

        self.assertEqual(0, return_code)
        command = run_mock.call_args.args[0]
        self.assertEqual(
            [
                run_with_env.sys.executable,
                "-m",
                "bw_sm.env",
                "run",
                "--token-env",
                "PROJECT_TOKEN",
                "--backend",
                "api",
                "--project",
                "project-name",
                "--org-id",
                "organization-id",
                "--",
                "bash",
                "-euo",
                "pipefail",
                "-c",
                "python task.py",
            ],
            command,
        )
        self.assertNotIn("access-token", command)
        self.assertEqual(
            "access-token", run_mock.call_args.kwargs["env"]["PROJECT_TOKEN"]
        )
        self.assertEqual(["access-token"], run_mock.call_args.kwargs["initial_masks"])
        self.assertEqual(Path("/workspace"), run_mock.call_args.kwargs["cwd"])

    @mock.patch.object(run_with_env, "run_with_scoped_masks")
    def test_supports_project_id_without_optional_org(
        self, run_mock: mock.Mock
    ) -> None:
        """Project ids preserve the existing selector contract."""
        run_mock.return_value = 17
        environ = {
            "BTENV_COMMAND": "false",
            "BTENV_PROJECT": "",
            "BTENV_PROJECT_ID": "project-id",
            "BTENV_ORG_ID": "",
            "BTENV_TOKEN_ENV": "BWS_ACCESS_TOKEN",
            "BTENV_ACCESS_TOKEN": "access-token",
            "BTENV_BACKEND": "cli",
        }

        return_code = run_with_env.run_with_env(environ, Path("/workspace"))

        self.assertEqual(17, return_code)
        command = run_mock.call_args.args[0]
        self.assertIn("--project-id", command)
        self.assertIn("project-id", command)
        self.assertNotIn("--org-id", command)


if __name__ == "__main__":
    unittest.main()
