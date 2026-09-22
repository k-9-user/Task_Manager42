# Task Manager 42

## Description

Task Manager 42 is a collaborative project/task-management application built with React, FastAPI and PostgreSQL. Its intended workflow is to create projects, add members with owner/editor/viewer permissions, assign tasks and deadlines, track progress, search tasks, manage attachments and export personal or project data.


### Prerequisites

- Docker with Compose v2 supporting `up --wait`, and a running Docker daemon.
- Make and Python 3 (the local wrapper uses only the standard library).
- OpenSSL supporting `req -addext` and `x509 -ext`, plus curl.
- Latest stable Google Chrome for eventual mandatory browser verification.
- Free local ports 80 and 443; network access for container images/dependency downloads.

Run the following commands from the repository root. Application runtimes are containerized: Python 3.12, Node 24 and PostgreSQL 17. A host Node/Python backend environment is not needed for the container workflow. The root `package.json` is not the frontend application; its package lives in `frontend/`.

### Development quickstart

```sh
make setup
make check
make up
make smoke
```

`make setup` creates non-secret `.env` configuration plus independent ignored files under `secrets/` for the database URL/password, JWT and OAuth signing, optional Google client secret, and bootstrap-admin password. On a legacy install it validates and migrates existing `.env` secret values before atomically rewriting `.env`; it also migrates the exact former `:8443` local URLs to the default HTTPS port. Other new-format configuration and certificates are preserved; mixed/custom URLs and missing or conflicting secret files are refused rather than guessed or regenerated. Never commit credentials or private keys.

The wrapper accepts plain `KEY=value` entries in `.env`: no quotes, interpolation, inline comments, duplicates or undocumented keys. Secret files contain exactly one value without a newline. `make check` verifies the private directory, regular non-symlink files, permissions, placeholders, secret independence, Google pairing, and consistency between `database_url`, `postgres_password`, and non-secret `POSTGRES_*` values. Host variables cannot override checked configuration or secrets.

`make check` validates local tools, daemon, configuration, secrets, local URLs, certificate validity/SAN/key matching and Compose configuration. `make up` performs checks, builds and starts the development stack with the frontend enabled by default. Migrations and administrator bootstrap must complete before the backend starts; nginx waits for backend and frontend health.

Compose builds two local application images, `task-manager-back:latest` and `task-manager-front:latest`. This localhost-only stack has no development/production image variants.

**Use localhost only.** The canonical address is **https://localhost**. Only nginx publishes ports, on `127.0.0.1:80` and `127.0.0.1:443`; its unprivileged container listens internally on 8080/8443. HTTP redirects to HTTPS while preserving the request URI. Do not publish direct database/backend/frontend ports or turn this development stack into an Internet service. A one-shot service creates the configured first administrator after migrations; local and Google registrations always create ordinary users. Read the local bootstrap password from `secrets/bootstrap_admin_password` without sharing or committing it.

Existing databases are accepted only when their first account exactly matches the configured active administrator and bootstrap password. Otherwise startup fails without modifying users. For disposable incompatible development data, review `BOOTSTRAP_ADMIN_*`, obtain explicit approval, run `make reset-db`, then start the stack again. Reset is never automatic. Because the database now persists on the host, this matters beyond first boot: editing `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_USERNAME` or `secrets/bootstrap_admin_password` after the first start blocks every later `make up` until the matching credentials are restored or the database is explicitly reset.

### Persistent data

The database cluster and uploaded attachments live on the host under `data/` at the repository root: `data/postgres` for PostgreSQL and `data/uploads` for attachments. Both are Compose named volumes bound to those directories, which the Make wrapper creates (mode 0700) before every Compose call — Compose requires an absolute, pre-existing bind path and never creates one. `data/` is git-ignored; never commit it. The data survives `make down`, a container crash and a Docker daemon restart, and `make up` picks it straight back up. Only `make reset-db`, `make fclean` and `make re` erase it, each behind a typed confirmation that lists the directories. `DATA_DIR` is fixed to `<repo>/data` by the wrapper and is intentionally not an `.env` key; a host `DATA_DIR` cannot redirect the stack, and a bare `docker compose` command fails rather than binding an unintended path. The frontend dependency volume stays inside Docker: it is rebuilt at image build and does not belong on the host.

`db`, `backend`, `frontend` and `nginx` restart automatically on a non-zero exit, capped at five attempts. The coverage is narrower than it sounds: a restart policy reacts to process exit only, so a hung or `unhealthy` container whose main process is still alive is not restarted; Docker also ignores the policy for anything stopped by hand, including `docker stop` and `docker kill`; and a PostgreSQL immediate shutdown exits 0, which `on-failure` does not act on. PostgreSQL stops with `SIGINT` (fast shutdown) so `make down` checkpoints cleanly; after a real crash, WAL replay at startup is the only automatic repair, and uploads have no equivalent. See `scripts/README.md` for the details.

| Address | Purpose |
|---|---|
| https://localhost | Development frontend shell; known broken/mock flows |
| https://localhost/docs | Swagger UI for the real API |
| https://localhost/openapi.json | Generated API specification |
| https://localhost/health | Backend/database health JSON; not a complete status/backup system |

The frontend is served under a nonce-based Content-Security-Policy: nginx mints a unique nonce per request and Vite stamps it on the tags it generates, via `html.cspNonce` in `frontend/vite.config.js`. `script-src` never allows `'unsafe-inline'`, and the strict nonce-free policy stays on `/api/`, `/health`, `/docs` and `/openapi.json`. If a script is ever blocked, add the nonce to the tag rather than relaxing `script-src` — a blocked inline script renders a blank page while nginx and Vite both log a clean 200. See `scripts/README.md`.

`make smoke` makes read-only HTTPS requests for health, the frontend root and representative OpenAPI paths. It does **not** create users, authenticate, test browser JavaScript, validate every route or prove feature completion. Its TLS client uses the generated certificate explicitly with `--cacert`, rather than disabling verification. It also verifies the frontend CSP nonce pipeline end to end, but curl enforces no policy and runs no script, so only a browser can prove the page renders.

### Commands and tests

| Command | Behavior |
|---|---|
| `make setup` | Create or migrate local env/secret files and create missing TLS files |
| `make check` | Validate local prerequisites/configuration/TLS/Compose |
| `make up` | Check, build and start default development services |
| `make down` | Stop/remove Compose services while preserving all data under `data/` |
| `make clean` | Alias of `make down`; preserve data and images |
| `make fclean` | After typed confirmation, remove project containers, local app images and all project volumes, and erase `data/` |
| `make re` | Check configuration, then confirmed `fclean`, rebuild and start an empty stack |
| `make logs` | Follow service logs; avoid sharing secrets from application output |
| `make ps` | Show Compose services including the test profile |
| `make smoke` | Check read-only HTTPS health/frontend/OpenAPI; no account mutations |
| `make test` | Build backend test image and run pytest against isolated test storage |
| `make test TESTS='tests/test_health.py'` | Pass selected pytest arguments through the wrapper |
| `make reset-db` | Explicitly confirmed deletion of development DB only, including `data/postgres` |

`make fclean` and `make re` permanently delete the development database,
uploaded files and frontend dependency volume, emptying `data/postgres` and
`data/uploads` on the host. They verify Compose project labels, verify that each
host directory is the one Compose resolved and lies inside `data/`, and require
typing the target name before running. They preserve source files, `.env`,
secret files, TLS certificates and pulled PostgreSQL/Nginx images.

### Google OAuth and API keys

Google sign-in starts from `/login`. The provider callback stores no bearer token
in a URL: it creates a short-lived Secure/HttpOnly handoff, redirects to the
frontend, and the frontend exchanges that handoff once with
`POST /api/auth/oauth/google/exchange`.

Authenticated users can issue and manage public-API credentials through
`POST/GET /api/api-keys`, `DELETE /api/api-keys/{id}` and
`POST /api/api-keys/{id}/rotate`. Issue and rotate responses show the raw key
once. Lists expose metadata only; the database stores only SHA-256 hashes.
Revocation and rotation invalidate the old key immediately. Public API calls use
`X-API-Key`; browser clients are not supported, so that header is intentionally
excluded from CORS.

The test profile uses PostgreSQL 17 on an isolated internal network with tmpfs storage, no published DB port and fixed **test-only** credentials. `DATABASE_URL` and `TEST_DATABASE_URL` both target `taskmanager_test` on `test-db`. Fixtures guard the database name/host/credentials before destructive operations, run the initial Alembic migration and truncate only the dedicated test data. Development data/uploads are not mounted into tests. Do not override test URLs to the development DB.

Tests rebuild the backend image to include edits; `TESTS` is parsed as arguments, not shell code. The wrapper removes the test DB container after the run, including pytest failure. Do not run concurrent test invocations within the same Compose project. A uses real-auth `client`; B uses explicit `member_client`; C SQLite fixtures use shared authentication dependencies. SQLite tests do not replace PostgreSQL integration tests.

## Database Schema

All entity IDs are UUIDs. See [the detailed schema](docs/00-contrat-commun.md) and [`db_install`](backend/alembic/versions/db_install.py).

| Table | Key fields and relationships |
|---|---|
| `users` | Unique email/username, nullable display name, password hash or OAuth identity, global role/status, avatar URL, timestamps |
| `projects` | Name/description, `owner_id -> users`, creation time |
| `project_members` | Unique project/user pair, owner/editor/viewer role; canonical project authorization |
| `tasks` | `project_id`, title/description/status, nullable assignee and due date, timestamps |
| `attachments` | Task/uploader references, file name/URL, timestamp; restrictive parent deletion |
| `api_keys` | User reference, unique SHA-256 key hash, timestamp |
| `oauth_handoffs` | One-time hashed OAuth browser handoff with user and expiry |
| `notifications` | Recipient, type/content/read flag, nullable task/project context, timestamp |

Project/member/task relations support cascades; deleted assignees and notification context can become null. Attachments intentionally restrict referenced-parent deletion. Project owner references and owner memberships must remain consistent. Five PostgreSQL enums encode global role, account status, project role, task status and current notification type.
