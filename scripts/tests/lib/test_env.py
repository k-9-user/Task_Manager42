""".env contract and parser tests."""

from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.lib import env, paths
from scripts.tests.fixtures import valid_env, valid_secrets


class EnvTests(unittest.TestCase):
    def setUp(self):
        self.values, self.secret_values = valid_env(), valid_secrets()

    def test_parser_rejects_shell_syntax_and_duplicates(self):
        for text in ("JWT_SECRET=$(id)", 'JWT_SECRET="quoted"', "JWT_SECRET=a\nJWT_SECRET=b",
                     "export JWT_SECRET=a", "JWT_SECRET=a # comment", "JWT_SECRET=`id`"):
            with self.subTest(text=text), patch.object(Path, "read_text", return_value=text), \
                    patch.object(Path, "is_file", return_value=True), self.assertRaises(ValueError):
                env.read_env(paths.ROOT / ".env")

    def test_data_directory_is_not_part_of_the_env_contract(self):
        self.assertNotIn("DATA_DIR", env.ENV_NAMES)
        self.assertEqual(set(self.values), set(env.ENV_NAMES))
        self.assertEqual(paths.DATA_DIRS, tuple(paths.DATA_VOLUMES.values()))
        self.assertNotIn(paths.DATA_BACKUPS, paths.DATA_VOLUMES.values())


if __name__ == "__main__":
    unittest.main()
