"""TLS, smoke, and command dispatch tests."""

import unittest
from unittest.mock import patch

from scripts.build import commands, core


def nonced_page(nonce, *, stamped=None, placeholder=False, preamble=True):
    """A frontend response as nginx returns it once sub_filter has run."""

    stamped = nonce if stamped is None else stamped
    headers = (
        "HTTP/2 200\r\n"
        "content-type: text/html\r\n"
        "content-security-policy: default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; style-src 'self' 'unsafe-inline'\r\n"
    )
    preamble_tag = f'<script type="module" nonce="{stamped}">injectIntoGlobalHook</script>' if preamble else '<script type="module">injectIntoGlobalHook</script>'
    body = (
        "<!doctype html>"
        + ("VITE_CSP_NONCE" if placeholder else "")
        + preamble_tag
        + '<div id="root"></div>'
        + f'<script src="/src/main.jsx" nonce="{stamped}"></script>'
    )
    return headers + "\r\n" + body


ROOT_PAGE = '<div id="root"></div><script src="/src/main.jsx"></script>'


class CommandTests(unittest.TestCase):
    def test_run_passes_shell_metacharacters_as_literal_arguments(self):
        hostile_args = ["tool", "$(touch /tmp/injected)", ";", "`id`"]
        completed = unittest.mock.Mock(returncode=0, stdout="")

        with patch.object(core.subprocess, "run", return_value=completed) as run:
            core.run(hostile_args)

        self.assertEqual(run.call_args.args[0], hostile_args)
        self.assertIs(run.call_args.kwargs["shell"], False)

    def test_nginx_applies_the_expected_csp_to_normal_and_rate_limited_responses(self):
        expected = (
            "add_header Content-Security-Policy \"default-src 'self'; "
            "script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' https: data:; font-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'self'\" always;"
        )
        config = (core.ROOT / "nginx/default.conf").read_text(encoding="utf-8")

        self.assertEqual(config.count(expected), 2)

    def test_invalid_config_fails_before_commands(self):
        with patch.object(commands.config, "read_env", return_value={}), \
                patch.object(commands.config, "validate_env", side_effect=ValueError("invalid")), \
                patch.object(commands, "run") as run, self.assertRaisesRegex(ValueError, "invalid"):
            commands.check()
        run.assert_not_called()

    def test_certificate_sans_accept_wrapped_output(self):
        commands.validate_certificate_sans(
            "X509v3 Subject Alternative Name:\n"
            "    DNS:localhost,\n"
            "    IP Address:127.0.0.1\n"
        )

    def test_certificate_sans_reject_empty_output_cleanly(self):
        with self.assertRaisesRegex(ValueError, "SAN must include"):
            commands.validate_certificate_sans("")

    def test_certificate_sans_reject_missing_name(self):
        for output in ("DNS:localhost", "IP Address:127.0.0.1"):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, "SAN must include"):
                commands.validate_certificate_sans(output)

    def test_smoke_rejects_untransformed_entry(self):
        with patch.object(commands, "run", side_effect=[
            '{"status":"ok","db":"ok"}',
            ROOT_PAGE,
            nonced_page("a" * 32), nonced_page("b" * 32),
            "import App from './App.jsx'; createRoot(root).render(<StrictMode />)",
        ]) as run, self.assertRaisesRegex(ValueError, "Vite-transformed"):
            commands.smoke()
        self.assertEqual(run.call_args.args[0][-1], "https://localhost/src/main.jsx")

    def test_smoke_rejects_missing_locale(self):
        with patch.object(commands, "run", side_effect=[
            '{"status":"ok","db":"ok"}',
            ROOT_PAGE,
            nonced_page("a" * 32), nonced_page("b" * 32),
            'import "/node_modules/.vite/deps/react.js"; import "/src/App.jsx"; createRoot(root);',
            '{}',
        ]) as run, self.assertRaisesRegex(ValueError, "locale"):
            commands.smoke()
        self.assertEqual(run.call_args.args[0][-1], "https://localhost/locales/en/translation.json")

    def test_smoke_rejects_a_broken_frontend_nonce_pipeline(self):
        cases = (
            ([nonced_page("a" * 32, placeholder=True)], "did not substitute"),
            ([nonced_page("a" * 32, stamped="c" * 32)], "do not match"),
            ([nonced_page("a" * 32, preamble=False)], "not nonced"),
            ([nonced_page("a" * 32), nonced_page("a" * 32)], "not unique per request"),
        )
        for pages, message in cases:
            with self.subTest(message=message), patch.object(commands, "run", side_effect=[
                '{"status":"ok","db":"ok"}', ROOT_PAGE, *pages,
            ]), self.assertRaisesRegex(ValueError, message):
                commands.smoke()

    def test_nginx_declares_a_per_request_nonce_for_the_frontend_only(self):
        config = (core.ROOT / "nginx/default.conf").read_text(encoding="utf-8")
        self.assertEqual(config.count("script-src 'self' 'nonce-$request_id'"), 1)
        self.assertEqual(config.count("sub_filter 'VITE_CSP_NONCE' $request_id;"), 1)
        self.assertEqual(config.count("sub_filter_once off;"), 1)
        self.assertNotIn("'unsafe-inline'; script-src", config)
        self.assertNotIn("script-src 'self' 'unsafe-inline'", config)

    def test_remote_reset_rejected_before_confirmation_or_daemon_commands(self):
        with patch.object(commands.sys, "argv", ["dev.py", "reset-db"]), \
                patch.object(commands, "check", side_effect=ValueError("Local Docker endpoint required")), \
                patch.object(commands.docker, "reset_database") as reset, \
                patch("builtins.input") as confirm, \
                self.assertRaisesRegex(ValueError, "Local Docker endpoint required"):
            commands.main()
        reset.assert_not_called()
        confirm.assert_not_called()

    def test_backup_runs_the_backup_service_once_after_checks(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        events = []
        with patch.object(commands.sys, "argv", ["make.py", "backup"]), \
                patch.object(commands.config, "ensure_data_dirs"), \
                patch.object(commands, "check", side_effect=lambda: (events.append("check") or (env, "default"))), \
                patch.object(commands, "run", side_effect=lambda args, **_kwargs: events.append(args[len(core.COMPOSE):])):
            commands.main()
        self.assertEqual(events, ["check", ["run", "--rm", "backup", "once"]])

    def test_restore_checks_then_restores_the_requested_backup_then_starts(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        events = []
        with patch.object(commands.sys, "argv", ["make.py", "restore"]), \
                patch.dict(commands.os.environ, {"BACKUP": "taskmanager-20260923T100000Z"}), \
                patch.object(commands.config, "ensure_data_dirs"), \
                patch.object(commands.config, "read_env", return_value={"POSTGRES_DB": "taskmanager"}), \
                patch.object(commands, "check", side_effect=lambda: (events.append("check") or (env, "default"))), \
                patch.object(commands.docker, "restore_backup",
                             side_effect=lambda *args: events.append(("restore", *args[2:])) or args[3]), \
                patch.object(commands, "run", side_effect=lambda args, **_kwargs: events.append(args[len(core.COMPOSE):])):
            commands.main()
        self.assertEqual(events, [
            "check",
            ("restore", "taskmanager", "taskmanager-20260923T100000Z"),
            ["up", "--build", "--detach", "--wait"],
        ])

    def test_remote_restore_rejected_before_confirmation(self):
        with patch.object(commands.sys, "argv", ["make.py", "restore"]), \
                patch.object(commands.config, "ensure_data_dirs"), \
                patch.object(commands, "check", side_effect=ValueError("Local Docker endpoint required")), \
                patch.object(commands.docker, "restore_backup") as restore, \
                patch("builtins.input") as confirm, \
                self.assertRaisesRegex(ValueError, "Local Docker endpoint required"):
            commands.main()
        restore.assert_not_called()
        confirm.assert_not_called()

    def test_re_checks_before_destructive_cleanup_then_starts(self):
        env = {"DOCKER_HOST": "unix:///var/run/docker.sock"}
        events = []
        with patch.object(commands.sys, "argv", ["dev.py", "re"]), \
                patch.object(commands, "check", side_effect=lambda: (events.append("check") or (env, "default"))), \
                patch.object(commands.docker, "fclean", side_effect=lambda *_args, **_kwargs: events.append("fclean")), \
                patch.object(commands, "run", side_effect=lambda *_args, **_kwargs: events.append("up")):
            commands.main()
        self.assertEqual(events, ["check", "fclean", "up"])

    def test_missing_or_unknown_action_fails_before_setup(self):
        for argv in (["dev.py"], ["dev.py", "unknown"]):
            with self.subTest(argv=argv), patch.object(commands.sys, "argv", argv), \
                    patch.object(commands, "setup") as setup, self.assertRaisesRegex(ValueError, "Usage"):
                commands.main()
            setup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
