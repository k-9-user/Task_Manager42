"""Docker endpoint and guarded cleanup tests."""

import contextlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.build import core
from scripts.build import docker as docker_tools


@contextlib.contextmanager
def bound_data(populate=True):
    """Point the docker module at a throwaway data directory.

    docker.py imports DATA by value, so the patch has to land on that module.
    """

    with tempfile.TemporaryDirectory() as temporary:
        data = Path(temporary).resolve()
        for name in core.DATA_DIRS:
            directory = data / name
            directory.mkdir()
            if populate:
                (directory / "payload").write_text("state")
                (directory / "nested").mkdir()
                (directory / "nested" / "deep").write_text("state")
        with patch.object(docker_tools, "DATA", data):
            yield data


def compose_volumes(data, *, device_override=None):
    """Compose config payload matching a bound data directory."""

    volumes = {
        logical: {
            "name": f"task-manager_{logical}",
            "driver_opts": {"type": "none", "o": "bind",
                            "device": device_override or str(data / subdirectory)},
        }
        for logical, subdirectory in core.DATA_VOLUMES.items()
    }
    volumes["frontend_node_modules"] = {"name": "task-manager_frontend_node_modules"}
    return volumes


class DockerSafetyTests(unittest.TestCase):
    def test_application_images_use_project_role_names(self):
        self.assertEqual(
            core.APP_IMAGES,
            ("task-manager-back:latest", "task-manager-front:latest"),
        )

    def test_host_override_pinned_without_context_lookup(self):
        for endpoint in ("unix:///var/run/docker.sock", "unix:///Users/dev/.docker/run/docker.sock",
                         "npipe:////./pipe/docker_engine"):
            with self.subTest(endpoint=endpoint), patch.object(docker_tools, "run") as run:
                env, context = docker_tools.local_docker_env({
                    "DOCKER_HOST": endpoint,
                    "DOCKER_CONTEXT": "",
                })
                self.assertEqual(env["DOCKER_HOST"], endpoint)
                self.assertNotIn("DOCKER_CONTEXT", env)
                self.assertEqual(context, "DOCKER_HOST override")
                run.assert_not_called()

    def test_context_precedence_and_default_selection(self):
        endpoint = "unix:///Users/dev/.docker/run/docker.sock"
        info = json.dumps([{"Endpoints": {"docker": {"Host": endpoint}}}])
        for source in ({"DOCKER_CONTEXT": "desktop-linux", "DOCKER_HOST": "tcp://remote:2375"}, {}):
            with self.subTest(source=source), patch.object(
                docker_tools,
                "run",
                side_effect=[info] if source else ["desktop-linux\n", info],
            ) as run:
                env, context = docker_tools.local_docker_env(source)
                self.assertEqual(context, "desktop-linux")
                self.assertEqual(env["DOCKER_HOST"], endpoint)
                self.assertNotIn("DOCKER_CONTEXT", env)
                self.assertEqual(run.call_args.args[0], ["docker", "context", "inspect", "desktop-linux"])

    def test_remote_endpoints_rejected_from_host_or_context(self):
        for endpoint in ("tcp://remote:2375", "tcp://127.0.0.1:2375", "ssh://user@remote",
                         "npipe:////remote/pipe/docker_engine", "unix://remote/socket"):
            for source in ("host", "context", "default"):
                env = {"DOCKER_HOST": endpoint} if source == "host" else (
                    {"DOCKER_CONTEXT": "remote"} if source == "context" else {})
                info = json.dumps([{"Endpoints": {"docker": {"Host": endpoint}}}])
                with self.subTest(endpoint=endpoint, source=source), patch.object(
                    docker_tools,
                    "run",
                    side_effect=["remote\n", info] if source == "default" else [info],
                ) as run, self.assertRaisesRegex(ValueError, "Local Docker endpoint required"):
                    docker_tools.local_docker_env(env)
                self.assertTrue(all(call.args[0][1] == "context" for call in run.call_args_list))

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
            with patch.object(docker_tools, "run", side_effect=[
                json.dumps({"volumes": volumes}), existing, *inspections,
                "", "", None,
            ]) as run, patch("builtins.input", return_value="fclean") as confirm:
                docker_tools.fclean(env, "default", confirmation="fclean")

            prompt = confirm.call_args.args[0]
            self.assertIn("database and uploads", prompt)
            for item in volumes.values():
                self.assertIn(item["name"], prompt)
            for subdirectory in core.DATA_DIRS:
                self.assertIn(str(data / subdirectory), prompt)
                self.assertTrue((data / subdirectory).is_dir())
                self.assertEqual(list((data / subdirectory).iterdir()), [])
            command = run.call_args.args[0]
            self.assertEqual(command[-4:], ["down", "--volumes", "--rmi", "local"])
            self.assertNotIn("all", command)

    def test_fclean_removes_verified_custom_image_left_by_compose(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        image = core.APP_IMAGES[0]
        with bound_data() as data, patch.object(docker_tools, "run", side_effect=[
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
            docker_tools.fclean(env, "default", confirmation="fclean")

        self.assertEqual(run.call_args.args[0], ["docker", "image", "rm", image])

    def test_fclean_refuses_unlabelled_volume_before_confirmation(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        name = "task-manager_postgres_data"
        with bound_data() as data:
            with patch.object(docker_tools, "run", side_effect=[
                json.dumps({"volumes": {"postgres_data": dict(
                    compose_volumes(data)["postgres_data"], name=name)}}),
                name + "\n",
                json.dumps([{"Labels": {}}]),
            ]), patch("builtins.input") as confirm, \
                    self.assertRaisesRegex(ValueError, "Refusing"):
                docker_tools.fclean(env, "default", confirmation="fclean")
            confirm.assert_not_called()
            for subdirectory in core.DATA_DIRS:
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
            with patch.object(docker_tools, "run", side_effect=[
                json.dumps({"volumes": volumes}), existing, *inspections, "", "",
            ]), patch("builtins.input") as confirm, \
                    self.assertRaisesRegex(ValueError, "is not bound to"):
                docker_tools.fclean(env, "default", confirmation="fclean")
            confirm.assert_not_called()
            for subdirectory in core.DATA_DIRS:
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
            with patch.object(docker_tools, "run", side_effect=[
                json.dumps({"volumes": volumes}), existing, *inspections, "", "",
            ]), patch("builtins.input", return_value=""), \
                    self.assertRaisesRegex(ValueError, "Cleanup cancelled"):
                docker_tools.fclean(env, "default", confirmation="fclean")
            for subdirectory in core.DATA_DIRS:
                self.assertTrue((data / subdirectory / "payload").is_file())
                self.assertTrue((data / subdirectory / "nested" / "deep").is_file())

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

            with patch.object(docker_tools, "run", side_effect=results) as run, \
                    patch("builtins.input", side_effect=confirm):
                docker_tools.reset_database(env, "desktop-linux")

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
            with patch.object(docker_tools, "run", side_effect=[
                json.dumps({"volumes": volumes}),
            ]), patch("builtins.input") as confirm, \
                    self.assertRaisesRegex(ValueError, "must not be a symlink"):
                docker_tools.reset_database(env, "desktop-linux")
            confirm.assert_not_called()
            self.assertTrue((data / "uploads" / "payload").is_file())

    def test_fclean_keeps_backups(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        with bound_data() as data:
            backup = data / core.DATA_BACKUPS / "taskmanager-20260923T170000Z"
            backup.mkdir(parents=True)
            (backup / "database.sql.gz").write_text("state")
            volumes = compose_volumes(data)
            with patch.object(docker_tools, "run", side_effect=[
                json.dumps({"volumes": volumes}), "", "", "", None,
            ]), patch("builtins.input", return_value="fclean") as confirm:
                docker_tools.fclean(env, "default", confirmation="fclean")
            self.assertIn(f"Backups in {data / core.DATA_BACKUPS} are kept", confirm.call_args.args[0])
            self.assertTrue((backup / "database.sql.gz").is_file())


@contextlib.contextmanager
def backups(*names):
    with bound_data(populate=False) as data:
        directory = data / core.DATA_BACKUPS
        directory.mkdir()
        for name in names:
            (directory / name).mkdir()
        yield data


class RestoreTests(unittest.TestCase):
    env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
    older = "taskmanager-20260922T100000Z"
    newer = "taskmanager-20260923T100000Z"

    def test_restore_picks_latest_complete_backup_then_stops_writers_and_restores(self):
        with backups(self.older, self.newer, ".taskmanager-20260923T110000Z.partial",
                     "other-20260924T100000Z", "taskmanager-latest") as data:
            (data / core.DATA_BACKUPS / "taskmanager-20260924T100000Z").symlink_to(data)
            with patch.object(docker_tools, "run") as run, \
                    patch("builtins.input", return_value="restore") as confirm:
                name = docker_tools.restore_backup(self.env, "desktop-linux", "taskmanager")

        self.assertEqual(name, self.newer)
        prompt = confirm.call_args.args[0]
        for text in ("desktop-linux", self.env["DOCKER_HOST"], f"{self.newer} (latest) (2 available)"):
            self.assertIn(text, prompt)
        self.assertEqual([call.args[0][len(core.COMPOSE):] for call in run.call_args_list], [
            ["stop", "nginx", "backend", "backup"],
            ["--profile", "restore", "run", "--rm", "restore", self.newer],
        ])
        for call in run.call_args_list:
            self.assertIs(call.kwargs["env"], self.env)

    def test_restore_honours_the_requested_backup(self):
        with backups(self.older, self.newer), patch.object(docker_tools, "run") as run, \
                patch("builtins.input", return_value="restore"):
            docker_tools.restore_backup(self.env, "default", "taskmanager", self.older)
        self.assertEqual(run.call_args.args[0][-1], self.older)

    def test_restore_rejects_unknown_names_before_confirmation(self):
        for requested in ("../postgres", f"{self.newer}/..", "other-20260923T100000Z",
                          ".taskmanager-20260923T110000Z.partial", "taskmanager-20260101T000000Z"):
            with self.subTest(requested=requested), \
                    backups(self.newer, ".taskmanager-20260923T110000Z.partial"), \
                    patch.object(docker_tools, "run") as run, patch("builtins.input") as confirm, \
                    self.assertRaisesRegex(ValueError, "Unknown backup"):
                docker_tools.restore_backup(self.env, "default", "taskmanager", requested)
            confirm.assert_not_called()
            run.assert_not_called()

    def test_restore_without_backups_or_confirmation_runs_nothing(self):
        cases = ((backups(), "", "No backup"), (backups(self.newer), "yes", "Restore cancelled"))
        for context, answer, message in cases:
            with self.subTest(message=message), context, \
                    patch.object(docker_tools, "run") as run, \
                    patch("builtins.input", return_value=answer), \
                    self.assertRaisesRegex(ValueError, message):
                docker_tools.restore_backup(self.env, "default", "taskmanager")
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
