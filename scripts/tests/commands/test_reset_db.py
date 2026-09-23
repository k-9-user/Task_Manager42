"""make reset-db tests."""

import json
import unittest
from unittest.mock import patch

from scripts.commands import reset_db
from scripts.tests.fixtures import bound_data, compose_volumes


class ResetDbTests(unittest.TestCase):
    def test_reset_confirms_target_and_keeps_all_commands_pinned(self):
        env = {"DOCKER_HOST": "unix:///Users/dev/.docker/run/docker.sock"}
        volume = "task-manager_postgres_data"
        with bound_data() as data:
            results = [
                json.dumps({"volumes": compose_volumes(data)}),
                json.dumps([{"Labels": {
                    "com.docker.compose.project": "task-manager",
                    "com.docker.compose.volume": "postgres_data",
                }}]),
                None,
                None,
                None,
            ]

            def confirm(prompt):
                for target in ("desktop-linux", env["DOCKER_HOST"], volume,
                               str(data / "postgres")):
                    self.assertIn(target, prompt)
                return "reset-db"

            with patch.object(reset_db, "run", side_effect=results) as run, \
                    patch("builtins.input", side_effect=confirm):
                reset_db.reset_database(env, "desktop-linux")

            self.assertEqual(len(run.call_args_list), 5)
            for call in run.call_args_list:
                self.assertIs(call.kwargs["env"], env)
            self.assertEqual(run.call_args.args[0], ["docker", "volume", "rm", volume])
            self.assertEqual(list((data / "postgres").iterdir()), [])
            self.assertTrue((data / "uploads" / "payload").is_file())

    def test_reset_refuses_symlinked_database_directory(self):
        env = {"DOCKER_HOST": "unix:///Users/dev/.docker/run/docker.sock"}
        with bound_data() as data:
            volumes = compose_volumes(data)
            (data / "postgres" / "nested" / "deep").unlink()
            (data / "postgres" / "payload").unlink()
            (data / "postgres" / "nested").rmdir()
            (data / "postgres").rmdir()
            (data / "postgres").symlink_to(data / "uploads")
            with patch.object(reset_db, "run", side_effect=[
                json.dumps({"volumes": volumes}),
            ]), patch("builtins.input") as confirm, \
                    self.assertRaisesRegex(ValueError, "must not be a symlink"):
                reset_db.reset_database(env, "desktop-linux")
            confirm.assert_not_called()
            self.assertTrue((data / "uploads" / "payload").is_file())


if __name__ == "__main__":
    unittest.main()
