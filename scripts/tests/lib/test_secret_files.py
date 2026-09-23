"""Secret file reader tests."""

from pathlib import Path
import tempfile
import unittest

from scripts.lib import secret_files
from scripts.tests.fixtures import valid_env, valid_secrets


class SecretFileTests(unittest.TestCase):
    def setUp(self):
        self.values, self.secret_values = valid_env(), valid_secrets()

    def test_secret_reader_rejects_public_directory_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            secret_dir = Path(temporary) / "secrets"
            secret_dir.mkdir(mode=0o755)
            with self.assertRaisesRegex(ValueError, "private"):
                secret_files.read_secret_files(secret_dir)

    def test_secret_reader_rejects_symlinks_and_unexpected_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            secret_dir = Path(temporary) / "secrets"
            secret_dir.mkdir(mode=0o700)
            target = Path(temporary) / "target"
            target.write_text("hidden")
            (secret_dir / "jwt_secret").symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlink"):
                secret_files.read_secret_files(secret_dir)

            (secret_dir / "jwt_secret").unlink()
            (secret_dir / "unexpected").write_text("hidden")
            with self.assertRaisesRegex(ValueError, "unexpected"):
                secret_files.read_secret_files(secret_dir)

    def test_secret_reader_redacts_decode_errors(self):
        with tempfile.TemporaryDirectory() as temporary:
            secret_dir = Path(temporary) / "secrets"
            secret_dir.mkdir(mode=0o700)
            for name, value in self.secret_values.items():
                path = secret_dir / name
                path.write_text(value)
                path.chmod(0o644)
            (secret_dir / "jwt_secret").write_bytes(b"private-value-\xff")
            (secret_dir / "jwt_secret").chmod(0o644)

            with self.assertRaisesRegex(ValueError, "jwt_secret is unreadable") as error:
                secret_files.read_secret_files(secret_dir)

            self.assertNotIn("private-value", str(error.exception))


if __name__ == "__main__":
    unittest.main()
