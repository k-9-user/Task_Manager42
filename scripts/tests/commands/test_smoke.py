"""make smoke and nginx CSP tests."""

import unittest
from unittest.mock import patch

from scripts.commands import smoke
from scripts.lib import paths
from scripts.tests.fixtures import ROOT_PAGE, nonced_page


class SmokeTests(unittest.TestCase):
    def test_nginx_applies_the_expected_csp_to_normal_and_rate_limited_responses(self):
        expected = (
            "add_header Content-Security-Policy \"default-src 'self'; "
            "script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' https: data: blob:; font-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'self'\" always;"
        )
        config = (paths.ROOT / "nginx/default.conf").read_text(encoding="utf-8")

        self.assertEqual(config.count(expected), 2)

    def test_nginx_declares_a_per_request_nonce_for_the_frontend_only(self):
        config = (paths.ROOT / "nginx/default.conf").read_text(encoding="utf-8")
        self.assertEqual(config.count("script-src 'self' 'nonce-$request_id'"), 1)
        self.assertEqual(config.count("sub_filter 'VITE_CSP_NONCE' $request_id;"), 1)
        self.assertEqual(config.count("sub_filter_once off;"), 1)
        self.assertNotIn("'unsafe-inline'; script-src", config)
        self.assertNotIn("script-src 'self' 'unsafe-inline'", config)

    def test_smoke_rejects_untransformed_entry(self):
        with patch.object(smoke, "run", side_effect=[
            '{"status":"ok","db":"ok"}',
            ROOT_PAGE,
            nonced_page("a" * 32), nonced_page("b" * 32),
            "import App from './App.jsx'; createRoot(root).render(<StrictMode />)",
        ]) as run, self.assertRaisesRegex(ValueError, "Vite-transformed"):
            smoke.smoke()
        self.assertEqual(run.call_args.args[0][-1], "https://localhost/src/main.jsx")

    def test_smoke_rejects_missing_locale(self):
        with patch.object(smoke, "run", side_effect=[
            '{"status":"ok","db":"ok"}',
            ROOT_PAGE,
            nonced_page("a" * 32), nonced_page("b" * 32),
            'import "/node_modules/.vite/deps/react.js"; import "/src/App.jsx"; createRoot(root);',
            '{}',
        ]) as run, self.assertRaisesRegex(ValueError, "locale"):
            smoke.smoke()
        self.assertEqual(run.call_args.args[0][-1], "https://localhost/locales/en/translation.json")

    def test_smoke_rejects_a_broken_frontend_nonce_pipeline(self):
        cases = (
            ([nonced_page("a" * 32, placeholder=True)], "did not substitute"),
            ([nonced_page("a" * 32, stamped="c" * 32)], "do not match"),
            ([nonced_page("a" * 32, preamble=False)], "not nonced"),
            ([nonced_page("a" * 32), nonced_page("a" * 32)], "not unique per request"),
        )
        for pages, message in cases:
            with self.subTest(message=message), patch.object(smoke, "run", side_effect=[
                '{"status":"ok","db":"ok"}', ROOT_PAGE, *pages,
            ]), self.assertRaisesRegex(ValueError, message):
                smoke.smoke()

    def test_smoke_accepts_a_vite_hmr_timestamp_on_the_entry_only(self):
        stamped = ROOT_PAGE.replace('main.jsx"', 'main.jsx?t=1790178147270"')
        with patch.object(smoke, "run", side_effect=[
            '{"status":"ok","db":"ok"}',
            stamped,
            nonced_page("a" * 32), nonced_page("b" * 32),
            "import App from './App.jsx'; createRoot(root).render(<StrictMode />)",
        ]), self.assertRaisesRegex(ValueError, "Vite-transformed"):
            smoke.smoke()

        for root in (ROOT_PAGE.replace("main.jsx", "other.jsx"), ROOT_PAGE.replace('main.jsx"', 'main.jsx?x=1"')):
            with self.subTest(root=root), patch.object(smoke, "run", side_effect=[
                '{"status":"ok","db":"ok"}', root,
            ]), self.assertRaisesRegex(ValueError, "source entry is missing"):
                smoke.smoke()


if __name__ == "__main__":
    unittest.main()
