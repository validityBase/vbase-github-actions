"""Cache switches, scoped persistence keys and runner integration."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cache_config import cache_options, fingerprint, prepare
from run_with_env import run_with_env
from run_with_env_files import ProjectConfig, ScopedMaskFilter, dump_project


class CacheConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = {
            "BTENV_CACHE_ENABLED": "true",
            "BTENV_CACHE_TTL_SECONDS": "3600",
            "BTENV_CACHE_REFRESH": "false",
            "BTENV_PROJECT": "private-project",
            "BTENV_ORG_ID": "organization",
            "BTENV_ACCESS_TOKEN": "fake-token",
            "BTENV_BACKEND": "api",
            "RUNNER_TEMP": self.temp.name,
            "RUNNER_OS": "Linux",
            "BTENV_TOKEN_ENV": "TOKEN",
            "BTENV_COMMAND": "exit 0",
        }

    def test_disabled_is_default_and_needs_no_runner_or_token(self):
        self.assertEqual(cache_options({}), [])
        self.assertEqual(prepare({}), {})
        self.assertEqual(prepare({**self.env, "BTENV_CACHE_ENABLED": "false"}), {})
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_prefix_reused_across_runs_and_save_keys_are_unique(self):
        first = prepare(self.env)
        second = prepare(self.env)
        self.assertEqual(first["prefix"], second["prefix"])
        self.assertNotEqual(first["key"], second["key"])
        self.assertEqual(first["directory"], second["directory"])
        self.assertEqual(first["restore"], "true")
        outputs = json.dumps(first)
        self.assertNotIn("fake-token", outputs)
        self.assertNotIn("private-project", outputs)

    def test_project_org_token_and_runner_isolate_remote_cache(self):
        original = prepare(self.env)["prefix"]
        for key in ("BTENV_PROJECT", "BTENV_ORG_ID", "BTENV_ACCESS_TOKEN"):
            with self.subTest(key=key):
                self.assertNotEqual(
                    prepare({**self.env, key: "different"})["prefix"], original
                )
        self.assertNotEqual(
            prepare({**self.env, "RUNNER_OS": "macOS"})["prefix"], original
        )

    def test_windows_cache_is_rejected_before_storage_is_created(self):
        environ = {**self.env, "RUNNER_OS": "Windows"}
        with self.assertRaisesRegex(ValueError, "Linux or macOS"):
            prepare(environ)
        self.assertEqual(prepare({**environ, "BTENV_CACHE_ENABLED": "false"}), {})
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_existing_local_ciphertext_skips_restore_and_detects_refresh(self):
        directory = Path(prepare(self.env)["directory"])
        snapshot = directory / "snapshot.enc"
        snapshot.write_bytes(b"ciphertext")
        before = fingerprint(directory)
        self.assertEqual(prepare(self.env)["restore"], "false")
        (directory / "private.env").write_text("not included", encoding="utf-8")
        (directory / "cache.lock").touch()
        self.assertEqual(fingerprint(directory), before)
        snapshot.write_bytes(b"refreshed ciphertext")
        self.assertNotEqual(fingerprint(directory), before)

    def test_multi_project_order_and_output_variable_do_not_change_scope(self):
        projects = [
            {
                "project": "first",
                "token-env": "FIRST",
                "env-file-variable": "FIRST_FILE",
            },
            {
                "project": "second",
                "token-env": "SECOND",
                "env-file-variable": "SECOND_FILE",
            },
        ]
        environ = {**self.env, "FIRST": "token-1", "SECOND": "token-2"}
        original = prepare({**environ, "BTENV_PROJECTS_JSON": json.dumps(projects)})
        projects.reverse()
        projects[0]["env-file-variable"] = "ANOTHER_FILE"
        reordered = prepare({**environ, "BTENV_PROJECTS_JSON": json.dumps(projects)})
        self.assertEqual(original["prefix"], reordered["prefix"])

    def test_invalid_flags_ttl_and_backend_fail_before_restoring(self):
        for field, value in (
            ("BTENV_CACHE_ENABLED", "yes"),
            ("BTENV_CACHE_REFRESH", "1"),
            ("BTENV_CACHE_TTL_SECONDS", "0"),
            ("BTENV_CACHE_TTL_SECONDS", "-1"),
            ("BTENV_CACHE_TTL_SECONDS", "hour"),
            ("BTENV_BACKEND", "cli"),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                prepare({**self.env, field: value})

    def test_refuses_symlinked_files(self):
        directory = Path(prepare(self.env)["directory"])
        target = Path(self.temp.name) / "target"
        target.write_bytes(b"private")
        (directory / "snapshot.enc").symlink_to(target)
        with self.assertRaises(ValueError):
            fingerprint(directory)

    def test_single_and_multi_project_forward_the_same_cache_controls(self):
        environ = {
            **self.env,
            "BTENV_CACHE_DIR": self.temp.name,
            "BTENV_CACHE_REFRESH": "true",
        }
        expected = cache_options(environ)
        with patch("run_with_env.run_with_scoped_masks", return_value=19) as run:
            self.assertEqual(run_with_env(environ, Path(self.temp.name)), 19)
            command = run.call_args.args[0]
            start = command.index("--cache-enabled")
            self.assertEqual(command[start : command.index("--")], expected)
            self.assertNotIn("BTENV_CACHE_DIR", run.call_args.kwargs["env"])
        project = ProjectConfig(
            "project", None, "BTENV_ACCESS_TOKEN", "FILE", "org", "api"
        )
        with patch("run_with_env_files.run_with_scoped_masks", return_value=0) as dump:
            dump_project(project, Path("output.env"), environ, ScopedMaskFilter())
            command = dump.call_args.args[0]
            start = command.index("--cache-enabled")
            self.assertEqual(command[start : command.index("--output")], expected)


if __name__ == "__main__":
    unittest.main()
