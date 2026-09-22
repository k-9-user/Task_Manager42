"""TLS, smoke, and command dispatch tests."""

import unittest
from unittest.mock import patch

from scripts.build import commands, core


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
            '<div id="root"></div><script src="/src/main.jsx"></script>',
            "import App from './App.jsx'; createRoot(root).render(<StrictMode />)",
        ]) as run, self.assertRaisesRegex(ValueError, "Vite-transformed"):
            commands.smoke()
        self.assertEqual(run.call_args.args[0][-1], "https://localhost/src/main.jsx")

    def test_smoke_rejects_missing_locale(self):
        with patch.object(commands, "run", side_effect=[
            '{"status":"ok","db":"ok"}',
            '<div id="root"></div><script src="/src/main.jsx"></script>',
            'import "/node_modules/.vite/deps/react.js"; import "/src/App.jsx"; createRoot(root);',
            '{}',
        ]) as run, self.assertRaisesRegex(ValueError, "locale"):
            commands.smoke()
        self.assertEqual(run.call_args.args[0][-1], "https://localhost/locales/en/translation.json")

    def test_remote_reset_rejected_before_confirmation_or_daemon_commands(self):
        with patch.object(commands.sys, "argv", ["dev.py", "reset-db"]), \
                patch.object(commands, "check", side_effect=ValueError("Local Docker endpoint required")), \
                patch.object(commands.docker, "reset_database") as reset, \
                patch("builtins.input") as confirm, \
                self.assertRaisesRegex(ValueError, "Local Docker endpoint required"):
            commands.main()
        reset.assert_not_called()
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
