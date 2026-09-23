"""Local TLS pair: creation for setup, verification for check."""

import os
from pathlib import Path
import tempfile

from .paths import CERT, CERTS, KEY
from .process import require, run


def create_pair():
    require(CERT.exists() == KEY.exists(), "Incomplete TLS pair; restore it or remove both files before setup")
    if CERT.exists():
        print("Preserved existing TLS pair.")
        return

    CERTS.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(CERTS.stat().st_mode & 0o077 == 0, "nginx/certs must be private (chmod 700 nginx/certs)")
    with tempfile.TemporaryDirectory(dir=CERTS) as temporary:
        cert, key = Path(temporary) / "cert", Path(temporary) / "key"
        run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-days", "365", "-subj", "/CN=localhost", "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1",
            "-keyout", str(key), "-out", str(cert),
        ], quiet=True)

        for source, target in ((cert, CERT), (key, KEY)):
            source.chmod(0o644)
            os.link(source, target)

    print("Created local TLS pair; host trust store unchanged.")


def validate_certificate_sans(output):
    names = {
        name.strip()
        for line in output.splitlines()
        for name in line.split(",")
    }
    require(
        {"DNS:localhost", "IP Address:127.0.0.1"} <= names,
        "TLS certificate SAN must include localhost and 127.0.0.1; "
        "remove both local TLS files and run make setup to regenerate them",
    )


def verify_pair():
    require(CERT.is_file() and KEY.is_file() and os.access(CERT, os.R_OK) and os.access(KEY, os.R_OK), "Missing or unreadable TLS pair; run make setup")
    require(CERTS.stat().st_mode & 0o077 == 0, "nginx/certs must be private (chmod 700 nginx/certs)")
    require(all(path.stat().st_mode & 0o004 for path in (CERT, KEY)), "TLS files need read permission for unprivileged nginx inside private nginx/certs")
    run(["openssl", "x509", "-in", str(CERT), "-checkend", "0", "-noout"], quiet=True)
    san = run(["openssl", "x509", "-in", str(CERT), "-noout", "-ext", "subjectAltName"], quiet=True)
    validate_certificate_sans(san)
    public = run(["openssl", "x509", "-in", str(CERT), "-pubkey", "-noout"], quiet=True)
    private_public = run(["openssl", "pkey", "-in", str(KEY), "-passin", "pass:", "-pubout"], quiet=True)
    require(public == private_public, "TLS certificate and key do not match")
    run(["openssl", "verify", "-CAfile", str(CERT), str(CERT)], quiet=True)
