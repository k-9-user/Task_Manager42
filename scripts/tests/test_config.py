"""Configuration and secret lifecycle tests."""

import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.build import config, core


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.values = {
            "POSTGRES_DB": "taskmanager",
            "POSTGRES_USER": "user",
            "JWT_EXPIRATION": "3600",
            "OAUTH_GOOGLE_CLIENT_ID": "",
            "OAUTH_GOOGLE_REDIRECT_URI": "https://localhost/api/auth/oauth/google/callback",
            "CORS_ORIGINS": "https://localhost",
            "UPLOAD_DIR": "/app/uploads",
            "MAX_UPLOAD_SIZE_MB": "10",
            "FORWARDED_ALLOW_IPS": "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
            "BOOTSTRAP_ADMIN_EMAIL": "admin@example.com",
            "BOOTSTRAP_ADMIN_USERNAME": "admin",
            "VITE_API_URL": "https://localhost",
        }
        password = "p" * 40
        self.secret_values = {
            "postgres_password": password,
            "database_url": f"postgresql://user:{password}@db:5432/taskmanager",
            "jwt_secret": "j" * 40,
            "oauth_session_secret": "o" * 40,
            "oauth_google_client_secret": "",
            "bootstrap_admin_password": "a" * 40,
        }

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

    def test_disabled_oauth_warns_without_values(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            config.validate_config(self.values, self.secret_values)
        self.assertIn("Google OAuth is disabled", output.getvalue())
        self.assertNotIn(self.secret_values["jwt_secret"], output.getvalue())

    def test_enabled_oauth_and_positive_bounds(self):
        self.values["OAUTH_GOOGLE_CLIENT_ID"] = "local-client"
        self.secret_values["oauth_google_client_secret"] = "local-secret"
        for number in ("1", "3600", "9999999999"):
            with self.subTest(number=number), contextlib.redirect_stderr(io.StringIO()) as output:
                config.validate_config(
                    self.values | {"JWT_EXPIRATION": number, "MAX_UPLOAD_SIZE_MB": number},
                    self.secret_values,
                )
                self.assertEqual(output.getvalue(), "")

    def test_invalid_config_is_rejected_without_values(self):
        env_cases = [(key, value) for key in ("JWT_EXPIRATION", "MAX_UPLOAD_SIZE_MB")
                     for value in ("", "0", "-1", "1.5", "no", "1e3")]
        env_cases += [
            ("UPLOAD_DIR", "/tmp/uploads"),
            ("OAUTH_GOOGLE_REDIRECT_URI", ""),
            ("OAUTH_GOOGLE_REDIRECT_URI", "http://localhost/api/auth/oauth/google/callback"),
            ("OAUTH_GOOGLE_REDIRECT_URI", "https://example.org/callback"),
            ("OAUTH_GOOGLE_CLIENT_ID", "unpaired-client"),
            ("BOOTSTRAP_ADMIN_EMAIL", "invalid"),
            ("BOOTSTRAP_ADMIN_USERNAME", "bad user"),
            ("POSTGRES_DB", "taskmanager_test"),
            ("FORWARDED_ALLOW_IPS", "*"),
        ]
        for key, value in env_cases:
            with self.subTest(key=key, value=value):
                output = io.StringIO()
                with contextlib.redirect_stderr(output), self.assertRaises(ValueError) as error:
                    config.validate_config(self.values | {key: value}, self.secret_values)
                for secret in (value for value in self.secret_values.values() if value):
                    self.assertNotIn(secret, str(error.exception) + output.getvalue())

        secret_cases = [
            ("database_url", "postgresql://private:credential@db:5432/other"),
            ("oauth_session_secret", self.secret_values["jwt_secret"]),
            ("jwt_secret", "replace_with_" + "x" * 40),
            ("bootstrap_admin_password", "too-short"),
        ]
        for key, value in secret_cases:
            with self.subTest(key=key), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(ValueError) as error:
                config.validate_config(self.values, self.secret_values | {key: value})
            self.assertNotIn(value, str(error.exception))

    def test_missing_and_unknown_keys(self):
        for values in ({}, self.values | {"COMPOSE_PROFILES": "test"}):
            with self.assertRaises(ValueError):
                config.validate_config(values, self.secret_values)
        for secrets in ({}, self.secret_values | {"unexpected": "secret"}):
            with self.assertRaises(ValueError):
                config.validate_config(self.values, secrets)

    def test_parser_rejects_shell_syntax_and_duplicates(self):
        for text in ("JWT_SECRET=$(id)", 'JWT_SECRET="quoted"', "JWT_SECRET=a\nJWT_SECRET=b",
                     "export JWT_SECRET=a", "JWT_SECRET=a # comment", "JWT_SECRET=`id`"):
            with self.subTest(text=text), patch.object(Path, "read_text", return_value=text), \
                    patch.object(Path, "is_file", return_value=True), self.assertRaises(ValueError):
                config.read_env(core.ROOT / ".env")

    def test_host_environment_cannot_override_config(self):
        with patch.object(config, "read_env", return_value=self.values), \
                patch.dict(config.os.environ, {"JWT_SECRET": "host-value", "COMPOSE_PROFILES": "test"}):
            env = config.compose_env()
        self.assertNotIn("JWT_SECRET", env)
        self.assertNotIn("COMPOSE_PROFILES", env)

    def test_fresh_setup_creates_private_secret_files_without_printing_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_example(root)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                config.setup_configuration(root)

            self.assertEqual(config.read_env(root / ".env"), self.values)
            secrets = config.read_secret_files(root / "secrets")
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
                if key not in {"BOOTSTRAP_ADMIN_EMAIL", "BOOTSTRAP_ADMIN_USERNAME"}
            } | core.LEGACY_LOCAL_URLS | legacy_secrets
            (root / ".env").write_text(
                "\n".join(f"{key}={value}" for key, value in legacy_env.items()) + "\n"
            )

            config.setup_configuration(root)

            self.assertEqual(config.read_env(root / ".env"), self.values)
            migrated = config.read_secret_files(root / "secrets")
            for old_name, new_name in core.LEGACY_SECRET_NAMES.items():
                self.assertEqual(migrated[new_name], legacy_secrets[old_name])
            self.assertTrue(migrated["bootstrap_admin_password"])

    def test_setup_migrates_exact_legacy_local_urls_without_changing_secrets(self):
        legacy_values = self.values | core.LEGACY_LOCAL_URLS
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_example(root)
            (root / ".env").write_text(
                "\n".join(f"{key}={value}" for key, value in legacy_values.items()) + "\n"
            )
            self._write_secret_files(root)

            config.setup_configuration(root)

            self.assertEqual(config.read_env(root / ".env"), self.values)
            self.assertEqual(config.read_secret_files(root / "secrets"), self.secret_values)

    def test_setup_rejects_mixed_local_url_migration_without_rewriting(self):
        mixed_values = self.values | {"CORS_ORIGINS": "https://localhost:8443"}
        original = "\n".join(f"{key}={value}" for key, value in mixed_values.items()) + "\n"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_example(root)
            (root / ".env").write_text(original)
            self._write_secret_files(root)

            with self.assertRaisesRegex(ValueError, "mixed or custom local URLs"):
                config.setup_configuration(root)

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
                config.setup_configuration(root)

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
                if key not in {"BOOTSTRAP_ADMIN_EMAIL", "BOOTSTRAP_ADMIN_USERNAME"}
            } | core.LEGACY_LOCAL_URLS | legacy_secrets
            original = "\n".join(f"{key}={value}" for key, value in legacy_env.items()) + "\n"
            (root / ".env").write_text(original)
            (root / "secrets").mkdir(mode=0o700)
            (root / "secrets" / "jwt_secret").write_text("x" * 40)
            (root / "secrets" / "jwt_secret").chmod(0o644)

            with self.assertRaisesRegex(ValueError, "conflicts") as error:
                config.setup_configuration(root)

            self.assertEqual((root / ".env").read_text(), original)
            self.assertNotIn(self.secret_values["jwt_secret"], str(error.exception))

    def test_secret_reader_rejects_public_directory_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            secret_dir = Path(temporary) / "secrets"
            secret_dir.mkdir(mode=0o755)
            with self.assertRaisesRegex(ValueError, "private"):
                config.read_secret_files(secret_dir)

    def test_secret_reader_rejects_symlinks_and_unexpected_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            secret_dir = Path(temporary) / "secrets"
            secret_dir.mkdir(mode=0o700)
            target = Path(temporary) / "target"
            target.write_text("hidden")
            (secret_dir / "jwt_secret").symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlink"):
                config.read_secret_files(secret_dir)

            (secret_dir / "jwt_secret").unlink()
            (secret_dir / "unexpected").write_text("hidden")
            with self.assertRaisesRegex(ValueError, "unexpected"):
                config.read_secret_files(secret_dir)

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
                config.read_secret_files(secret_dir)

            self.assertNotIn("private-value", str(error.exception))


if __name__ == "__main__":
    unittest.main()
