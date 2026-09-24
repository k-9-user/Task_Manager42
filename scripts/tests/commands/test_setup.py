"""make setup: configuration lifecycle tests."""

import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from scripts.commands import setup
from scripts.lib import env, secret_files
from scripts.tests.fixtures import valid_env, valid_secrets


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.values, self.secret_values = valid_env(), valid_secrets()

    def _write_example(self, root: Path) -> None:
        (root / ".env.example").write_text(
            "\n".join(f"{key}={value}" for key, value in self.values.items()) + "\n"
        )

    def _write_secret_files(self, root: Path) -> None:
        secret_dir = root / "secrets"
        secret_dir.mkdir(mode=0o700)
        for name, value in self.secret_values.items():
            path = secret_dir / name
            path.write_text(value)
            path.chmod(0o644)

    def test_setup_adds_missing_backup_keys_without_touching_other_values(self):
        custom = self.values | {"JWT_EXPIRATION": "7200"}
        old = {key: value for key, value in custom.items() if key not in env.ADDED_ENV_NAMES}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_example(root)
            (root / ".env").write_text("\n".join(f"{key}={value}" for key, value in old.items()) + "\n")
            self._write_secret_files(root)

            with contextlib.redirect_stdout(io.StringIO()) as output:
                setup.setup_configuration(root)

            self.assertEqual(env.read_env(root / ".env"), custom)
            self.assertEqual(secret_files.read_secret_files(root / "secrets"), self.secret_values)
            self.assertIn("Added new default settings", output.getvalue())

    def test_existing_configuration_is_left_untouched(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_example(root)
            original = "# local notes\n" + "\n".join(f"{key}={value}" for key, value in self.values.items()) + "\n"
            (root / ".env").write_text(original)
            self._write_secret_files(root)
            secrets_before = {path.name: path.read_bytes() for path in (root / "secrets").iterdir()}

            with contextlib.redirect_stdout(io.StringIO()) as output:
                setup.setup_configuration(root)

            self.assertEqual((root / ".env").read_text(), original)
            self.assertEqual({path.name: path.read_bytes() for path in (root / "secrets").iterdir()}, secrets_before)
            self.assertIn("Preserved existing .env and secret files.", output.getvalue())

    def test_fresh_setup_creates_private_secret_files_without_printing_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_example(root)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                setup.setup_configuration(root)

            self.assertEqual(env.read_env(root / ".env"), self.values)
            secrets = secret_files.read_secret_files(root / "secrets")
            self.assertEqual(set(secrets), set(self.secret_values))
            self.assertEqual(
                secrets["database_url"],
                f"postgresql://user:{secrets['postgres_password']}@db:5432/taskmanager",
            )
            for value in (value for value in secrets.values() if value):
                self.assertNotIn(value, output.getvalue())
            self.assertEqual((root / "secrets").stat().st_mode & 0o777, 0o700)
            for name in secrets:
                self.assertEqual((root / "secrets" / name).stat().st_mode & 0o022, 0)

    def test_legacy_setup_moves_secrets_and_rewrites_env(self):
        legacy_secrets = {
            "POSTGRES_PASSWORD": self.secret_values["postgres_password"],
            "DATABASE_URL": self.secret_values["database_url"],
            "JWT_SECRET": self.secret_values["jwt_secret"],
            "OAUTH_SESSION_SECRET": self.secret_values["oauth_session_secret"],
            "OAUTH_GOOGLE_CLIENT_SECRET": "",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_example(root)
            legacy_env = {
                key: value for key, value in self.values.items()
                if key not in {"BOOTSTRAP_ADMIN_EMAIL", "BOOTSTRAP_ADMIN_USERNAME", *env.ADDED_ENV_NAMES}
            } | env.LEGACY_LOCAL_URLS | legacy_secrets
            (root / ".env").write_text(
                "\n".join(f"{key}={value}" for key, value in legacy_env.items()) + "\n"
            )

            setup.setup_configuration(root)

            self.assertEqual(env.read_env(root / ".env"), self.values)
            migrated = secret_files.read_secret_files(root / "secrets")
            for old_name, new_name in secret_files.LEGACY_SECRET_NAMES.items():
                self.assertEqual(migrated[new_name], legacy_secrets[old_name])
            self.assertTrue(migrated["bootstrap_admin_password"])

    def test_setup_migrates_exact_legacy_local_urls_without_changing_secrets(self):
        legacy_values = self.values | env.LEGACY_LOCAL_URLS
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_example(root)
            (root / ".env").write_text(
                "\n".join(f"{key}={value}" for key, value in legacy_values.items()) + "\n"
            )
            self._write_secret_files(root)

            setup.setup_configuration(root)

            self.assertEqual(env.read_env(root / ".env"), self.values)
            self.assertEqual(secret_files.read_secret_files(root / "secrets"), self.secret_values)

    def test_setup_rejects_mixed_local_url_migration_without_rewriting(self):
        mixed_values = self.values | {"CORS_ORIGINS": "https://localhost:8443"}
        original = "\n".join(f"{key}={value}" for key, value in mixed_values.items()) + "\n"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_example(root)
            (root / ".env").write_text(original)
            self._write_secret_files(root)

            with self.assertRaisesRegex(ValueError, "mixed or custom local URLs"):
                setup.setup_configuration(root)

            self.assertEqual((root / ".env").read_text(), original)

    def test_new_format_setup_refuses_missing_secret_instead_of_regenerating(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_example(root)
            (root / ".env").write_text(
                "\n".join(f"{key}={value}" for key, value in self.values.items()) + "\n"
            )
            (root / "secrets").mkdir(mode=0o700)
            with self.assertRaisesRegex(ValueError, "missing"):
                setup.setup_configuration(root)

    def test_legacy_setup_refuses_conflicting_secret_without_rewriting_env(self):
        legacy_secrets = {
            "POSTGRES_PASSWORD": self.secret_values["postgres_password"],
            "DATABASE_URL": self.secret_values["database_url"],
            "JWT_SECRET": self.secret_values["jwt_secret"],
            "OAUTH_SESSION_SECRET": self.secret_values["oauth_session_secret"],
            "OAUTH_GOOGLE_CLIENT_SECRET": "",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_example(root)
            legacy_env = {
                key: value for key, value in self.values.items()
                if key not in {"BOOTSTRAP_ADMIN_EMAIL", "BOOTSTRAP_ADMIN_USERNAME", *env.ADDED_ENV_NAMES}
            } | env.LEGACY_LOCAL_URLS | legacy_secrets
            original = "\n".join(f"{key}={value}" for key, value in legacy_env.items()) + "\n"
            (root / ".env").write_text(original)
            (root / "secrets").mkdir(mode=0o700)
            (root / "secrets" / "jwt_secret").write_text("x" * 40)
            (root / "secrets" / "jwt_secret").chmod(0o644)

            with self.assertRaisesRegex(ValueError, "conflicts") as error:
                setup.setup_configuration(root)

            self.assertEqual((root / ".env").read_text(), original)
            self.assertNotIn(self.secret_values["jwt_secret"], str(error.exception))


if __name__ == "__main__":
    unittest.main()
