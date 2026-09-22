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

The frontend is enabled by default at **https://localhost**. Only Nginx
publishes ports, bound to `127.0.0.1:80` and `127.0.0.1:443`; its unprivileged
container keeps internal ports 8080/8443. HTTP redirects to HTTPS. The backend,
database and frontend have no published ports.
Nginx waits for healthy frontend and backend services; the backend waits for
the database and successful migrations.

Compose builds exactly two local application images: `task-manager-back:latest`
and `task-manager-front:latest`. There are no development/production image
variants; this repository ships one localhost runtime for each application role.

`setup` creates non-secret `.env` configuration and ignored file-backed Docker
secrets under `secrets/`. A legacy `.env` is validated and migrated without
rotating its database/signing values. Exact former `:8443` local URLs migrate
atomically to the default HTTPS port; mixed/custom URLs are refused. Other
new-format configuration is preserved and missing/conflicting files are refused.
Values in `.env` remain plain `KEY=value`; secret files contain one value without
a newline. Host environment
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
these checks; it now also fails outright, because the stateful volumes require
`DATA_DIR` and the Compose file declares it with `${DATA_DIR:?...}`. Use Make.
`down`, `logs`, and `ps` remain usable with expired TLS.

## Frontend CSP Nonce

The frontend is served under a nonce-based Content-Security-Policy. `script-src`
never allows `'unsafe-inline'`; instead nginx mints a unique nonce per request
from `$request_id`, names it in the policy it sends for `location /`, and
rewrites Vite's `VITE_CSP_NONCE` placeholder to the same value with `sub_filter`.
Vite stamps that placeholder on every script, style and preload tag it generates
— including the inline React Refresh preamble the dev server injects, which has
no counterpart in `frontend/index.html`. The placeholder is configured by
`html.cspNonce` in `frontend/vite.config.js`.

Three constraints keep this correct:

- `add_header` inside a `location` **replaces** every server-level `add_header`
  instead of merging, so `location /` repeats all four security headers. Only
  `script-src` differs from the server policy.
- `sub_filter` cannot rewrite a compressed body, so the frontend location clears
  `Accept-Encoding` upstream. `sub_filter_types` stays at its default
  `text/html`, so JavaScript and JSON responses are never rewritten.
- `style-src` keeps `'unsafe-inline'` and deliberately gains no nonce: adding a
  nonce source makes browsers ignore `'unsafe-inline'`, which breaks any
  stylesheet injected at runtime without the nonce.

The server-level policy is unchanged, so `/api/`, `/health`, `/docs`,
`/openapi.json` and the rate-limited responses keep the strict, nonce-free CSP.

**If a script is blocked, add the nonce to the tag — never add `'unsafe-inline'`
to `script-src`.** A blocked inline script produces a blank page and no
server-side error at all: nginx and Vite both log a clean 200. `make smoke` now
asserts the nonce pipeline (placeholder substituted, every script tag nonced,
tag nonce equal to the header nonce, and a different nonce on a second request),
but curl does not execute or enforce anything — only a browser can prove the
page actually renders.

## Persistent Host Data

The database cluster and uploaded attachments live on the host, under `data/` at
the repository root:

| Path | Compose volume | Contents |
|---|---|---|
| `data/postgres` | `postgres_data` | PostgreSQL 17 cluster (`PGDATA=.../data/pgdata`) |
| `data/uploads` | `backend_uploads` | Uploaded attachments |

Both are Compose named volumes bound to those directories with the `local`
driver (`type: none, o: bind`). Compose requires each `device` to be an absolute
path that already exists and never creates one, so every action except `setup`
calls `config.ensure_data_dirs()` first. It creates the directories at mode
0700, refuses symlinks and non-directories, and leaves existing content alone.

`config.compose_env()` pins `DATA_DIR` to `<repo>/data` **after** the host
environment is filtered, so a host `DATA_DIR` cannot redirect the stack — the
same posture the wrapper already takes on configuration and secrets. `DATA_DIR`
is deliberately not a `.env` key: the env contract in
`docs/00-contrat-commun.md` §3 is fixed.

`data/` is git-ignored. `frontend_node_modules` stays an ordinary Docker volume:
it is rebuilt by `npm ci` at image build, and binding it to the host shadows
that tree and breaks platform-native binaries.

A one-shot `init-data` service chowns `data/uploads` to uid 10001 before the
backend starts, because the backend container runs unprivileged and cannot
chown its own bind mount. The database needs no equivalent: the PostgreSQL
entrypoint starts as root and chowns `PGDATA` itself.

## Crash Behavior

`db`, `backend`, `frontend` and `nginx` use `restart: on-failure:5`. That covers
a non-zero exit, capped at five attempts so a crash loop stops instead of
spinning. `migrate`, `bootstrap-admin` and `init-data` stay `restart: "no"`.
Four limits are deliberate and worth knowing, each observed rather than assumed:

- A restart policy reacts to **process termination only**. A container that
  hangs, or that reports `unhealthy` while its PID 1 stays alive, is not
  restarted; that behavior belongs to Swarm, not standalone Compose. Healing on
  `unhealthy` would need a sidecar holding the Docker socket, which this
  localhost stack does not take on.
- Docker ignores the restart policy for a container stopped by hand. `docker
  kill` and `docker stop` count as manual stops, so they are **not** a valid way
  to test the policy: the container exits 137 and stays down with
  `RestartCount` at 0. Verify the policy with a container that exits on its own.
- **A `SIGQUIT` immediate shutdown of PostgreSQL exits 0**, so `on-failure` does
  not restart the database in that path. The policy covers a genuine abnormal
  exit (OOM kill, a failure to start), not every route to a dead database. If
  the database coming back in every case matters more than a bounded retry
  count, `unless-stopped` is the policy that also covers a zero exit.
- `depends_on: {condition: service_healthy, restart: true}` fires on explicit
  Compose operations, not on a daemon-driven restart. After an autonomous `db`
  restart the backend is not bounced and relies on SQLAlchemy reconnecting.

`db` stops with `SIGINT` and a 30 s grace period. Docker's default `SIGTERM` is
a PostgreSQL *smart* shutdown that waits for clients and is routinely killed at
the grace period, forcing WAL recovery on the next start; `SIGINT` is a *fast*
shutdown that checkpoints first. After a genuine crash, WAL replay at startup is
the only automatic repair in this stack — nothing repairs uploads, and a partial
restore of one directory without the other can leave `attachments` rows pointing
at missing files.

`make up` stays safely repeatable on existing data: `alembic upgrade head` is a
no-op at head, and `bootstrap-admin` verifies rather than rewrites the first
account.

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

`scripts/dev.py` is only the command entry point. Implementation lives under
`scripts/localdev/`: shared process helpers, configuration/secret lifecycle,
Docker safety, and command orchestration are separated by concern. Host tests
mirror those boundaries under `scripts/tests/`; `scripts/test_dev.py` remains
the compatibility aggregator.

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
writers, removes only the `db` container and its `postgres_data` volume, then
empties `data/postgres`. Uploads and frontend dependencies are left intact. If
no database volume exists, there is nothing to reset: use `make up`. Changing
file-backed database credentials does not update an existing PostgreSQL cluster;
restore the matching credentials or explicitly reset the disposable dev database.

Erasing the host directory is required, not incidental: `docker volume rm` on a
bind-backed volume removes only the volume object and leaves the cluster on
disk, so without it the next `make up` would silently re-adopt the old data.
Before deleting anything, `docker._bound_data_dir()` requires that the path came
from the Compose-resolved `device`, that it matches `<repo>/data/<name>`, that
its parent is exactly `<repo>/data`, and that it is a real directory rather than
a symlink. The directory itself is kept so the bind device stays valid. Both
prompts list the host directories they will erase.

Normal `make down` preserves all data, including the dev database and uploads.
`make clean` is the same operation. `make fclean` and `make re` are intentionally
destructive: after checking project volume labels and the bound paths, and
requiring the exact target name, they remove the development database, uploaded
files, frontend dependency volume and locally built application images, and
empty `data/postgres` and `data/uploads`. They preserve `.env`, secret files,
TLS files, source and pulled images. Use `make reset-db` when only the database
should be removed.
