"""Compose environment and local Docker endpoint tests."""

import json
import unittest
from unittest.mock import patch

from scripts.lib import compose, paths
from scripts.tests.fixtures import valid_env, valid_secrets


class ComposeTests(unittest.TestCase):
    def setUp(self):
        self.values, self.secret_values = valid_env(), valid_secrets()

    def test_application_images_use_project_role_names(self):
        self.assertEqual(
            compose.APP_IMAGES,
            ("task-manager-back:latest", "task-manager-front:latest"),
        )

    def test_host_override_pinned_without_context_lookup(self):
        for endpoint in ("unix:///var/run/docker.sock", "unix:///Users/dev/.docker/run/docker.sock",
                         "npipe:////./pipe/docker_engine"):
            with self.subTest(endpoint=endpoint), patch.object(compose, "run") as run:
                env, context = compose.local_docker_env({
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
                compose,
                "run",
                side_effect=[info] if source else ["desktop-linux\n", info],
            ) as run:
                env, context = compose.local_docker_env(source)
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
                    compose,
                    "run",
                    side_effect=["remote\n", info] if source == "default" else [info],
                ) as run, self.assertRaisesRegex(ValueError, "Local Docker endpoint required"):
                    compose.local_docker_env(env)
                self.assertTrue(all(call.args[0][1] == "context" for call in run.call_args_list))

    def test_host_environment_cannot_override_config(self):
        with patch.object(compose, "read_env", return_value=self.values), \
                patch.dict(compose.os.environ, {"JWT_SECRET": "host-value", "COMPOSE_PROFILES": "test"}):
            env = compose.compose_env()
        self.assertNotIn("JWT_SECRET", env)
        self.assertNotIn("COMPOSE_PROFILES", env)

    def test_compose_env_pins_the_data_directory_against_host_override(self):
        with patch.object(compose, "read_env", return_value=self.values), \
                patch.dict(compose.os.environ, {"DATA_DIR": "/tmp/somewhere-else"}):
            env = compose.compose_env()
        self.assertEqual(env["DATA_DIR"], str(paths.ROOT / "data"))


if __name__ == "__main__":
    unittest.main()
