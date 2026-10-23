"""The same helpers must work with both package layouts and caller settings."""

import datetime
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from release import prepare_release, release_notes, repository_file


class ConfigurationTests(unittest.TestCase):
    def test_both_repositories_with_custom_changelog_and_tag_prefix(self):
        for version_file, current, expected in (
            ("src/vbase_api/_version.py", "0.1.3", "0.1.4"),
            ("vbase/_version.py", "1.0.1", "1.0.2"),
        ):
            with self.subTest(
                version_file=version_file
            ), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source = root / version_file
                source.parent.mkdir(parents=True)
                source.write_text(f'__version__ = "{current}"\n', encoding="utf-8")
                notes = root / "notes/CHANGES.md"
                notes.parent.mkdir()
                notes.write_text(
                    "# Changes\n\n## [Unreleased]\n\n### Fixed\n- Fix timeout.\n",
                    encoding="utf-8",
                )
                self.assertEqual(
                    prepare_release(
                        root,
                        "patch",
                        datetime.date(2026, 10, 23),
                        version_file=version_file,
                        changelog_file="notes/CHANGES.md",
                    ),
                    expected,
                )
                self.assertEqual(
                    release_notes(
                        root,
                        "release." + expected,
                        version_file=version_file,
                        changelog_file="notes/CHANGES.md",
                        tag_prefix="release.",
                    ),
                    "### Fixed\n- Fix timeout.\n",
                )

    def test_file_configuration_cannot_escape_caller_checkout(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for path in ("../version.py", str(root / "version.py"), ""):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    repository_file(root, path)

    def test_symlink_configuration_cannot_escape_caller_checkout(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "checkout"
            root.mkdir()
            (root / "version.py").symlink_to(Path(temp) / "outside.py")
            with self.assertRaises(ValueError):
                repository_file(root, "version.py")
