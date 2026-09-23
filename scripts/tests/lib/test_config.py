"""Configuration validation tests."""

import contextlib
import io
import unittest

from scripts.lib import config, env
from scripts.tests.fixtures import valid_env, valid_secrets


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.values, self.secret_values = valid_env(), valid_secrets()

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
        env_cases = [(key, value) for key in ("JWT_EXPIRATION", "MAX_UPLOAD_SIZE_MB", "PASSWORD_MIN_LENGTH", "PASSWORD_MAX_LENGTH",
                                              "BACKUP_INTERVAL_MINUTES", "BACKUP_RETENTION")
                     for value in ("", "0", "00", "-1", "1.5", "no", "1e3")]
        env_cases += [("PASSWORD_MIN_LENGTH", "129"), ("PASSWORD_MAX_LENGTH", "5")]
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
            ("bootstrap_admin_password", "short"),
            ("bootstrap_admin_password", "a" * 129),
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

    def test_check_asks_for_setup_when_backup_keys_are_missing(self):
        old = {key: value for key, value in self.values.items() if key not in env.ADDED_ENV_NAMES}
        with self.assertRaisesRegex(ValueError, "run make setup"):
            config.validate_config(old, self.secret_values)


if __name__ == "__main__":
    unittest.main()
