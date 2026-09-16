"""Docker endpoint and guarded cleanup tests."""

import json
import unittest
from unittest.mock import patch

from scripts.build import core
from scripts.build import docker as docker_tools


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
        volumes = {
            "postgres_data": {"name": "task-manager_postgres_data"},
            "backend_uploads": {"name": "task-manager_backend_uploads"},
            "frontend_node_modules": {"name": "task-manager_frontend_node_modules"},
        }
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
        command = run.call_args.args[0]
        self.assertEqual(command[-4:], ["down", "--volumes", "--rmi", "local"])
        self.assertNotIn("all", command)

    def test_fclean_removes_verified_custom_image_left_by_compose(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        image = core.APP_IMAGES[0]
        with patch.object(docker_tools, "run", side_effect=[
            json.dumps({"volumes": {}}), "",
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
        with patch.object(docker_tools, "run", side_effect=[
            json.dumps({"volumes": {"postgres_data": {"name": name}}}),
            name + "\n",
            json.dumps([{"Labels": {}}]),
        ]), patch("builtins.input") as confirm, self.assertRaisesRegex(ValueError, "Refusing"):
            docker_tools.fclean(env, "default", confirmation="fclean")
        confirm.assert_not_called()

    def test_reset_confirms_target_and_keeps_all_commands_pinned(self):
        env = {"DOCKER_HOST": "unix:///Users/dev/.docker/run/docker.sock"}
        volume = "task-manager_postgres_data"
        results = [
            json.dumps({"volumes": {"postgres_data": {"name": volume}}}),
            json.dumps([{"Labels": {
                "com.docker.compose.project": "task-manager",
                "com.docker.compose.volume": "postgres_data",
            }}]),
            None,
            None,
            None,
        ]

        def confirm(prompt):
            for target in ("desktop-linux", env["DOCKER_HOST"], volume):
                self.assertIn(target, prompt)
            return "reset-db"

        with patch.object(docker_tools, "run", side_effect=results) as run, \
                patch("builtins.input", side_effect=confirm):
            docker_tools.reset_database(env, "desktop-linux")

        self.assertEqual(len(run.call_args_list), 5)
        for call in run.call_args_list:
            self.assertIs(call.kwargs["env"], env)
        self.assertEqual(run.call_args.args[0], ["docker", "volume", "rm", volume])


if __name__ == "__main__":
    unittest.main()
