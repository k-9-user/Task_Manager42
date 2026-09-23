"""Subprocess helper tests."""

import unittest
from unittest.mock import patch

from scripts.lib import process


class ProcessTests(unittest.TestCase):
    def test_run_passes_shell_metacharacters_as_literal_arguments(self):
        hostile_args = ["tool", "$(touch /tmp/injected)", ";", "`id`"]
        completed = unittest.mock.Mock(returncode=0, stdout="")

        with patch.object(process.subprocess, "run", return_value=completed) as run:
            process.run(hostile_args)

        self.assertEqual(run.call_args.args[0], hostile_args)
        self.assertIs(run.call_args.kwargs["shell"], False)


if __name__ == "__main__":
    unittest.main()
