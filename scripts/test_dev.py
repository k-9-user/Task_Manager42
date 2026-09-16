"""Host-only tooling checks: no Docker, network, real secrets or file writes."""

import contextlib
import io
import json
import unittest
from unittest.mock import patch

from scripts import dev


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.values = dev.read_env(dev.ROOT / ".env.example")
        self.values.update(JWT_SECRET="j" * 40, OAUTH_SESSION_SECRET="o" * 40,
                           POSTGRES_PASSWORD="p" * 40)
        self.values["DATABASE_URL"] = "postgresql://user:" + "p" * 40 + "@db:5432/taskmanager"

    def test_disabled_oauth_warns_without_values(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            dev.validate_env(self.values)
        self.assertIn("Google OAuth is disabled", output.getvalue())
        self.assertNotIn(self.values["JWT_SECRET"], output.getvalue())

    def test_enabled_oauth_and_positive_bounds(self):
        self.values.update(OAUTH_GOOGLE_CLIENT_ID="local-client", OAUTH_GOOGLE_CLIENT_SECRET="local-secret")
        for number in ("1", "3600", "9999999999"):
            with self.subTest(number=number), contextlib.redirect_stderr(io.StringIO()) as output:
                dev.validate_env(self.values | {"JWT_EXPIRATION": number, "MAX_UPLOAD_SIZE_MB": number})
                self.assertEqual(output.getvalue(), "")

    def test_invalid_config_is_rejected_without_values(self):
        cases = [(key, value) for key in ("JWT_EXPIRATION", "MAX_UPLOAD_SIZE_MB")
                 for value in ("", "0", "-1", "1.5", "no", "1e3")]
        cases += [("UPLOAD_DIR", "/tmp/uploads"), ("OAUTH_GOOGLE_REDIRECT_URI", ""),
                  ("OAUTH_GOOGLE_REDIRECT_URI", "http://localhost:8443/api/auth/oauth/google/callback"),
                  ("OAUTH_GOOGLE_REDIRECT_URI", "https://example.org/callback"),
                  ("OAUTH_GOOGLE_CLIENT_ID", "unpaired-client"),
                  ("OAUTH_GOOGLE_CLIENT_SECRET", "unpaired-secret"),
                  ("DATABASE_URL", "postgresql://private:credential@db:5432/other"),
                  ("OAUTH_SESSION_SECRET", self.values["JWT_SECRET"]),
                  ("JWT_SECRET", "replace_with_" + "x" * 40),
                  ("POSTGRES_DB", "taskmanager_test"), ("FORWARDED_ALLOW_IPS", "*")]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                output = io.StringIO()
                with contextlib.redirect_stderr(output), self.assertRaises(ValueError) as error:
                    dev.validate_env(self.values | {key: value})
                for secret in (self.values["JWT_SECRET"], self.values["POSTGRES_PASSWORD"],
                               "unpaired-secret", "private:credential"):
                    self.assertNotIn(secret, str(error.exception) + output.getvalue())

    def test_missing_and_unknown_keys(self):
        for values in ({}, self.values | {"COMPOSE_PROFILES": "test"}):
            with self.assertRaises(ValueError):
                dev.validate_env(values)

    def test_parser_rejects_shell_syntax_and_duplicates(self):
        for text in ("JWT_SECRET=$(id)", 'JWT_SECRET="quoted"', "JWT_SECRET=a\nJWT_SECRET=b",
                     "export JWT_SECRET=a", "JWT_SECRET=a # comment", "JWT_SECRET=`id`"):
            with self.subTest(text=text), patch.object(dev.Path, "read_text", return_value=text), \
                    patch.object(dev.Path, "is_file", return_value=True), self.assertRaises(ValueError):
                dev.read_env(dev.ROOT / ".env")

    def test_host_environment_cannot_override_config(self):
        with patch.object(dev, "read_env", return_value=self.values), \
                patch.dict(dev.os.environ, {"JWT_SECRET": "host-value", "COMPOSE_PROFILES": "test"}):
            env = dev.compose_env()
        self.assertEqual(env["JWT_SECRET"], self.values["JWT_SECRET"])
        self.assertNotIn("COMPOSE_PROFILES", env)

    def test_invalid_config_fails_before_commands(self):
        with patch.object(dev, "read_env", return_value=self.values | {"JWT_EXPIRATION": "0"}), \
                patch.object(dev, "run") as run, self.assertRaises(ValueError):
            dev.check()
        run.assert_not_called()

    def test_certificate_sans_accept_wrapped_output(self):
        dev.validate_certificate_sans(
            "X509v3 Subject Alternative Name:\n"
            "    DNS:localhost,\n"
            "    IP Address:127.0.0.1\n"
        )

    def test_certificate_sans_reject_empty_output_cleanly(self):
        with self.assertRaisesRegex(ValueError, "SAN must include"):
            dev.validate_certificate_sans("")

    def test_certificate_sans_reject_missing_name(self):
        for output in ("DNS:localhost", "IP Address:127.0.0.1"):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, "SAN must include"):
                dev.validate_certificate_sans(output)

    def test_smoke_rejects_untransformed_entry(self):
        with patch.object(dev, "run", side_effect=[
            '{"status":"ok","db":"ok"}',
            '<div id="root"></div><script src="/src/main.jsx"></script>',
            "import App from './App.jsx'; createRoot(root).render(<StrictMode />)",
        ]) as run, self.assertRaisesRegex(ValueError, "Vite-transformed"):
            dev.smoke()
        self.assertEqual(run.call_args.args[0][-1], "https://localhost:8443/src/main.jsx")

    def test_smoke_rejects_missing_locale(self):
        with patch.object(dev, "run", side_effect=[
            '{"status":"ok","db":"ok"}',
            '<div id="root"></div><script src="/src/main.jsx"></script>',
            'import "/node_modules/.vite/deps/react.js"; import "/src/App.jsx"; createRoot(root);',
            '{}',
        ]) as run, self.assertRaisesRegex(ValueError, "locale"):
            dev.smoke()
        self.assertEqual(run.call_args.args[0][-1], "https://localhost:8443/locales/en/translation.json")


class DockerSafetyTests(unittest.TestCase):
    def test_host_override_pinned_without_context_lookup(self):
        for endpoint in ("unix:///var/run/docker.sock", "unix:///Users/dev/.docker/run/docker.sock",
                         "npipe:////./pipe/docker_engine"):
            with self.subTest(endpoint=endpoint), patch.object(dev, "run") as run:
                env, context = dev.local_docker_env({"DOCKER_HOST": endpoint, "DOCKER_CONTEXT": ""})
                self.assertEqual(env["DOCKER_HOST"], endpoint)
                self.assertNotIn("DOCKER_CONTEXT", env)
                run.assert_not_called()

    def test_context_precedence_and_default_selection(self):
        endpoint = "unix:///Users/dev/.docker/run/docker.sock"
        info = json.dumps([{"Endpoints": {"docker": {"Host": endpoint}}}])
        for source in ({"DOCKER_CONTEXT": "desktop-linux", "DOCKER_HOST": "tcp://remote:2375"}, {}):
            with self.subTest(source=source), patch.object(dev, "run", side_effect=
                    [info] if source else ["desktop-linux\n", info]) as run:
                env, context = dev.local_docker_env(source)
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
                with self.subTest(endpoint=endpoint, source=source), patch.object(dev, "run", side_effect=
                        ["remote\n", info] if source == "default" else [info]) as run, \
                        self.assertRaisesRegex(ValueError, "Local Docker endpoint required"):
                    dev.local_docker_env(env)
                self.assertTrue(all(call.args[0][1] == "context" for call in run.call_args_list))

    def test_remote_reset_rejected_before_confirmation_or_daemon_commands(self):
        with patch.object(dev.sys, "argv", ["dev.py", "reset-db"]), \
                patch.object(dev, "validate_env"), patch.object(dev, "read_env"), \
                patch.object(dev, "tools"), patch.object(dev, "compose_env", return_value={"DOCKER_HOST": "tcp://localhost:2375"}), \
                patch.object(dev, "run") as run, patch("builtins.input") as confirm, \
                self.assertRaisesRegex(ValueError, "Local Docker endpoint required"):
            dev.main()
        run.assert_not_called()
        confirm.assert_not_called()

    def test_reset_confirms_target_and_keeps_all_commands_pinned(self):
        env = {"DOCKER_HOST": "unix:///Users/dev/.docker/run/docker.sock"}
        volume = "task-manager_postgres_data"
        results = [json.dumps({"volumes": {"postgres_data": {"name": volume}}}),
                   json.dumps([{"Labels": {"com.docker.compose.project": "task-manager",
                                          "com.docker.compose.volume": "postgres_data"}}]), None, None, None]
        def confirm(prompt):
            for target in ("desktop-linux", env["DOCKER_HOST"], volume):
                self.assertIn(target, prompt)
            # A host/context change during confirmation cannot redirect subsequent commands.
            dev.os.environ["DOCKER_CONTEXT"] = "remote"
            dev.os.environ["DOCKER_HOST"] = "tcp://remote:2375"
            return "reset-db"
        with patch.object(dev.sys, "argv", ["dev.py", "reset-db"]), \
                patch.object(dev, "check", return_value=(env, "desktop-linux")), \
                patch.object(dev, "run", side_effect=results) as run, \
                patch.dict(dev.os.environ), patch("builtins.input", side_effect=confirm), \
                contextlib.redirect_stdout(io.StringIO()):
            dev.main()
        self.assertEqual(len(run.call_args_list), 5)
        for call in run.call_args_list:
            self.assertIs(call.kwargs["env"], env)
        self.assertEqual(run.call_args.args[0], ["docker", "volume", "rm", volume])

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
        with patch.object(dev, "run", side_effect=[
            json.dumps({"volumes": volumes}), existing, *inspections,
            "", "", None,
        ]) as run, patch("builtins.input", return_value="fclean") as confirm:
            dev.fclean(env, "default", confirmation="fclean")

        prompt = confirm.call_args.args[0]
        self.assertIn("database and uploads", prompt)
        for item in volumes.values():
            self.assertIn(item["name"], prompt)
        command = run.call_args.args[0]
        self.assertEqual(command[-4:], ["down", "--volumes", "--rmi", "local"])
        self.assertNotIn("all", command)

    def test_fclean_removes_verified_custom_image_left_by_compose(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        image = dev.APP_IMAGES[0]
        with patch.object(dev, "run", side_effect=[
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
            dev.fclean(env, "default", confirmation="fclean")

        self.assertEqual(run.call_args.args[0], ["docker", "image", "rm", image])

    def test_fclean_refuses_unlabelled_volume_before_confirmation(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        name = "task-manager_postgres_data"
        with patch.object(dev, "run", side_effect=[
            json.dumps({"volumes": {"postgres_data": {"name": name}}}),
            name + "\n",
            json.dumps([{"Labels": {}}]),
        ]), patch("builtins.input") as confirm, self.assertRaisesRegex(ValueError, "Refusing"):
            dev.fclean(env, "default", confirmation="fclean")
        confirm.assert_not_called()

    def test_re_checks_before_destructive_cleanup_then_starts(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        events = []
        with patch.object(dev.sys, "argv", ["dev.py", "re"]), \
                patch.object(dev, "check", side_effect=lambda: (events.append("check") or (env, "default"))), \
                patch.object(dev, "fclean", side_effect=lambda *_args, **_kwargs: events.append("fclean")), \
                patch.object(dev, "run", side_effect=lambda *_args, **_kwargs: events.append("up")):
            dev.main()
        self.assertEqual(events, ["check", "fclean", "up"])

    def test_missing_or_unknown_action_fails_before_setup(self):
        for argv in (["dev.py"], ["dev.py", "unknown"]):
            with self.subTest(argv=argv), patch.object(dev.sys, "argv", argv), \
                    patch.object(dev, "setup") as setup, self.assertRaisesRegex(ValueError, "Usage"):
                dev.main()
            setup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
