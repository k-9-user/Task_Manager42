"""TLS certificate checks."""

import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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

    def test_existing_pair_is_preserved_without_openssl(self):
        with tempfile.TemporaryDirectory() as temporary:
            certs = Path(temporary)
            cert, key = certs / "localhost.crt", certs / "localhost.key"
            cert.write_text("certificate")
            key.write_text("private key")
            with patch.object(tls, "CERTS", certs), patch.object(tls, "CERT", cert), \
                    patch.object(tls, "KEY", key), patch.object(tls, "run") as run, \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                tls.create_pair()

            run.assert_not_called()
            self.assertEqual((cert.read_text(), key.read_text()), ("certificate", "private key"))
            self.assertIn("Preserved existing TLS pair.", output.getvalue())


if __name__ == "__main__":
    unittest.main()
