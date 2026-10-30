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

    @mock.patch.object(
        run_with_prepared_env,
        "read_dotenv",
        return_value={"VALUE": "loaded-secret"},
    )
    @mock.patch.object(run_with_prepared_env, "run_with_scoped_masks")
    def test_runs_with_paths_without_access_tokens(
        self,
        run_mock: mock.Mock,
        read_values_mock: mock.Mock,
    ) -> None:
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
        read_values_mock.assert_called_once_with(env_file.resolve())

    @mock.patch.object(
        run_with_prepared_env,
        "read_dotenv",
        return_value={"VALUE": "loaded-secret", "EMPTY": ""},
    )
    @mock.patch.object(run_with_prepared_env, "run_with_scoped_masks")
    def test_loads_selected_file_into_command_environment(
        self,
        run_mock: mock.Mock,
        _read_dotenv_mock: mock.Mock,
    ) -> None:
        """A selected prepared file becomes values rather than a path."""
        with tempfile.TemporaryDirectory() as directory:
            session_directory = Path(directory)
            env_file = session_directory / "project-0.env"
            env_file.write_text('VALUE="loaded-secret"\n', encoding="utf-8")
            env_file.chmod(0o600)
            manifest = session_directory / "session.json"
            prepared_session.write_session_manifest(
                manifest, {"APP_ENV_FILE": env_file}, {"APP_TOKEN"}
            )

            run_with_prepared_env.run_with_prepared_env(
                manifest,
                "run tests",
                session_directory,
                {"APP_TOKEN": "machine-token", "VALUE": "old"},
                "APP_ENV_FILE",
            )

        child_env = run_mock.call_args.kwargs["env"]
        self.assertNotIn("APP_TOKEN", child_env)
        self.assertNotIn("APP_ENV_FILE", child_env)
        self.assertEqual("loaded-secret", child_env["VALUE"])
        self.assertEqual("", child_env["EMPTY"])

    @mock.patch.object(
        run_with_prepared_env,
        "read_dotenv",
        return_value={"VALUE": "loaded-secret"},
    )
    def test_rejects_unknown_environment_file_variable(
        self, _read_dotenv_mock: mock.Mock
    ) -> None:
        """The load selector must name an entry from the manifest."""
        with tempfile.TemporaryDirectory() as directory:
            session_directory = Path(directory)
            env_file = session_directory / "project-0.env"
            env_file.write_text('VALUE="loaded-secret"\n', encoding="utf-8")
            env_file.chmod(0o600)
            manifest = session_directory / "session.json"
            prepared_session.write_session_manifest(
                manifest, {"APP_ENV_FILE": env_file}, {"APP_TOKEN"}
            )

            with self.assertRaisesRegex(
                prepared_session.SessionError, "no env file variable named MISSING"
            ):
                run_with_prepared_env.run_with_prepared_env(
                    manifest,
                    "run tests",
                    session_directory,
                    {},
                    "MISSING",
                )


if __name__ == "__main__":
    unittest.main()
