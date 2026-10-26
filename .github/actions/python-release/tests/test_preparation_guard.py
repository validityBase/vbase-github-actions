"""Exercise the real preparation guard without GitHub access or credentials."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class PreparationGuardTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.script = (
            Path(__file__).resolve().parents[1] / "scripts/check_open_release_prs.sh"
        )
        gh = self.root / "gh"
        gh.write_text(
            """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
Path(os.environ["TEST_ARGS"]).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
if os.environ.get("TEST_FAILURE"):
    sys.exit(7)
query = sys.argv[sys.argv.index("--jq") + 1]
for repo, branch in json.loads(os.environ["TEST_HEADS"]):
    print(f"{repo or ''}\\t{branch}" if ".head.repo.full_name" in query else branch)
""",
            encoding="utf-8",
        )
        gh.chmod(0o755)

    def run_guard(self, heads, **extra):
        env = {
            **os.environ,
            "PATH": str(self.root) + os.pathsep + os.environ["PATH"],
            "GITHUB_REPOSITORY": "validityBase/example",
            "DEFAULT_BRANCH": "main",
            "RELEASE_PREFIX": "release/",
            "TEST_ARGS": str(self.root / "args.json"),
            "TEST_HEADS": json.dumps(heads),
            **extra,
        }
        return subprocess.run(
            ["bash", str(self.script)],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_fork_release_pr_does_not_block_preparation(self):
        result = self.run_guard([("outsider/example", "release/v1.2.3")])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_same_repository_release_pr_blocks_preparation(self):
        result = self.run_guard([("validityBase/example", "release/v1.2.3")])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("An open Release PR", result.stdout)

    def test_ordinary_and_deleted_fork_heads_do_not_block(self):
        result = self.run_guard(
            [
                ("validityBase/example", "fix/timeout"),
                ("outsider/example", "release/v1.2.3"),
                (None, "release/v2.0.0"),
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_checks_all_pages_and_retains_head_repository(self):
        heads = [("validityBase/example", f"fix/{i}") for i in range(120)]
        heads.append(("validityBase/example", "release/v1.2.3"))
        self.assertEqual(self.run_guard(heads).returncode, 1)
        args = json.loads((self.root / "args.json").read_text(encoding="utf-8"))
        self.assertIn("--paginate", args)
        self.assertIn(".head.repo.full_name", args[args.index("--jq") + 1])

    def test_uses_configured_repository_branch_and_prefix(self):
        result = self.run_guard(
            [("another/project", "releases/v1.2.3")],
            GITHUB_REPOSITORY="another/project",
            DEFAULT_BRANCH="stable",
            RELEASE_PREFIX="releases/",
        )
        self.assertEqual(result.returncode, 1)
        args = json.loads((self.root / "args.json").read_text(encoding="utf-8"))
        self.assertIn("repos/another/project/pulls", args)
        self.assertIn("base=stable", args)

    def test_api_failure_stops_preparation(self):
        result = self.run_guard([], TEST_FAILURE="true")
        self.assertEqual(result.returncode, 7)
