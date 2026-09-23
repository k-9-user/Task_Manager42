"""Host data directory tests."""

from pathlib import Path
import tempfile
import unittest

from scripts.lib import data as data_dirs
from scripts.lib import paths


class DataDirTests(unittest.TestCase):
    def test_ensure_data_dirs_creates_every_bound_directory_privately(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary) / "data"
            data_dirs.ensure_data_dirs(data)
            for name in paths.DATA_DIRS:
                directory = data / name
                self.assertTrue(directory.is_dir())
                self.assertEqual(directory.stat().st_mode & 0o077, 0)

    def test_ensure_data_dirs_is_idempotent_and_preserves_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary) / "data"
            data_dirs.ensure_data_dirs(data)
            (data / paths.DATA_DIRS[0] / "payload").write_text("state")
            data_dirs.ensure_data_dirs(data)
            self.assertEqual((data / paths.DATA_DIRS[0] / "payload").read_text(), "state")

    def test_ensure_data_dirs_refuses_symlinks_and_non_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "target").mkdir()

            linked = root / "linked-data"
            linked.symlink_to(root / "target")
            with self.assertRaisesRegex(ValueError, "must not be a symlink"):
                data_dirs.ensure_data_dirs(linked)

            child = root / "child-data"
            child.mkdir()
            (child / paths.DATA_DIRS[0]).symlink_to(root / "target")
            with self.assertRaisesRegex(ValueError, "must not be a symlink"):
                data_dirs.ensure_data_dirs(child)

            regular = root / "regular-data"
            regular.mkdir()
            (regular / paths.DATA_DIRS[0]).write_text("not a directory")
            with self.assertRaisesRegex(ValueError, "not a directory"):
                data_dirs.ensure_data_dirs(regular)

    def test_ensure_data_dirs_creates_the_backup_directory_privately(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary) / "data"
            data_dirs.ensure_data_dirs(data)
            self.assertTrue((data / paths.DATA_BACKUPS).is_dir())
            self.assertEqual((data / paths.DATA_BACKUPS).stat().st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
