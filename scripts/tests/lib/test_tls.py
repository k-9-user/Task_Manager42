"""TLS certificate checks."""

import unittest

from scripts.lib import tls


class TlsTests(unittest.TestCase):
    def test_certificate_sans_accept_wrapped_output(self):
        tls.validate_certificate_sans(
            "X509v3 Subject Alternative Name:\n"
            "    DNS:localhost,\n"
            "    IP Address:127.0.0.1\n"
        )

    def test_certificate_sans_reject_empty_output_cleanly(self):
        with self.assertRaisesRegex(ValueError, "SAN must include"):
            tls.validate_certificate_sans("")

    def test_certificate_sans_reject_missing_name(self):
        for output in ("DNS:localhost", "IP Address:127.0.0.1"):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, "SAN must include"):
                tls.validate_certificate_sans(output)


if __name__ == "__main__":
    unittest.main()
