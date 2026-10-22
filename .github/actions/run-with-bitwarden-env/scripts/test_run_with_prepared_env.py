"""Tests for commands that reuse a prepared Bitwarden session."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run_with_prepared_env
from _bitwarden_runtime import prepared_session


class RunWithPreparedEnvTests(unittest.TestCase):
    """Verify reuse, token isolation, masking, and exit-code propagation."""

    @mock.patch.object(run_with_prepared_env, "run_with_scoped_masks")
    def test_runs_with_paths_without_access_tokens(self, run_mock: mock.Mock) -> None:
        """The child receives prepared paths while machine tokens are removed."""
        run_mock.return_value = 19
        with tempfile.TemporaryDirectory() as directory:
            session_directory = Path(directory)
            env_file = session_directory / "project-0.env"
            env_file.write_text('VALUE="loaded-secret"\n', encoding="utf-8")
            env_file.chmod(0o600)
            manifest = session_directory / "session.json"
            prepared_session.write_session_manifest(
                manifest, {"APP_ENV_FILE": env_file}, {"APP_TOKEN"}
            )

            result = run_with_prepared_env.run_with_prepared_env(
                manifest,
                "run tests",
                session_directory,
                {"APP_TOKEN": "machine-token", "UNCHANGED": "value"},
            )

        self.assertEqual(19, result)
        child_env = run_mock.call_args.kwargs["env"]
        self.assertNotIn("APP_TOKEN", child_env)
        self.assertEqual(str(env_file.resolve()), child_env["APP_ENV_FILE"])
        self.assertEqual("value", child_env["UNCHANGED"])
        mask_filter = run_mock.call_args.kwargs["mask_filter"]
        self.assertIn("loaded-secret", mask_filter._masks)


if __name__ == "__main__":
    unittest.main()
