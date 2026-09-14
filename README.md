# Task Manager 42

## Description

Task Manager 42 is a collaborative project/task-management application built with React, FastAPI and PostgreSQL. Its intended workflow is to create projects, add members with owner/editor/viewer permissions, assign tasks and deadlines, track progress, search tasks, manage attachments and export personal or project data.


### Prerequisites

- Docker with Compose v2 supporting `up --wait`, and a running Docker daemon.
- Make and Python 3 (the local wrapper uses only the standard library).
- OpenSSL supporting `req -addext` and `x509 -ext`, plus curl.
- Latest stable Google Chrome for eventual mandatory browser verification.
- Free local ports 8080 and 8443; network access for container images/dependency downloads.

Run the following commands from the repository root. Application runtimes are containerized: Python 3.12, Node 24 and PostgreSQL 17. A host Node/Python backend environment is not needed for the container workflow. The root `package.json` is not the frontend application; its package lives in `frontend/`.

### Development quickstart

```sh
make setup
make check
make up
make smoke
```

`make setup` creates `.env` only if absent, generating independent JWT/OAuth secrets and a random database password. It creates a local self-signed TLS pair only if absent. Existing configuration and certificates are preserved, not overwritten. Review `.env.example` and your local `.env`; never commit credentials or private keys. Setup does not repair stale existing secrets or change credentials inside an existing database volume.

The wrapper accepts plain `KEY=value` entries: no quotes, interpolation, inline comments, duplicate keys or extra keys absent from `.env.example`. It uses that checked file instead of conflicting host environment/Compose overrides. Keep `DATABASE_URL` consistent with `POSTGRES_*`; JWT, OAuth-session and database secrets must be independent, non-placeholder URL-safe values of at least 32 characters.

`make check` validates local tools, daemon, configuration, secrets, local URLs, certificate validity/SAN/key matching and Compose configuration. `make up` performs checks, builds and starts the development stack with the frontend enabled by default. The backend waits for database health and migration completion; nginx waits for backend and frontend health.

**Use localhost only.** The canonical address remains **https://localhost:8443**. Only nginx publishes ports, on `127.0.0.1:8080` and `127.0.0.1:8443`; HTTP redirects to HTTPS. Do not publish direct database/backend/frontend ports or turn this development stack into an Internet service. The first registration in an empty database becomes administrator, so bootstrap must remain local and under your control.

| Address | Purpose |
|---|---|
| https://localhost:8443 | Development frontend shell; known broken/mock flows |
| https://localhost:8443/docs | Swagger UI for the real API |
| https://localhost:8443/openapi.json | Generated API specification |
| https://localhost:8443/health | Backend/database health JSON; not a complete status/backup system |

`make smoke` makes read-only HTTPS requests for health, the frontend root and representative OpenAPI paths. It does **not** create users, authenticate, test browser JavaScript, validate every route or prove feature completion. Its TLS client uses the generated certificate explicitly with `--cacert`, rather than disabling verification.

### Commands and tests

| Command | Behavior |
|---|---|
| `make setup` | Create missing local env/certificate files; preserve existing files |
| `make check` | Validate local prerequisites/configuration/TLS/Compose |
| `make up` | Check, build and start default development services |
| `make down` | Stop/remove Compose services while preserving named volumes |
| `make logs` | Follow service logs; avoid sharing secrets from application output |
| `make ps` | Show Compose services including the test profile |
| `make smoke` | Check read-only HTTPS health/frontend/OpenAPI; no account mutations |
| `make test` | Build backend test image and run pytest against isolated test storage |
| `make test TESTS='tests/test_health.py'` | Pass selected pytest arguments through the wrapper |
| `make reset-db` | Explicitly confirmed deletion of development DB only |

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
| `api_keys` | User reference, unique stored key representation, timestamp |
| `notifications` | Recipient, type/content/read flag, nullable task/project context, timestamp |

Project/member/task relations support cascades; deleted assignees and notification context can become null. Attachments intentionally restrict referenced-parent deletion. Project owner references and owner memberships must remain consistent. Five PostgreSQL enums encode global role, account status, project role, task status and current notification type.
