"""Host-only tooling checks: no Docker, network, real secrets or file writes."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import dev


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.values = {
            "POSTGRES_DB": "taskmanager",
            "POSTGRES_USER": "user",
            "JWT_EXPIRATION": "3600",
            "OAUTH_GOOGLE_CLIENT_ID": "",
            "OAUTH_GOOGLE_REDIRECT_URI": "https://localhost:8443/api/auth/oauth/google/callback",
            "CORS_ORIGINS": "https://localhost:8443",
            "UPLOAD_DIR": "/app/uploads",
            "MAX_UPLOAD_SIZE_MB": "10",
            "FORWARDED_ALLOW_IPS": "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
            "BOOTSTRAP_ADMIN_EMAIL": "admin@example.com",
            "BOOTSTRAP_ADMIN_USERNAME": "admin",
            "VITE_API_URL": "https://localhost:8443",
        }
        password = "p" * 40
        self.secret_values = {
            "postgres_password": password,
            "database_url": f"postgresql://user:{password}@db:5432/taskmanager",
            "jwt_secret": "j" * 40,
            "oauth_session_secret": "o" * 40,
            "oauth_google_client_secret": "",
            "bootstrap_admin_password": "a" * 40,
        }

    def _write_example(self, root: Path) -> None:
        (root / ".env.example").write_text(
            "\n".join(f"{key}={value}" for key, value in self.values.items()) + "\n"
        )

    def test_disabled_oauth_warns_without_values(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            dev.validate_config(self.values, self.secret_values)
        self.assertIn("Google OAuth is disabled", output.getvalue())
        self.assertNotIn(self.secret_values["jwt_secret"], output.getvalue())

    def test_enabled_oauth_and_positive_bounds(self):
        self.values["OAUTH_GOOGLE_CLIENT_ID"] = "local-client"
        self.secret_values["oauth_google_client_secret"] = "local-secret"
        for number in ("1", "3600", "9999999999"):
            with self.subTest(number=number), contextlib.redirect_stderr(io.StringIO()) as output:
                dev.validate_config(
                    self.values | {"JWT_EXPIRATION": number, "MAX_UPLOAD_SIZE_MB": number},
                    self.secret_values,
                )
                self.assertEqual(output.getvalue(), "")

    def test_invalid_config_is_rejected_without_values(self):
        env_cases = [(key, value) for key in ("JWT_EXPIRATION", "MAX_UPLOAD_SIZE_MB")
                     for value in ("", "0", "-1", "1.5", "no", "1e3")]
        env_cases += [("UPLOAD_DIR", "/tmp/uploads"), ("OAUTH_GOOGLE_REDIRECT_URI", ""),
                      ("OAUTH_GOOGLE_REDIRECT_URI", "http://localhost:8443/api/auth/oauth/google/callback"),
                      ("OAUTH_GOOGLE_REDIRECT_URI", "https://example.org/callback"),
                      ("OAUTH_GOOGLE_CLIENT_ID", "unpaired-client"),
                      ("BOOTSTRAP_ADMIN_EMAIL", "invalid"),
                      ("BOOTSTRAP_ADMIN_USERNAME", "bad user"),
                      ("POSTGRES_DB", "taskmanager_test"), ("FORWARDED_ALLOW_IPS", "*")]
        for key, value in env_cases:
            with self.subTest(key=key, value=value):
                output = io.StringIO()
                with contextlib.redirect_stderr(output), self.assertRaises(ValueError) as error:
                    dev.validate_config(self.values | {key: value}, self.secret_values)
                for secret in (value for value in self.secret_values.values() if value):
                    self.assertNotIn(secret, str(error.exception) + output.getvalue())

        secret_cases = [
            ("database_url", "postgresql://private:credential@db:5432/other"),
            ("oauth_session_secret", self.secret_values["jwt_secret"]),
            ("jwt_secret", "replace_with_" + "x" * 40),
            ("bootstrap_admin_password", "too-short"),
        ]
        for key, value in secret_cases:
            with self.subTest(key=key), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(ValueError) as error:
                dev.validate_config(self.values, self.secret_values | {key: value})
            self.assertNotIn(value, str(error.exception))

    def test_missing_and_unknown_keys(self):
        for values in ({}, self.values | {"COMPOSE_PROFILES": "test"}):
            with self.assertRaises(ValueError):
                dev.validate_config(values, self.secret_values)
        for secrets in ({}, self.secret_values | {"unexpected": "secret"}):
            with self.assertRaises(ValueError):
                dev.validate_config(self.values, secrets)

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
        self.assertNotIn("JWT_SECRET", env)
        self.assertNotIn("COMPOSE_PROFILES", env)

    def test_invalid_config_fails_before_commands(self):
        with patch.object(dev, "read_env", return_value=self.values | {"JWT_EXPIRATION": "0"}), \
                patch.object(dev, "read_secret_files", return_value=self.secret_values), \
                patch.object(dev, "run") as run, self.assertRaises(ValueError):
            dev.check()
        run.assert_not_called()

    def test_fresh_setup_creates_private_secret_files_without_printing_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_example(root)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                dev.setup_configuration(root)

            self.assertEqual(dev.read_env(root / ".env"), self.values)
            secrets = dev.read_secret_files(root / "secrets")
            self.assertEqual(set(secrets), set(self.secret_values))
            self.assertEqual(secrets["database_url"], (
                f"postgresql://user:{secrets['postgres_password']}@db:5432/taskmanager"
            ))
            for value in (value for value in secrets.values() if value):
                self.assertNotIn(value, output.getvalue())
            self.assertEqual((root / "secrets").stat().st_mode & 0o777, 0o700)
            for name in secrets:
                self.assertEqual((root / "secrets" / name).stat().st_mode & 0o022, 0)

    def test_legacy_setup_moves_secrets_and_rewrites_env(self):
        legacy_secrets = {
            "POSTGRES_PASSWORD": self.secret_values["postgres_password"],
            "DATABASE_URL": self.secret_values["database_url"],
            "JWT_SECRET": self.secret_values["jwt_secret"],
            "OAUTH_SESSION_SECRET": self.secret_values["oauth_session_secret"],
            "OAUTH_GOOGLE_CLIENT_SECRET": "",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_example(root)
            legacy_env = {
                key: value for key, value in self.values.items()
                if key not in {"BOOTSTRAP_ADMIN_EMAIL", "BOOTSTRAP_ADMIN_USERNAME"}
            } | legacy_secrets
            (root / ".env").write_text(
                "\n".join(f"{key}={value}" for key, value in legacy_env.items()) + "\n"
            )

            dev.setup_configuration(root)

            self.assertEqual(dev.read_env(root / ".env"), self.values)
            migrated = dev.read_secret_files(root / "secrets")
            for old_name, new_name in dev.LEGACY_SECRET_NAMES.items():
                self.assertEqual(migrated[new_name], legacy_secrets[old_name])
            self.assertTrue(migrated["bootstrap_admin_password"])

    def test_new_format_setup_refuses_missing_secret_instead_of_regenerating(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_example(root)
            (root / ".env").write_text(
                "\n".join(f"{key}={value}" for key, value in self.values.items()) + "\n"
            )
            (root / "secrets").mkdir(mode=0o700)
            with self.assertRaisesRegex(ValueError, "missing"):
                dev.setup_configuration(root)

    def test_legacy_setup_refuses_conflicting_secret_without_rewriting_env(self):
        legacy_secrets = {
            "POSTGRES_PASSWORD": self.secret_values["postgres_password"],
            "DATABASE_URL": self.secret_values["database_url"],
            "JWT_SECRET": self.secret_values["jwt_secret"],
            "OAUTH_SESSION_SECRET": self.secret_values["oauth_session_secret"],
            "OAUTH_GOOGLE_CLIENT_SECRET": "",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_example(root)
            legacy_env = {
                key: value for key, value in self.values.items()
                if key not in {"BOOTSTRAP_ADMIN_EMAIL", "BOOTSTRAP_ADMIN_USERNAME"}
            } | legacy_secrets
            original = "\n".join(f"{key}={value}" for key, value in legacy_env.items()) + "\n"
            (root / ".env").write_text(original)
            (root / "secrets").mkdir(mode=0o700)
            (root / "secrets" / "jwt_secret").write_text("x" * 40)
            (root / "secrets" / "jwt_secret").chmod(0o644)

            with self.assertRaisesRegex(ValueError, "conflicts") as error:
                dev.setup_configuration(root)

            self.assertEqual((root / ".env").read_text(), original)
            self.assertNotIn(self.secret_values["jwt_secret"], str(error.exception))

    def test_secret_reader_rejects_public_directory_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            secret_dir = Path(temporary) / "secrets"
            secret_dir.mkdir(mode=0o755)
            with self.assertRaisesRegex(ValueError, "private"):
                dev.read_secret_files(secret_dir)

    def test_secret_reader_rejects_symlinks_and_unexpected_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            secret_dir = Path(temporary) / "secrets"
            secret_dir.mkdir(mode=0o700)
            target = Path(temporary) / "target"
            target.write_text("hidden")
            (secret_dir / "jwt_secret").symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlink"):
                dev.read_secret_files(secret_dir)

            (secret_dir / "jwt_secret").unlink()
            (secret_dir / "unexpected").write_text("hidden")
            with self.assertRaisesRegex(ValueError, "unexpected"):
                dev.read_secret_files(secret_dir)

    def test_secret_reader_redacts_decode_errors(self):
        with tempfile.TemporaryDirectory() as temporary:
            secret_dir = Path(temporary) / "secrets"
            secret_dir.mkdir(mode=0o700)
            for name, value in self.secret_values.items():
                path = secret_dir / name
                path.write_text(value)
                path.chmod(0o644)
            leaked = b"private-value-\xff"
            (secret_dir / "jwt_secret").write_bytes(leaked)
            (secret_dir / "jwt_secret").chmod(0o644)

            with self.assertRaisesRegex(ValueError, "jwt_secret is unreadable") as error:
                dev.read_secret_files(secret_dir)

            self.assertNotIn("private-value", str(error.exception))

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
