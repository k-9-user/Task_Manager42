"""make restore tests."""

import unittest
from unittest.mock import patch

from scripts.commands import backup
from scripts.lib import compose, paths
from scripts.tests.fixtures import backups


class BackupTests(unittest.TestCase):
    env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
    older = "taskmanager-20260922T100000Z"
    newer = "taskmanager-20260923T100000Z"

    def test_restore_picks_latest_complete_backup_then_stops_writers_and_restores(self):
        with backups(self.older, self.newer, ".taskmanager-20260923T110000Z.partial",
                     "other-20260924T100000Z", "taskmanager-latest") as data:
            (data / paths.DATA_BACKUPS / "taskmanager-20260924T100000Z").symlink_to(data)
            with patch.object(backup, "run") as run, \
                    patch("builtins.input", return_value="restore") as confirm:
                name = backup.restore_backup(self.env, "desktop-linux", "taskmanager")

        self.assertEqual(name, self.newer)
        prompt = confirm.call_args.args[0]
        for text in ("desktop-linux", self.env["DOCKER_HOST"], f"{self.newer} (latest) (2 available)"):
            self.assertIn(text, prompt)
        self.assertEqual([call.args[0][len(compose.COMPOSE):] for call in run.call_args_list], [
            ["stop", "nginx", "backend", "backup"],
            ["--profile", "restore", "run", "--rm", "restore", self.newer],
            ["up", "--build", "--detach", "--wait"],
        ])
        for call in run.call_args_list:
            self.assertIs(call.kwargs["env"], self.env)

    def test_restore_honours_the_requested_backup(self):
        with backups(self.older, self.newer), patch.object(backup, "run") as run, \
                patch("builtins.input", return_value="restore"):
            backup.restore_backup(self.env, "default", "taskmanager", self.older)
        self.assertEqual(run.call_args_list[1].args[0][-1], self.older)

    def test_restore_rejects_unknown_names_before_confirmation(self):
        for requested in ("../postgres", f"{self.newer}/..", "other-20260923T100000Z",
                          ".taskmanager-20260923T110000Z.partial", "taskmanager-20260101T000000Z"):
            with self.subTest(requested=requested), \
                    backups(self.newer, ".taskmanager-20260923T110000Z.partial"), \
                    patch.object(backup, "run") as run, patch("builtins.input") as confirm, \
                    self.assertRaisesRegex(ValueError, "Unknown backup"):
                backup.restore_backup(self.env, "default", "taskmanager", requested)
            confirm.assert_not_called()
            run.assert_not_called()

    def test_restore_without_backups_or_confirmation_runs_nothing(self):
        cases = ((backups(), "", "No backup"), (backups(self.newer), "yes", "Restore cancelled"))
        for context, answer, message in cases:
            with self.subTest(message=message), context, \
                    patch.object(backup, "run") as run, \
                    patch("builtins.input", return_value=answer), \
                    self.assertRaisesRegex(ValueError, message):
                backup.restore_backup(self.env, "default", "taskmanager")
            run.assert_not_called()

    def test_failed_restore_still_restarts_the_stack_and_reports_the_error(self):
        steps = []

        def fake_run(args, **_kwargs):
            steps.append(args[len(compose.COMPOSE):][:2])
            if "restore" in args:
                raise ValueError("docker command failed (exit 1)")

        with backups(self.newer), patch.object(backup, "run", side_effect=fake_run), \
                patch("builtins.input", return_value="restore"), \
                self.assertRaisesRegex(ValueError, "exit 1"):
            backup.restore_backup(self.env, "default", "taskmanager")
        self.assertEqual(steps, [["stop", "nginx"], ["--profile", "restore"], ["up", "--build"]])


if __name__ == "__main__":
    unittest.main()
