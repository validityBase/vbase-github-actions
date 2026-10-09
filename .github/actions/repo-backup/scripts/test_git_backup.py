"""Exercise full and incremental bundles against a real local Git repository."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import git_backup


class GitBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.workspace = self.root / "repo"
        self.git("init", "-b", "main", str(self.workspace), cwd=self.root)
        self.git("config", "user.name", "Backup Test", cwd=self.workspace)
        self.git("config", "user.email", "backup@example.test", cwd=self.workspace)
        (self.workspace / "file.txt").write_text("initial\n", encoding="utf-8")
        self.git("add", "file.txt", cwd=self.workspace)
        self.git("commit", "-m", "Initial", cwd=self.workspace)
        self.environment = patch.dict(
            os.environ,
            {
                "GITHUB_REPOSITORY": "validityBase/example",
                "GITHUB_RUN_ID": "101",
                "GITHUB_RUN_ATTEMPT": "1",
                "GITHUB_RUN_NUMBER": "1",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    @staticmethod
    def git(*args: str, cwd: Path) -> str:
        result = subprocess.run(
            ["git", *args], cwd=cwd, check=True,
            capture_output=True, text=True,
        )
        return result.stdout.strip()

    def test_full_and_incremental_restore_updated_and_deleted_refs(self) -> None:
        now = datetime(2026, 10, 9, tzinfo=timezone.utc)
        self.git("branch", "obsolete", cwd=self.workspace)
        full_refs = git_backup.snapshot_refs(self.workspace)
        full = git_backup.build_artifacts(
            self.workspace, "github-backups", "repo.bundle", "full", now,
        )
        self.assertIn("/2026/10/full/", full.remote_prefix)
        git_backup.create_and_verify_bundle(self.workspace, full.bundle_path)
        checksum = git_backup.write_checksum(full.bundle_path, full.sha256_path)
        git_backup.write_metadata(
            self.workspace, full, checksum, "full", None, full_refs,
        )
        git_backup.smoke_test_restore(self.workspace, full.bundle_path, full_refs)
        saved_full_bundle = self.root / "monthly.bundle"
        shutil.copy2(full.bundle_path, saved_full_bundle)
        self.assertEqual(
            "full", json.loads(full.metadata_path.read_text())["backup_type"],
        )
        prerequisites = git_backup.base_prerequisites(self.workspace, full_refs)
        self.assertFalse(git_backup.has_new_objects(self.workspace, prerequisites))

        self.git("branch", "-D", "obsolete", cwd=self.workspace)
        (self.workspace / "file.txt").write_text("updated\n", encoding="utf-8")
        self.git("add", "file.txt", cwd=self.workspace)
        self.git("commit", "-m", "Update", cwd=self.workspace)
        new_refs = git_backup.snapshot_refs(self.workspace)
        self.assertTrue(git_backup.has_new_objects(self.workspace, prerequisites))
        incremental = git_backup.build_artifacts(
            self.workspace, "github-backups", "repo.bundle", "incremental", now,
        )
        self.assertIn("/2026/10/09/", incremental.remote_prefix)
        self.assertNotIn("/full/", incremental.remote_prefix)
        git_backup.create_and_verify_bundle(
            self.workspace, incremental.bundle_path, prerequisites,
        )
        git_backup.smoke_test_restore(
            self.workspace, incremental.bundle_path, new_refs, saved_full_bundle,
        )

    def test_missing_base_commit_rejects_incremental(self) -> None:
        with self.assertRaisesRegex(ValueError, "not available locally"):
            git_backup.base_prerequisites(self.workspace, {"refs/heads/main": "0" * 40})


if __name__ == "__main__":
    unittest.main()
