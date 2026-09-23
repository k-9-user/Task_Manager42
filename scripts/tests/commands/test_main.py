"""Target dispatch tests: order of checks, confirmations and Compose calls."""

import unittest
from unittest.mock import patch

from scripts import commands
from scripts.commands import backup, check, cleanup, reset_db, setup
from scripts.lib import compose
from scripts.lib import data as data_dirs


class MainTests(unittest.TestCase):
    def test_missing_or_unknown_action_fails_before_setup(self):
        for argv in (["make.py"], ["make.py", "unknown"]):
            with self.subTest(argv=argv), patch.object(commands.sys, "argv", argv), \
                    patch.object(setup, "setup") as setup_target, self.assertRaisesRegex(ValueError, "Usage"):
                commands.main()
            setup_target.assert_not_called()

    def test_remote_reset_rejected_before_confirmation_or_daemon_commands(self):
        with patch.object(commands.sys, "argv", ["make.py", "reset-db"]), \
                patch.object(check, "check", side_effect=ValueError("Local Docker endpoint required")), \
                patch.object(reset_db, "reset_database") as reset, \
                patch("builtins.input") as confirm, \
                self.assertRaisesRegex(ValueError, "Local Docker endpoint required"):
            commands.main()
        reset.assert_not_called()
        confirm.assert_not_called()

    def test_backup_runs_the_backup_service_once_after_checks(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        events = []
        with patch.object(commands.sys, "argv", ["make.py", "backup"]), \
                patch.object(data_dirs, "ensure_data_dirs"), \
                patch.object(check, "check", side_effect=lambda: (events.append("check") or (env, "default"))), \
                patch.object(backup, "run", side_effect=lambda args, **_kwargs: events.append(args[len(compose.COMPOSE):])):
            commands.main()
        self.assertEqual(events, ["check", ["run", "--rm", "backup", "once"]])

    def test_restore_checks_then_restores_the_requested_backup_then_starts(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        events = []
        with patch.object(commands.sys, "argv", ["make.py", "restore"]), \
                patch.dict(backup.os.environ, {"BACKUP": "taskmanager-20260923T100000Z"}), \
                patch.object(data_dirs, "ensure_data_dirs"), \
                patch.object(backup, "read_env", return_value={"POSTGRES_DB": "taskmanager"}), \
                patch.object(check, "check", side_effect=lambda: (events.append("check") or (env, "default"))), \
                patch.object(backup, "restore_backup",
                             side_effect=lambda *args: events.append(("restore", *args[2:])) or args[3]), \
                patch.object(backup, "run", side_effect=lambda args, **_kwargs: events.append(args[len(compose.COMPOSE):])):
            commands.main()
        self.assertEqual(events, [
            "check",
            ("restore", "taskmanager", "taskmanager-20260923T100000Z"),
            ["up", "--build", "--detach", "--wait"],
        ])

    def test_remote_restore_rejected_before_confirmation(self):
        with patch.object(commands.sys, "argv", ["make.py", "restore"]), \
                patch.object(data_dirs, "ensure_data_dirs"), \
                patch.object(check, "check", side_effect=ValueError("Local Docker endpoint required")), \
                patch.object(backup, "restore_backup") as restore, \
                patch("builtins.input") as confirm, \
                self.assertRaisesRegex(ValueError, "Local Docker endpoint required"):
            commands.main()
        restore.assert_not_called()
        confirm.assert_not_called()

    def test_re_checks_before_destructive_cleanup_then_starts(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        events = []
        with patch.object(commands.sys, "argv", ["make.py", "re"]), \
                patch.object(check, "check", side_effect=lambda: (events.append("check") or (env, "default"))), \
                patch.object(cleanup, "fclean", side_effect=lambda *_args, **_kwargs: events.append("fclean")), \
                patch.object(cleanup, "run", side_effect=lambda *_args, **_kwargs: events.append("up")):
            commands.main()
        self.assertEqual(events, ["check", "fclean", "up"])


if __name__ == "__main__":
    unittest.main()
