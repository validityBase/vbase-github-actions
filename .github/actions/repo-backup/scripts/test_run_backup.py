"""Unit tests for repo-backup credential orchestration."""

from __future__ import annotations

import unittest

import run_backup


DIRECT_CREDENTIALS = {
    "OBJECT_STORAGE_ACCESS_KEY_ID": "access-key",
    "OBJECT_STORAGE_SECRET_ACCESS_KEY": "secret-key",
    "OBJECT_STORAGE_BUCKET_NAME": "backup-bucket",
    "OBJECT_STORAGE_ENDPOINT_URL": "https://s3.example.com",
    "OBJECT_STORAGE_REGION": "us-east-1",
}


class BuildExecutionTests(unittest.TestCase):
    """Validate selection and isolation of credential modes."""

    def test_builds_direct_backup_execution(self) -> None:
        """Complete direct credentials run the existing backup implementation."""
        execution = run_backup.build_execution(DIRECT_CREDENTIALS, "python")

        self.assertEqual(("python", "-m", "scripts.main"), execution.command)
        self.assertEqual(
            "access-key", execution.environment["OBJECT_STORAGE_ACCESS_KEY_ID"]
        )

    def test_builds_bitwarden_execution_without_token_in_arguments(self) -> None:
        """Bitwarden tokens stay in the child environment, not command arguments."""
        execution = run_backup.build_execution(
            {
                run_backup.BITWARDEN_TOKEN_KEY: "sensitive-token",
                run_backup.BITWARDEN_PROJECT_KEY: "backup-project",
                run_backup.BITWARDEN_ORG_ID_KEY: "organization-id",
            },
            "python",
        )

        self.assertEqual("sensitive-token", execution.environment["BWS_ACCESS_TOKEN"])
        self.assertNotIn("sensitive-token", execution.command)
        self.assertEqual(
            (
                "python",
                "-m",
                "bw_sm.env",
                "run",
                "--project",
                "backup-project",
                "--token-env",
                "BWS_ACCESS_TOKEN",
                "--backend",
                "api",
                "--org-id",
                "organization-id",
                "--",
                "python",
                "-m",
                "scripts.main",
            ),
            execution.command,
        )

    def test_rejects_partial_direct_credentials(self) -> None:
        """Direct mode cannot start with an incomplete credential set."""
        with self.assertRaisesRegex(
            run_backup.ConfigurationError, "Direct credential mode requires"
        ):
            run_backup.build_execution(
                {"OBJECT_STORAGE_ACCESS_KEY_ID": "access-key"}, "python"
            )

    def test_rejects_mixed_credential_modes(self) -> None:
        """Callers must not combine Bitwarden and direct credentials."""
        with self.assertRaisesRegex(
            run_backup.ConfigurationError, "cannot be combined"
        ):
            run_backup.build_execution(
                {
                    **DIRECT_CREDENTIALS,
                    run_backup.BITWARDEN_TOKEN_KEY: "sensitive-token",
                    run_backup.BITWARDEN_PROJECT_KEY: "backup-project",
                },
                "python",
            )

    def test_requires_project_in_bitwarden_mode(self) -> None:
        """A Bitwarden token must be paired with a project name."""
        with self.assertRaisesRegex(
            run_backup.ConfigurationError, "bitwarden-project is required"
        ):
            run_backup.build_execution(
                {run_backup.BITWARDEN_TOKEN_KEY: "sensitive-token"}, "python"
            )


if __name__ == "__main__":
    unittest.main()
