# Task Manager 42

*Created as part of the 42 curriculum by Eraad, khderdou, ksupinsk, and nratajcz.*

## Overview

Task Manager 42 is a collaborative project and task-management application. Users
create projects, invite members with owner/editor/viewer permissions, assign and
track tasks, attach private files, exchange project messages, search their visible
work, and export or import data. Administrators can manage accounts, while external
clients can use a documented API protected by per-user API keys.

The application is a localhost development stack built around React, FastAPI,
PostgreSQL, and nginx. Docker Compose orchestrates the services, but the Make wrapper
is the supported entry point because it supplies validated configuration such as the
absolute `DATA_DIR`.

## Features

- Email/username login, Argon2 password hashing, JWT sessions, and optional Google
  OAuth 2.0/OIDC.
- Project and task CRUD with owner, editor, and viewer authorization.
- Administrator account listing, editing, role changes, bans, unbans, and deletion.
- Project messages, task comments, notifications, and persistent gamification.
- API-key-protected public task/project API with per-key rate limiting.
- Task and project search with text filters, status/project filters, allow-listed
  sorting, deterministic tie-breaking, totals, and pagination.
- Private task attachments and banners with client/server validation, upload
  progress, authenticated preview/download, and deletion.
- Deterministic JSON/CSV export and validated JSON/CSV bulk import.
- GDPR data export and confirmed account deletion with locally captured email
  notifications.
- Database-aware health checks, a status page, scheduled backups, and confirmed
  database/upload restoration.

## Technology Choices

| Technology | Role and rationale |
|---|---|
| React + Vite | Component-based frontend with fast local development and a clear service/UI boundary |
| Tailwind CSS + component CSS | Responsive styling with reusable layout primitives and focused component rules |
| FastAPI + Pydantic | Typed request validation, dependency-based authorization, and generated OpenAPI documentation |
| PostgreSQL 17 | Relational integrity for users, memberships, projects, tasks, and dependent records |
| SQLAlchemy + Alembic | ORM queries, explicit relationships/constraints, and versioned schema setup |
| nginx | One TLS entry point, reverse proxying, HTTP redirect, CSP, and security headers |
| Docker Compose | Reproducible application, database, backup, test, and mail-catcher services |
| Mailpit | Safe local capture of GDPR operation emails without external delivery |

## Database Model

All primary and relationship identifiers are UUIDs. The current authoritative DDL is
`backend/alembic/versions/initial_schema.py`.

| Table | Purpose and important relationships |
|---|---|
| `users` | Unique email/username, Argon2 hash or Google identity, global role/status, profile fields |
| `projects` | Project metadata and canonical owner reference |
| `project_members` | Unique project/user membership with owner/editor/viewer role |
| `tasks` | Project task, optional assignee/due date/banner, status, timestamps |
| `attachments` | Task attachment metadata and nullable uploader reference; bytes remain on private storage |
| `comments` | Authored task discussion |
| `project_messages` | Authored project message wall |
| `notifications` | Recipient, notification type/content/read state, optional task/project context |
| `api_keys` | User relationship and unique key hash; never the raw API key |
| `user_activities` | Deduplicated actions used by gamification tracks |
| `user_achievements` | Persistent unlocked achievements and awarded XP |
| `user_badges` | Persistent level badge awards |

Foreign keys cascade or null dependent references according to ownership semantics.
Unique constraints protect membership, API-key, identity, activity, achievement, and
badge invariants.

## Feature Ownership

| Area | Contributor(s) |
|---|---|
| Compose, Make workflow, TLS/nginx, auth, OAuth, admin, health/backups | Eraad |
| Projects, tasks, memberships, GDPR, notifications, project messages | khderdou |
| API keys/public API, rate limiting, search, attachments, import/export | ksupinsk |
| React pages/components, routing, UI design, locale catalogs, legal pages | nratajcz |
| Admin and collaborative feature UI integration | Backend owner(s) + nratajcz |

Repository history shows feature work integrated into `Final` through reviewed topic
branches and merge commits. The team coordinated around shared API routes, database
relationships, environment variables, and frontend response envelopes so backend and
frontend work could converge without separate contracts.

## 42 Modules

The authoritative scoring source used for this table is the official subject PDF
stored in this repository's history at commit `50d4dd0`, path
`docs/transcendence.pdf` (PDF creation date: 2026-04-08). It requires **14 points**:
a major module is worth 2 points and a minor module is worth 1 point.

Only complete modules are included in the confirmed total.

| Category | Module | Value | Implemented feature | Status |
|---|---|---:|---|---|
| Web | Framework for frontend and backend | 2 | React/Vite frontend and FastAPI backend | IMPLEMENTED |
| Web | Public API | 2 | Five documented API-key routes, rate limiting, membership authorization | IMPLEMENTED |
| User Management | Advanced permissions | 2 | Admin user CRUD/roles/status plus role-dependent views and actions | IMPLEMENTED |
| User Management | Organization system | 2 | Project CRUD, membership add/remove, owner/editor/viewer actions | IMPLEMENTED |
| Web | ORM | 1 | SQLAlchemy models and PostgreSQL persistence | IMPLEMENTED |
| Web | Advanced search | 1 | Filters, safe sorting, pagination, totals, task and project search | IMPLEMENTED |
| Web | File upload and management | 1 | Multiple types, size/type checks, progress, private access, preview, deletion | IMPLEMENTED |
| User Management | Remote authentication | 1 | Google OAuth 2.0/OIDC flow with a one-time browser handoff | IMPLEMENTED |
| Data and Analytics | Data export and import | 1 | JSON/CSV export and validated bulk import | IMPLEMENTED |
| Data and Analytics | GDPR compliance | 1 | Readable export, confirmed deletion, operation emails | IMPLEMENTED |
| DevOps | Health/status/backups/disaster recovery | 1 | Health/status routes, scheduled database+upload backups, confirmed restore | IMPLEMENTED |
| Gaming and user experience | Gamification | 1 | Persistent achievements, badges, XP/levels, rules, progress, and unlock feedback | IMPLEMENTED |
| Accessibility and Internationalization | Multiple languages | 1 | FR/EN/ES catalogs and switcher; notification bodies remain English-only | PARTIALLY IMPLEMENTED |
| Web | Complete notification system | 1 | Assignment, task-status, and project-invite notifications only | PARTIALLY IMPLEMENTED |

Confirmed arithmetic: **4 major modules × 2 + 8 minor modules × 1 = 16 points**.

**CONFIRMED POINT REQUIREMENT SATISFIED: 16 / 14 points.**

The two partial modules are not included in that total. Google OAuth needs local
provider credentials for a live demonstration; credentials are intentionally not
committed.

## Architecture

```text
Browser / API client
        |
        v
nginx on https://localhost
  |-- /              -> React/Vite frontend
  |-- /api, /health  -> FastAPI
  |                      |-- PostgreSQL
  |                      `-- private upload directory
  `-- /docs, /openapi.json

Mailpit <- GDPR operation email
Backup service -> database dump + upload archive under data/backups
```

- **Frontend:** React 19, Vite, Tailwind CSS, and i18next.
- **Gateway:** unprivileged nginx terminates TLS, redirects HTTP, applies security
  headers/CSP, and proxies frontend/backend traffic.
- **Backend:** FastAPI, Pydantic, SQLAlchemy, Alembic, JWT, and Authlib.
- **Database:** PostgreSQL 17. The current schema is defined by
  `backend/alembic/versions/initial_schema.py`.
- **Storage:** PostgreSQL and uploads are bind-backed under the ignored `data/`
  directory. Upload bytes are never served by nginx or an unrestricted FastAPI
  static mount.

## Security

- nginx exposes only `127.0.0.1:80` and `127.0.0.1:443`; HTTP redirects to HTTPS.
- Local TLS certificates are generated by `make setup` and validated by `make check`.
- Passwords use salted Argon2 hashes. Protected browser routes use bearer JWTs, and
  banned users are rejected when credentials are resolved.
- API keys have a `tm42_` prefix, are returned only when issued, and are stored as
  SHA-256 hashes. Lists expose metadata rather than raw keys.
- Project membership is checked before reads, counts, pagination, downloads, and
  writes. Outsiders generally receive a non-disclosing 404.
- Attachment storage names are generated UUIDs. Downloads re-resolve the current
  task/project membership and reject traversal, absolute-path, nested-path, and
  symlink escapes.
- CSV export uses the standard CSV writer and prefixes cells whose first meaningful
  character is `=`, `+`, `-`, or `@`. Database values and JSON exports are unchanged.
- Runtime secrets live in ignored regular files under `secrets/`; `.env`, TLS private
  keys, persistent data, and uploads are ignored. `make check` validates file types,
  permissions, placeholders, secret independence, and configuration consistency.
- The frontend uses a nonce-based CSP. `/docs` has a separate policy for Swagger UI,
  while API and OpenAPI responses retain the strict default policy.

## Requirements

- Docker Engine with Compose v2 and a running daemon.
- GNU Make and Python 3 (the host-side wrapper uses the standard library only).
- OpenSSL, curl, and free local ports 80, 443, and 8025.
- Network access on the first build for container images and dependencies.
- A current browser for final interactive verification.

Application runtimes are containerized (Python 3.12, Node 24, PostgreSQL 17). A host
backend virtual environment or host `npm install` is not required.

## Setup

Run these commands from the repository root:

```sh
make setup
make check
make up
make smoke
```

`make setup` creates or migrates the ignored `.env`, independent secret files, local
TLS certificate/key, and required data directories. Existing valid secrets and TLS
material are preserved. It is safe to run again when new non-secret configuration
keys are added.

`make check` validates tools, Docker, `.env`, secret files, TLS, local URLs, and the
resolved Compose configuration without printing secret values. `make up` repeats the
checks, builds the application images, applies migrations, validates/bootstrap the
first administrator, and waits for healthy services.

Do **not** replace this workflow with raw `docker compose up --build`. The Compose file
requires `DATA_DIR`, which is deliberately fixed and supplied by `scripts/make.py`.

Google OAuth is disabled when both local Google values are empty. To enable it, set a
local Google client ID and the HTTPS callback URL in `.env`, place the matching client
secret in `secrets/oauth_google_client_secret`, register
`https://localhost/api/auth/oauth/google/callback` with the provider, and rerun
`make check`. Never commit provider credentials.

## Usage

| Address | Purpose |
|---|---|
| `https://localhost` | React application |
| `https://localhost/status` | Component and backup status |
| `https://localhost/docs` | Swagger UI |
| `https://localhost/openapi.json` | Generated OpenAPI 3.1 specification |
| `https://localhost/health` | Backend/database health |
| `http://localhost:8025` | Mailpit inbox for locally captured emails |

The generated certificate is local, so the browser may require an explicit trust
decision. Mailpit captures GDPR emails; the development stack does not deliver them
to real recipients.

Useful lifecycle commands:

| Command | Effect |
|---|---|
| `make up` | Check, build, migrate, and start the stack |
| `make down` | Stop/remove containers while preserving `data/` |
| `make ps` | Show project services |
| `make logs` | Follow service logs |
| `make smoke` | Read-only TLS, health, frontend, CSP, and OpenAPI smoke checks |
| `make backup` | Create a database and upload backup immediately |
| `make restore` | Confirm and restore the newest complete backup |
| `make restore BACKUP=<name>` | Confirm and restore a selected complete backup |
| `make reset-db` | Confirm and delete only the development database |
| `make fclean` | Confirm and remove project containers/images/volumes and all `data/` |

Scheduled backups run every 60 minutes and retain 24 complete backups by default.
Each backup contains a PostgreSQL dump and a flat upload archive. Restore validates
both, loads a staging database, and only then switches the live database. Destructive
commands require typed confirmation.

## API Documentation

FastAPI generates the OpenAPI document from the composed application. The generated
specification is the source of truth for request and response schemas:

- `GET /openapi.json` returns the specification.
- `GET /docs` renders Swagger UI through nginx's route-specific CSP.

The public API uses `X-API-Key` and returns the common success envelope
`{"success": true, "data": ...}`. Error responses use
`{"success": false, "error": "..."}`.

## Testing

Backend tests use an isolated PostgreSQL 17 service with tmpfs storage and no
development data or upload mounts:

```sh
make test
make test TESTS='tests/test_public_api.py tests/test_search.py tests/test_attachments.py tests/test_export_import.py'
python3 scripts/test.py -v
git diff --check
```

The frontend image can be checked without installing Node on the host:

```sh
docker build -t task-manager-front:latest frontend
docker run --rm task-manager-front:latest npm run lint -- src
docker run --rm task-manager-front:latest npm run build
```

The backend image can be compiled without importing host dependencies:

```sh
docker build -t task-manager-back:latest backend
docker run --rm --entrypoint python task-manager-back:latest -m compileall -q app tests
```

Run `make up` before `make smoke`. The smoke test is intentionally read-only and does
not replace authenticated API tests or a real browser walkthrough.

## Project Structure

```text
backend/
  app/                 FastAPI app, routers, auth, models, schemas, services
  alembic/             current database schema migration
  tests/               PostgreSQL integration tests
frontend/
  public/locales/      English, French, and Spanish catalogs
  src/                 React pages, components, services, and styles
nginx/                 TLS reverse-proxy and CSP configuration
backup/                scheduled backup and safe restore implementation
scripts/               Make command implementation and host-side unit tests
secrets/README.md      secret-file contract (never real values)
docker-compose.yml     service definitions; invoked through Make
Makefile               supported operator entry point
```

## API / Person C Features

### API keys and public API

Authenticated users can issue, list, and revoke keys:

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/api-keys` | Issue a key; raw value shown once |
| `GET` | `/api/api-keys` | List key IDs and creation times |
| `DELETE` | `/api/api-keys/{key_id}` | Revoke a key immediately |

Public calls send `X-API-Key`:

| Method | Route | Access |
|---|---|---|
| `GET` | `/api/v1/public/tasks` | Any current project member |
| `POST` | `/api/v1/public/tasks` | Project owner or editor |
| `PUT` | `/api/v1/public/tasks/{task_id}` | Project owner or editor |
| `DELETE` | `/api/v1/public/tasks/{task_id}` | Project owner |
| `GET` | `/api/v1/public/projects` | Any current project member |

Task and project lists use `created_at DESC, id DESC`. The rate limiter is a
60-request/60-second fixed window per API key and returns 429 with `Retry-After`.

### Advanced search

- `GET /api/search/tasks` searches visible task titles/descriptions and supports
  status/project filters, allow-listed sort fields/direction, and pagination.
- `GET /api/search/projects` searches visible project names with safe sorting and
  pagination.
- Both default to page 1 and limit 20, cap limit at 100, compute `total` before
  pagination, escape SQL wildcard characters, and apply an `id DESC` tie-breaker.

### Attachments

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/tasks/{task_id}/attachments` | Owner/editor upload |
| `GET` | `/api/tasks/{task_id}/attachments` | Member metadata listing |
| `GET` | `/api/attachments/{attachment_id}` | Authenticated member preview/download |
| `DELETE` | `/api/attachments/{attachment_id}` | Owner/editor deletion |

Listings expose only `id`, safe filename, content type, and creation time. The
frontend uses an authenticated blob request for preview/download, so protected files
remain usable without a public upload URL. It reloads metadata after upload and
removes deleted items immediately.

### Import and export

- `GET /api/export?format=json|csv` exports all visible projects or one selected
  project in deterministic order.
- `POST /api/import` accepts a JSON or CSV file, validates every record, and commits
  the bulk import once validation succeeds.
- Strict task schemas reject unknown fields and invalid title, description, status,
  date, or UUID values. Nested JSON task project IDs must match their parent project.
- Existing writable projects accept imports; a source project that is not writable
  is recreated as a new project owned by the importer when the file supplies its
  name.

## Known Limitations

- **Legacy database revisions:** `Final` consolidated the Alembic history into
  `initial_schema`. A database stamped with a removed legacy revision (for example
  `add_project_messages`) cannot be upgraded in place. Back up valuable data first;
  only use the confirmed `make reset-db` path for disposable local data. Fresh
  databases and the isolated test database use `initial_schema` successfully.
- **Google OAuth:** no provider credentials are committed, and the feature returns a
  controlled unavailable response until a local client is configured. This audit did
  not perform a live provider login.
- **API-key lifecycle:** keys can be issued, listed, and revoked. There is no in-place
  rotation route; revoke the old key and issue a new one.
- **Rate limiting:** public-API windows are in process memory. They reset on backend
  restart and are not shared across multiple backend processes.
- **Import authorization semantics:** a viewer or outsider importing an exported
  project with a name receives a new owned project rather than a rejection. Assignees
  that cannot belong to that newly created project are cleared.
- **Internationalization:** the three locale catalogs have matching keys, but stored
  notification bodies are currently generated in English, so the official complete
  multi-language module is not claimed.
- **Notifications:** only project invites, task assignments, and task-status changes
  generate notifications; the official all-create/update/delete notification module
  is not claimed.
- **Frontend lint script:** unscoped `npm run lint` also scans `node_modules` in the
  image and reports dependency parse errors. Use `npm run lint -- src`; application
  source is clean.
- Automated tests do not replace a final browser walkthrough of file-picker,
  preview/download, OAuth, responsive layout, and language behavior.

## Team

| Login | Existing repository role | Main contribution area |
|---|---|---|
| **Eraad** | Tech lead; backend auth/security | Compose/Make/TLS, JWT and Argon2 auth, Google OAuth, administrator management, health/backups |
| **khderdou** | Project manager; backend projects/tasks | Projects, tasks, memberships, GDPR, notifications, project messages, coordination |
| **ksupinsk** | Backend public API/data | API keys, public API/rate limiting, search, attachments, CSV/JSON import/export |
| **nratajcz** | Frontend | React application, routing/pages/components, design, FR/EN/ES catalogs, legal pages |

The team used feature branches and shared API/database contracts to coordinate work.
AI tools were used as learning and review aids for unfamiliar framework, security,
and testing concepts; retained changes were reviewed and tested by the team.
