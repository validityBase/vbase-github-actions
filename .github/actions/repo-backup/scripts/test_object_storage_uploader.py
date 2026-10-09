"""Check object-store lookup and download command construction."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.object_storage_uploader import ObjectStorageUploader


class ObjectStorageUploaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.uploader = ObjectStorageUploader(
            "access-key", "secret-key", "bucket", "https://s3.example.test", "region"
        )

    def test_lists_monthly_backup_keys(self) -> None:
        with patch.object(
            self.uploader,
            "_run_aws",
            return_value='{"Contents": [{"Key": "backups/repo/full/metadata.json"}]}',
        ) as run_aws:
            keys = self.uploader.list_keys("backups/repo/full/")

        self.assertEqual(["backups/repo/full/metadata.json"], keys)
        self.assertIn("list-objects-v2", run_aws.call_args.args)
        self.assertEqual(False, run_aws.call_args.kwargs["log_output"])

    def test_downloads_monthly_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "base" / "repo.bundle"
            with patch.object(self.uploader, "_run_aws") as run_aws:
                self.uploader.download_file(
                    "backups/repo/full/repo.bundle", destination
                )
            self.assertTrue(destination.parent.is_dir())

        self.assertIn(
            "s3://bucket/backups/repo/full/repo.bundle", run_aws.call_args.args
        )


if __name__ == "__main__":
    unittest.main()
