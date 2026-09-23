"""make check tests."""

import unittest
from unittest.mock import patch

from scripts.commands import check


class CheckTests(unittest.TestCase):
    def test_invalid_config_fails_before_commands(self):
        with patch.object(check, "read_env", return_value={}), \
                patch.object(check, "validate_env", side_effect=ValueError("invalid")), \
                patch.object(check, "run") as run, self.assertRaisesRegex(ValueError, "invalid"):
            check.check()
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
