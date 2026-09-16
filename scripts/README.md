# Local Development

Prerequisites: Python 3 (standard library only), Make, Docker with Compose v2
supporting `up --wait`, a running Docker daemon, OpenSSL with `req -addext` and
`x509 -ext`, and curl. Run commands from the repository root.

```sh
make setup
make check
make up
make smoke
make test
make test TESTS='tests/test_foundation.py -k health'
make logs
make ps
make down
make clean
make fclean
make re
```

The frontend is enabled by default at **https://localhost:8443**. Only Nginx
publishes ports, bound to `127.0.0.1:8080` and `127.0.0.1:8443`. HTTP redirects
to HTTPS on 8443. The backend, database and frontend have no published ports.
Nginx waits for healthy frontend and backend services; the backend waits for
the database and successful migrations.

`setup` creates non-secret `.env` configuration and ignored file-backed Docker
secrets under `secrets/`. A legacy `.env` is validated and migrated without
rotating its database/signing values; a new-format configuration is preserved
and missing/conflicting files are refused. Values in `.env` remain plain
`KEY=value`; secret files contain one value without a newline. Host environment
variables cannot override checked configuration or secrets. OAuth credentials
remain optional: leave both client ID and secret file empty to disable Google
login. The redirect remains fixed at the localhost callback.

`setup` generates a 365-day self-signed certificate with localhost and
127.0.0.1 SANs. It never modifies the host trust store. A browser may warn;
`smoke` instead verifies TLS with `curl --cacert nginx/certs/localhost.crt`.
The host certificate directory is private (0700); its files are readable by
unprivileged Nginx via individual read-only bind mounts. Do not widen directory
permissions. To renew an expired pair, remove both local files and rerun setup.

`check` validates tools, daemon, exact env/secret manifests, private directory
and file permissions, placeholders, secret independence, DB consistency,
positive integer JWT expiration and upload limit,
the persistent `/app/uploads` path, local URLs, paired Google credentials,
IP/CIDR proxy allowlist, TLS readability/expiration/SAN/key pair,
and Compose configuration without printing secret-bearing output. It runs
before `up`, `test`, `smoke`, and `reset-db`. Direct `docker compose up` bypasses
these checks; use Make. `down`, `logs`, and `ps` remain usable with expired TLS.

Compose runs migrations, then a one-shot `bootstrap-admin`, then the backend.
The service creates the configured admin only in an empty database. On later
starts, the first account must match the configured identity, active admin role,
and password. Mismatches fail safely and require restoring matching credentials
or an explicitly confirmed reset; public registration never grants admin.

`test` builds the same backend development image before running pytest (no
source bind mount, so edits are included by rebuilding). The test-only profile
uses PostgreSQL 17 on an isolated internal network, tmpfs storage, no published
ports, and fixed test-only credentials. Both database URLs point exactly to
`taskmanager_test` on `test-db`. No dev env, uploads or dev database are mounted
into tests. The test database container is removed on completion, including
pytest failure. Do not run multiple test invocations concurrently in this
Compose project. `TESTS` is split into arguments, never executed as shell code.
Pytest writes its cache to `/tmp/pytest-cache`, not the image-owned `/app`.
Smoke performs only read-only health, frontend root, Vite-transformed entry,
English locale JSON and OpenAPI feature-family checks (including public API,
export/import and attachments); real JWT flows belong to the test suite.
These asset checks do not replace browser execution tests.

Run host-only configuration safety tests without containers or third-party
dependencies using `python3 -m unittest scripts.test_dev`.

## Resetting an Old Dev Database

The completed initial `db_install` revision requires a reset if the dev volume
was initialized with the old revision. Alembic cannot detect that its already
applied revision changed. **No reset is automatic.**

```sh
make reset-db
# Type reset-db at the prompt to confirm permanent dev database deletion.
make up
```

The reset checks the volume's Compose project and database labels, stops dev
writers, removes only the `db` container and its `postgres_data` volume, and
leaves uploads and frontend dependencies intact. If no database volume exists,
there is nothing to reset: use `make up`. Changing file-backed database credentials
does not update an existing PostgreSQL volume; restore the matching credentials
or explicitly reset the disposable dev database.

Normal `make down` preserves named volumes, including the dev database and
uploads. `make clean` is the same operation. `make fclean` and `make re` are
intentionally destructive: after checking project volume labels and requiring
the exact target name, they remove the development database, uploaded files,
frontend dependency volume and locally built application images. They preserve
`.env`, secret files, TLS files, source and pulled images. Use `make reset-db` when only the
database should be removed.
