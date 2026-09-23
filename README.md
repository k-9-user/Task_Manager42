# Task Manager 42

*This project has been created as part of the 42 curriculum by Eraad, khderdou, ksupinsk, nratajcz.*

Task Manager 42 is a collaborative project/task-management web application built
with React, FastAPI and PostgreSQL. Users create projects, invite members with
owner/editor/viewer permissions, create and assign tasks with deadlines, track
progress on a Kanban-style board, attach files and banners to tasks, message
their team per project, search across projects and tasks, and manage their
personal data (export/deletion) in line with GDPR. Administrators can manage
every account's role and status. A public, API-key-authenticated endpoint lets
external tools create and manage tasks without the web UI.

## Team

| Login | Role(s) | Main area of ownership |
|---|---|---|
| **Eraad** | Tech Lead, Backend (Auth & Security) | Docker/Compose setup, database bootstrap, JWT auth, password hashing (Argon2), Google OAuth, admin permissions & roles, HTTPS/nginx reverse proxy, health check, rate limiting |
| **khderdou** | Project Manager, Backend (Projects & Tasks) | Projects/tasks/members CRUD, role-based permissions, GDPR export & account deletion, notifications backend, project message wall, sprint coordination (backlog, syncs) |
| **ksupinsk** | Backend (Public API & Data) | Public API with API-key auth & rate limiting, advanced search (filters/sort/pagination), file attachments & task banners, CSV/JSON export & import |
| **nratajcz** | Frontend | React app structure & routing, all pages/components, i18n (FR/EN/ES), responsive layout, legal pages, design pass |

## Project management

- **Branching**: one long-lived branch per person (previously labelled `A`/`B`/`C`/`D`
  during planning, now mapped 1:1 to the logins above), merged regularly into a shared
  integration branch, with a final branch cut for submission.
- **Commit convention**: `[SCOPE] description` (e.g. `[auth] add JWT token generation`).
- **Coordination**: the team agreed the API routes, database schema and environment
  variables up front, so the four areas above (auth, projects/tasks, public API/data,
  frontend) could be built in parallel against a stable interface. Each area's
  four-week task breakdown made explicit "who is waiting on whom" (e.g. the frontend
  could not start wiring a page until the corresponding backend route was confirmed
  testable).
- **Backlog & syncs**: GitHub Issues for the backlog; two short weekly syncs (in
  person / video call) to unblock dependencies between areas.
- **Module scope**: the module list below was fixed at the start and tracked against
  a 14-point minimum throughout, rather than chased opportunistically.

## Why this project

A task manager was chosen over a more novelty-driven idea (e.g. a game) because it
needs genuine multi-user collaboration (a hard requirement), maps naturally onto a
relational schema (`users` → `projects` → `tasks` → `attachments`/`comments`), and
cleanly supports a varied, coherent set of modules (permissions, public API, search,
file upload) without a heavy technical dependency such as real-time synchronization.

## Technologies used

| Choice | Why |
|---|---|
| **React** (Vite) | Most widely used frontend framework; large ecosystem; easy to structure into reusable components |
| **Tailwind CSS** | Utility-first styling solution used across the frontend (sidebar, auth pages, project list, etc.) instead of hand-rolled CSS only |
| **FastAPI** | Lightweight, high-performance Python backend framework; generates OpenAPI/Swagger docs automatically, which the public-API module relies on |
| **PostgreSQL** | Robust relational database; well suited to the users↔projects↔tasks relational model |
| **SQLAlchemy (ORM)** | Avoids hand-written SQL, parameterizes every query against injection, speeds up iteration |
| **Alembic** | Versioned, reviewable database migrations |
| **Docker Compose** | Identical local environment for everyone on the team; the whole stack starts with one command |
| **JWT** (PyJWT) | Stateless authentication that also underpins the public API-key story |
| **Argon2** (pwdlib/argon2-cffi) | Modern, memory-hard password hashing (not reversible encryption) |
| **nginx** | Single HTTPS entry point, reverse proxy, per-request CSP nonce, rate limiting on auth routes |
| **i18next** | Full FR/EN/ES translation of all visible UI text, including legal pages |

## Database schema

All entity IDs are UUIDs. See [`db_install`](backend/alembic/versions/db_install.py)
plus the migrations that followed it for the exact DDL.

| Table | Key fields and relationships |
|---|---|
| `users` | Unique email/username, nullable display name, password hash or OAuth identity, global role/status, avatar URL, timestamps |
| `projects` | Name/description, `owner_id -> users`, creation time |
| `project_members` | Unique project/user pair, owner/editor/viewer role; canonical project authorization |
| `tasks` | `project_id`, title/description/status, nullable assignee and due date, optional banner image, timestamps |
| `attachments` | Task/uploader references, file name/URL, timestamp; restrictive parent deletion |
| `comments` | Per-task discussion thread: task/author references, content, timestamps |
| `project_messages` | Per-project team message wall: project/author references, content, timestamp |
| `api_keys` | User reference, unique SHA-256 key hash, timestamp |
| `oauth_handoffs` | One-time hashed OAuth browser handoff with user and expiry |
| `notifications` | Recipient, type/content/read flag, nullable task/project context, timestamp |

Project/member/task relations support cascades; deleted assignees and notification
context can become null. Attachments intentionally restrict referenced-parent
deletion. Project owner references and owner memberships must remain consistent.
Five PostgreSQL enums encode global role, account status, project role, task
status and current notification type.

## Features and who built them

| Feature | Owner(s) |
|---|---|
| Docker Compose stack, TLS/nginx, Make wrapper (setup/check/up/down/backup/...) | Eraad |
| Email/password auth, JWT, Argon2 hashing, Google OAuth | Eraad |
| Admin: list/rename/ban/unban/role-change/delete any user | Eraad (backend) + nratajcz (frontend) |
| Health check endpoint + user-facing status page + backups | Eraad |
| Projects & tasks CRUD, members with owner/editor/viewer roles | khderdou |
| Project message wall (per-project team chat) | khderdou (backend) + nratajcz (frontend) |
| GDPR data export and confirmed account deletion (Profile → My data, confirmation emails) | khderdou |
| Notifications (task assignment/status change) | khderdou |
| Public API with API-key auth and rate limiting | ksupinsk |
| Advanced search (tasks and projects: text, filters, sort, pagination) | ksupinsk (backend) + nratajcz (frontend) |
| File attachments and task banners | ksupinsk (backend) + nratajcz (frontend) |
| CSV/JSON export and import | ksupinsk |
| React app, routing, all pages, Tailwind design pass | nratajcz |
| FR/EN/ES translations (including legal pages) | nratajcz |
| Privacy Policy / Terms of Service | nratajcz |

## Modules (14 points required)

| Category | Module | Type | Pts | Owner |
|---|---|---|---|---|
| Web | Framework (frontend + backend) | Major | 2 | nratajcz + Eraad |
| Web | ORM | Minor | 1 | Eraad |
| Web | Public API | Major | 2 | ksupinsk |
| Web | Advanced search (filters + sort + pagination) | Minor | 1 | ksupinsk |
| Web | File upload | Minor | 1 | ksupinsk |
| User Management | Advanced permissions (owner/editor/viewer + admin) | Major | 2 | Eraad |
| User Management | OAuth (Google) | Minor | 1 | Eraad |
| Accessibility | Multi-language support (FR/EN/ES, all visible text) | Minor | 1 | nratajcz |
| Data & Analytics | Export/import (CSV/JSON) | Minor | 1 | ksupinsk |
| Data & Analytics | GDPR (export + confirmed deletion + confirmation emails) | Minor | 1 | khderdou |
| DevOps | Health check + status page + backups + disaster recovery | Minor | 1 | Eraad |
| **Total** | | | **14** | |

Notes on two modules, for transparency at defense time:

- **OAuth**: CSRF-safe Authlib flow, token-free browser handoff, cancellation/error
  handling (see `backend/app/routers/auth.py` and `backend/app/auth/oauth.py`),
  verified end to end with a real Google Cloud OAuth Client ID/Secret. Those
  credentials are never committed — `.env`/`secrets/oauth_google_client_secret`
  ship blank; each environment configures its own (see `make setup`). Without
  them, the button shows a clean `503 Google OAuth unavailable` instead of a
  broken redirect.
- **Health check / status / backups / DR**: `GET /health` checks the database
  connection; `/status` in the frontend polls it and shows component state; `make
  backup` dumps the database (`pg_dump`, timestamped, last 7 kept, see
  `scripts/build/commands.py`) to `data/backups/`. Disaster recovery is a manual
  restore of the most recent dump (`docker compose exec -T db psql -U <user> <db> <
  data/backups/<file>.sql` after `make up`) — there is no automated restore drill.

No bonus modules are claimed.

## Individual contributions

- **Eraad** — Project bootstrap (Compose, Dockerfiles, Make wrapper, TLS); the full
  auth stack (register/login, JWT issuance, Argon2 hashing, Google OAuth); admin
  user management endpoints and the last-administrator/last-active-administrator
  invariants; nginx reverse proxy, CSP, rate limiting; `/health` and its
  status/backup follow-through.
- **khderdou** — Projects, tasks and project-members endpoints with role
  enforcement; GDPR export/deletion; notifications backend; project message wall;
  sprint planning and cross-team coordination (backlog, syncs, shared API contract).
- **ksupinsk** — Public API (`/api/v1/public/*`) with API-key issuance/rotation and
  rate limiting; advanced search with allow-listed sort fields; task attachments
  and banners; CSV/JSON export/import.
- **nratajcz** — The React application end to end: routing, every page and shared
  component, the Tailwind-based visual design, FR/EN/ES translations, responsive
  layout, and the legal pages.

## Resources

- [FastAPI documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 documentation](https://docs.sqlalchemy.org/en/20/)
- [Alembic documentation](https://alembic.sqlalchemy.org/)
- [React documentation](https://react.dev/)
- [Tailwind CSS documentation](https://tailwindcss.com/docs)
- [i18next / react-i18next documentation](https://www.i18next.com/)
- [JWT.io — Introduction to JSON Web Tokens](https://jwt.io/introduction)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Docker Compose documentation](https://docs.docker.com/compose/)

**AI usage**: the team used an AI assistant as a learning aid while
working with technologies and concepts that were new to some or all members —
FastAPI/SQLAlchemy/Alembic on the backend, React/Tailwind on the frontend, and
Python's testing ecosystem (pytest) for writing and understanding the test suite.
It was used to explain unfamiliar concepts, get oriented in a new language/framework,
and help write and reason about tests, always under team review — every change was
read, run and understood by the team before being kept.

---

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

**Use localhost only.** The canonical address is **https://localhost**. Only nginx publishes application ports, on `127.0.0.1:80` and `127.0.0.1:443`; its unprivileged container listens internally on 8080/8443. The Mailpit mail catcher publishes its inbox on `127.0.0.1:8025` so GDPR confirmation emails can be read locally; nothing leaves the machine. HTTP redirects to HTTPS while preserving the request URI. Do not publish direct database/backend/frontend ports or turn this development stack into an Internet service. A one-shot service creates the configured first administrator after migrations; local and Google registrations always create ordinary users. Read the local bootstrap password from `secrets/bootstrap_admin_password` without sharing or committing it.

Existing databases are accepted only when their first account exactly matches the configured active administrator and bootstrap password. Otherwise startup fails without modifying users. For disposable incompatible development data, review `BOOTSTRAP_ADMIN_*`, obtain explicit approval, run `make reset-db`, then start the stack again. Reset is never automatic. Because the database now persists on the host, this matters beyond first boot: editing `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_USERNAME` or `secrets/bootstrap_admin_password` after the first start blocks every later `make up` until the matching credentials are restored or the database is explicitly reset.

### Persistent data

The database cluster and uploaded attachments live on the host under `data/` at the repository root: `data/postgres` for PostgreSQL and `data/uploads` for attachments. Both are Compose named volumes bound to those directories, which the Make wrapper creates (mode 0700) before every Compose call — Compose requires an absolute, pre-existing bind path and never creates one. `data/backups` holds `make backup` dumps. `data/` is git-ignored; never commit it. The data survives `make down`, a container crash and a Docker daemon restart, and `make up` picks it straight back up. Only `make reset-db`, `make fclean` and `make re` erase database/upload data, each behind a typed confirmation that lists the directories. `DATA_DIR` is fixed to `<repo>/data` by the wrapper and is intentionally not an `.env` key; a host `DATA_DIR` cannot redirect the stack, and a bare `docker compose` command fails rather than binding an unintended path. The frontend dependency volume stays inside Docker: it is rebuilt at image build and does not belong on the host.

`db`, `backend`, `frontend` and `nginx` restart automatically on a non-zero exit, capped at five attempts. The coverage is narrower than it sounds: a restart policy reacts to process exit only, so a hung or `unhealthy` container whose main process is still alive is not restarted; Docker also ignores the policy for anything stopped by hand, including `docker stop` and `docker kill`; and a PostgreSQL immediate shutdown exits 0, which `on-failure` does not act on. PostgreSQL stops with `SIGINT` (fast shutdown) so `make down` checkpoints cleanly; after a real crash, WAL replay at startup is the only automatic repair, and uploads have no equivalent. See `scripts/README.md` for the details.

| Address | Purpose |
|---|---|
| https://localhost | Frontend application |
| https://localhost/status | User-facing health/status page |
| https://localhost/docs | Swagger UI for the real API |
| https://localhost/openapi.json | Generated API specification |
| https://localhost/health | Backend/database health JSON |
| http://localhost:8025 | Mailpit inbox (GDPR confirmation emails) |

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
| `make backup` | Dump the development database to `data/backups/` (timestamped, last 7 kept) |
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
`POST /api/auth/oauth/google/exchange`. This requires a real Google OAuth Client
ID/Secret to be configured (see the Modules section above); without one, the
backend returns a clean `503` instead of attempting the redirect.

Authenticated users can issue and manage public-API credentials through
`POST/GET /api/api-keys`, `DELETE /api/api-keys/{id}` and
`POST /api/api-keys/{id}/rotate`. Issue and rotate responses show the raw key
once. Lists expose metadata only; the database stores only SHA-256 hashes.
Revocation and rotation invalidate the old key immediately. Public API calls use
`X-API-Key`; browser clients are not supported, so that header is intentionally
excluded from CORS.

The test profile uses PostgreSQL 17 on an isolated internal network with tmpfs storage, no published DB port and fixed **test-only** credentials. `DATABASE_URL` and `TEST_DATABASE_URL` both target `taskmanager_test` on `test-db`. Fixtures guard the database name/host/credentials before destructive operations, run the initial Alembic migration and truncate only the dedicated test data. Development data/uploads are not mounted into tests. Do not override test URLs to the development DB.

Tests rebuild the backend image to include edits; `TESTS` is parsed as arguments, not shell code. The wrapper removes the test DB container after the run, including pytest failure. Do not run concurrent test invocations within the same Compose project. SQLite tests do not replace PostgreSQL integration tests.
