"""make fclean tests: guarded removal of volumes, images and data."""

import json
import unittest
from unittest.mock import patch

from scripts.commands import cleanup
from scripts.lib import compose, paths
from scripts.tests.fixtures import bound_data, compose_volumes


class CleanupTests(unittest.TestCase):
    def test_fclean_verifies_project_volumes_and_removes_only_local_images(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        with bound_data() as data:
            volumes = compose_volumes(data)
            existing = "\n".join(item["name"] for item in volumes.values()) + "\n"
            inspections = [
                json.dumps([{"Labels": {
                    "com.docker.compose.project": "task-manager",
                    "com.docker.compose.volume": logical,
                }}])
                for logical in volumes
            ]
            with patch.object(cleanup, "run", side_effect=[
                json.dumps({"volumes": volumes}), existing, *inspections,
                "", "", None,
            ]) as run, patch("builtins.input", return_value="fclean") as confirm:
                cleanup.fclean(env, "default", confirmation="fclean")

            prompt = confirm.call_args.args[0]
            self.assertIn("database and uploads", prompt)
            for item in volumes.values():
                self.assertIn(item["name"], prompt)
            for subdirectory in paths.DATA_DIRS:
                self.assertIn(str(data / subdirectory), prompt)
                self.assertTrue((data / subdirectory).is_dir())
                self.assertEqual(list((data / subdirectory).iterdir()), [])
            command = run.call_args.args[0]
            self.assertEqual(command[-4:], ["down", "--volumes", "--rmi", "local"])
            self.assertNotIn("all", command)

    def test_fclean_removes_verified_custom_image_left_by_compose(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        image = compose.APP_IMAGES[0]
        with bound_data() as data, patch.object(cleanup, "run", side_effect=[
            json.dumps({"volumes": compose_volumes(data)}), "",
            "sha256:backend\n",
            json.dumps([{"Config": {"Labels": {
                "com.docker.compose.project": "task-manager",
            }}}]),
            "",
            None,
            "sha256:backend\n",
            None,
        ]) as run, patch("builtins.input", return_value="fclean"):
            cleanup.fclean(env, "default", confirmation="fclean")

        self.assertEqual(run.call_args.args[0], ["docker", "image", "rm", image])

    def test_fclean_refuses_unlabelled_volume_before_confirmation(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        name = "task-manager_postgres_data"
        with bound_data() as data:
            with patch.object(cleanup, "run", side_effect=[
                json.dumps({"volumes": {"postgres_data": dict(
                    compose_volumes(data)["postgres_data"], name=name)}}),
                name + "\n",
                json.dumps([{"Labels": {}}]),
            ]), patch("builtins.input") as confirm, \
                    self.assertRaisesRegex(ValueError, "Refusing"):
                cleanup.fclean(env, "default", confirmation="fclean")
            confirm.assert_not_called()
            for subdirectory in paths.DATA_DIRS:
                self.assertTrue((data / subdirectory / "payload").is_file())

    def test_fclean_refuses_device_outside_the_project_data_directory(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        with bound_data() as data:
            volumes = compose_volumes(data, device_override="/var/lib/elsewhere")
            existing = "\n".join(item["name"] for item in volumes.values()) + "\n"
            inspections = [
                json.dumps([{"Labels": {
                    "com.docker.compose.project": "task-manager",
                    "com.docker.compose.volume": logical,
                }}])
                for logical in volumes
            ]
            with patch.object(cleanup, "run", side_effect=[
                json.dumps({"volumes": volumes}), existing, *inspections, "", "",
            ]), patch("builtins.input") as confirm, \
                    self.assertRaisesRegex(ValueError, "is not bound to"):
                cleanup.fclean(env, "default", confirmation="fclean")
            confirm.assert_not_called()
            for subdirectory in paths.DATA_DIRS:
                self.assertTrue((data / subdirectory / "payload").is_file())

    def test_fclean_cancelled_confirmation_keeps_every_host_file(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        with bound_data() as data:
            volumes = compose_volumes(data)
            existing = "\n".join(item["name"] for item in volumes.values()) + "\n"
            inspections = [
                json.dumps([{"Labels": {
                    "com.docker.compose.project": "task-manager",
                    "com.docker.compose.volume": logical,
                }}])
                for logical in volumes
            ]
            with patch.object(cleanup, "run", side_effect=[
                json.dumps({"volumes": volumes}), existing, *inspections, "", "",
            ]), patch("builtins.input", return_value=""), \
                    self.assertRaisesRegex(ValueError, "Cleanup cancelled"):
                cleanup.fclean(env, "default", confirmation="fclean")
            for subdirectory in paths.DATA_DIRS:
                self.assertTrue((data / subdirectory / "payload").is_file())
                self.assertTrue((data / subdirectory / "nested" / "deep").is_file())

    def test_fclean_keeps_backups(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        with bound_data() as data:
            backup = data / paths.DATA_BACKUPS / "taskmanager-20260923T170000Z"
            backup.mkdir(parents=True)
            (backup / "database.sql.gz").write_text("state")
            volumes = compose_volumes(data)
            with patch.object(cleanup, "run", side_effect=[
                json.dumps({"volumes": volumes}), "", "", "", None,
            ]), patch("builtins.input", return_value="fclean") as confirm:
                cleanup.fclean(env, "default", confirmation="fclean")
            self.assertIn(f"Backups in {data / paths.DATA_BACKUPS} are kept", confirm.call_args.args[0])
            self.assertTrue((backup / "database.sql.gz").is_file())


if __name__ == "__main__":
    unittest.main()
