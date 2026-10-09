"""End-to-end backup tests with a local stand-in for object storage."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import main as backup_main
from scripts import restore_backup
from scripts.git_backup import smoke_test_restore


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def list_keys(self, prefix: str) -> list[str]:
        return [
            str(path.relative_to(self.root))
            for path in self.root.rglob("*")
            if path.is_file() and str(path.relative_to(self.root)).startswith(prefix)
        ]

    def upload_file(self, source: Path, key: str) -> None:
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    def download_file(self, key: str, destination: Path) -> None:
        shutil.copy2(self.root / key, destination)


class BackupFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.storage = LocalStorage(self.root / "storage")
        self.workspace = self.root / "workspace"
        origin = self.root / "origin.git"
        self.git("init", "--bare", "-b", "main", str(origin), cwd=self.root)
        self.git("init", "-b", "main", str(self.workspace), cwd=self.root)
        self.git("config", "user.name", "Backup Test", cwd=self.workspace)
        self.git("config", "user.email", "backup@example.test", cwd=self.workspace)
        self.git("remote", "add", "origin", str(origin), cwd=self.workspace)
        self.commit("initial")
        self.git("push", "-u", "origin", "main", cwd=self.workspace)
        self.environment = patch.dict(
            os.environ,
            {
                "GITHUB_WORKSPACE": str(self.workspace),
                "GITHUB_REPOSITORY": "validityBase/example",
                "GITHUB_RUN_ID": "101",
                "GITHUB_RUN_ATTEMPT": "1",
                "GITHUB_RUN_NUMBER": "1",
                "BACKUP_PREFIX": "github-backups",
                "BUNDLE_NAME": "repo.bundle",
                "OBJECT_STORAGE_ACCESS_KEY_ID": "test-id",
                "OBJECT_STORAGE_SECRET_ACCESS_KEY": "test-key",
                "OBJECT_STORAGE_BUCKET_NAME": "test-bucket",
                "OBJECT_STORAGE_ENDPOINT_URL": "https://s3.example.test",
                "OBJECT_STORAGE_REGION": "test-region",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    @staticmethod
    def git(*args: str, cwd: Path) -> str:
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=True,
        ).stdout.strip()

    def commit(self, content: str) -> None:
        (self.workspace / "file.txt").write_text(content + "\n", encoding="utf-8")
        self.git("add", "file.txt", cwd=self.workspace)
        self.git("commit", "-m", content, cwd=self.workspace)

    def run_backup(self, run_id: str) -> dict[str, object]:
        with patch.dict(os.environ, {"GITHUB_RUN_ID": run_id}):
            with patch.object(
                backup_main, "ObjectStorageUploader", return_value=self.storage
            ):
                backup_main.run()
        for path in self.storage.root.rglob("metadata.json"):
            metadata = json.loads(path.read_text(encoding="utf-8"))
            if metadata["github_run_id"] == run_id:
                return metadata
        self.fail(f"Missing metadata for GitHub run {run_id}.")

    def test_monthly_full_then_daily_incremental(self) -> None:
        first = self.run_backup("101")
        self.assertEqual("full", first["backup_type"])
        full_bundle = self.storage.root / first["remote_prefix"] / "repo.bundle"
        self.assertTrue(full_bundle.is_file())
        full_keys = set(self.storage.list_keys(first["remote_prefix"]))
        full_contents = {
            key: (self.storage.root / key).read_bytes() for key in full_keys
        }

        self.commit("second")
        self.git("push", "origin", "main", cwd=self.workspace)
        second = self.run_backup("102")
        self.assertEqual("incremental", second["backup_type"])
        self.assertEqual(first["remote_prefix"], second["base_prefix"])
        self.assertEqual(full_keys, set(self.storage.list_keys(first["remote_prefix"])))
        for key, contents in full_contents.items():
            self.assertEqual(contents, (self.storage.root / key).read_bytes())
        delta_bundle = self.storage.root / second["remote_prefix"] / "repo.bundle"
        self.assertTrue(delta_bundle.is_file())
        full_metadata = self.storage.root / first["remote_prefix"] / "metadata.json"
        daily_metadata = self.storage.root / second["remote_prefix"] / "metadata.json"
        smoke_test_restore(
            self.workspace, delta_bundle, second["refs"], full_bundle,
        )
        restored = self.root / "restored.git"
        with patch.object(
            sys,
            "argv",
            [
                "restore_backup",
                "--full-bundle", str(full_bundle),
                "--full-metadata", str(full_metadata),
                "--daily-bundle", str(delta_bundle),
                "--daily-metadata", str(daily_metadata),
                "--output", str(restored),
            ],
        ):
            restore_backup.main()
        self.assertEqual(
            self.git("rev-parse", "refs/heads/main", cwd=self.workspace),
            self.git("rev-parse", "refs/heads/main", cwd=restored),
        )

        full_bundle.unlink()
        third = self.run_backup("103")
        self.assertEqual("full", third["backup_type"])

    def test_unchanged_day_needs_only_metadata(self) -> None:
        full = self.run_backup("101")
        daily = self.run_backup("102")
        self.assertEqual("incremental", daily["backup_type"])
        self.assertEqual(full["remote_prefix"], daily["base_prefix"])
        self.assertIsNone(daily["bundle_file"])
        self.assertFalse(
            (self.storage.root / daily["remote_prefix"] / "repo.bundle").exists()
        )

        restored = self.root / "restored-unchanged.git"
        full_dir = self.storage.root / full["remote_prefix"]
        daily_dir = self.storage.root / daily["remote_prefix"]
        with patch.object(
            sys,
            "argv",
            [
                "restore_backup",
                "--full-bundle", str(full_dir / "repo.bundle"),
                "--full-metadata", str(full_dir / "metadata.json"),
                "--daily-metadata", str(daily_dir / "metadata.json"),
                "--output", str(restored),
            ],
        ):
            restore_backup.main()
        self.assertEqual(
            self.git("rev-parse", "main", cwd=self.workspace),
            self.git("rev-parse", "main", cwd=restored),
        )

    def test_new_month_starts_with_full_bundle(self) -> None:
        with patch.object(backup_main, "datetime") as clock:
            clock.now.return_value = datetime(2026, 10, 31, tzinfo=timezone.utc)
            self.run_backup("101")
            clock.now.return_value = datetime(2026, 11, 1, tzinfo=timezone.utc)
            next_month = self.run_backup("102")
        self.assertEqual("full", next_month["backup_type"])
        self.assertIn("/2026/11/full/", next_month["remote_prefix"])

    def test_corrupt_monthly_bundle_is_replaced(self) -> None:
        full = self.run_backup("101")
        bundle = self.storage.root / full["remote_prefix"] / "repo.bundle"
        bundle.write_bytes(b"corrupt")

        replacement = self.run_backup("102")
        self.assertEqual("full", replacement["backup_type"])
        self.assertNotEqual(full["remote_prefix"], replacement["remote_prefix"])


if __name__ == "__main__":
    unittest.main()
