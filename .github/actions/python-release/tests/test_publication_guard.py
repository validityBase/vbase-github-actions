"""Exercise the actual workflow guard before it can check out release code."""

import os
import re
import subprocess
import unittest
from pathlib import Path


class PublicationGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workflow = (
            Path(__file__).resolve().parents[3] / "workflows/build-python-release.yml"
        )
        contents = workflow.read_text(encoding="utf-8")
        # Extract this one literal shell block without adding a YAML dependency.
        match = re.search(
            r"    - name: Require a release tag\n.*?      run: \|\n((?:        [^\n]*\n)+)",
            contents,
            re.DOTALL,
        )
        if match is None:
            raise AssertionError("Release guard must remain a literal shell block")
        cls.guard = "\n".join(line[8:] for line in match[1].splitlines())

    def run_guard(
        self, event="workflow_dispatch", ref="refs/heads/main", tag="", branch="main"
    ):
        env = dict(
            os.environ,
            EVENT_NAME=event,
            REF=ref,
            REF_TYPE="tag" if ref.startswith("refs/tags/") else "branch",
            RELEASE_TAG=tag,
            DEFAULT_BRANCH=branch,
        )
        return subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", self.guard],
            env=env,
            capture_output=True,
            text=True,
        ).returncode

    def test_accepts_existing_tag_event_paths(self):
        for event in ("push", "workflow_dispatch"):
            with self.subTest(event=event):
                self.assertEqual(self.run_guard(event=event, ref="refs/tags/v0.1.4"), 0)

    def test_requires_explicit_tag_for_branch_dispatch(self):
        self.assertNotEqual(self.run_guard(), 0)
        self.assertEqual(self.run_guard(tag="v0.1.4"), 0)

    def test_override_requires_manual_default_branch(self):
        for event, ref in (
            ("push", "refs/heads/main"),
            ("pull_request", "refs/heads/main"),
            ("workflow_dispatch", "refs/heads/feature"),
            ("workflow_dispatch", "refs/tags/v0.1.4"),
        ):
            with self.subTest(event=event, ref=ref):
                self.assertNotEqual(
                    self.run_guard(event=event, ref=ref, tag="v0.1.4"), 0
                )
        self.assertEqual(
            self.run_guard(ref="refs/heads/stable", tag="v0.1.4", branch="stable"), 0
        )

    def test_rejects_invalid_git_tag_refs(self):
        for tag in ("../main", "v0.1.4\n", "v0.1.4^{commit}", "v0.1.4:main"):
            with self.subTest(tag=tag):
                self.assertNotEqual(self.run_guard(tag=tag), 0)
