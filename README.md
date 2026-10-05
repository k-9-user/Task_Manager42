*This project has been created as part of the 42 curriculum by eraad, khderdou, ksupinsk, nratajcz.*

# Task Manager 42

## Description

Task Manager 42 is a collaborative project and task manager. Its goal is to help teams
organize shared work: create projects, manage membership, assign tasks, discuss progress,
and exchange files. A React interface and a FastAPI backend share PostgreSQL persistence,
with nginx providing HTTPS access. Docker Compose runs the application locally at
[https://localhost](https://localhost).

## Team

| Member | Roles | Responsibilities |
|---|---|---|
| **eraad** | Tech Lead, Backend Developer | Authentication, security, infrastructure, administration, backups, gamification |
| **khderdou** | Product Owner, Project Manager, Backend Developer | Product goals, roadmap, coordination, projects/tasks, memberships, GDPR |
| **ksupinsk** | Backend Developer | Public API, API keys, search, uploads, import/export |
| **nratajcz** | Frontend Developer | React interface, design, navigation, translations, legal pages |

## Project Management

The team exchanged Markdown files containing tasks, goals, and the roadmap. Work was
split among authentication/infrastructure, project management features, public API/data,
and frontend development. Discord discussions and meetings 3–4 times a week supported
coordination and decisions about shared routes, database relationships, and integration.

## Technical Stack

| Technology | Use and reason for choosing it |
|---|---|
| React 19, Vite 8, Tailwind CSS 4 | Component-based interface, fast development tooling, and shared styling utilities |
| i18next / react-i18next | English, French, and Spanish catalogs with a language switcher |
| FastAPI, Pydantic, Python 3.12 | Typed request validation and generated interactive API documentation |
| PostgreSQL 17 | Relational storage and constraints suited to users, memberships, projects, and tasks |
| SQLAlchemy 2, Alembic | ORM queries and a reproducible database schema |
| PyJWT, Argon2, Authlib | Bearer sessions, salted password hashing, and Google OAuth/OIDC |
| Docker Compose, nginx, Mailpit | Shared local environment, HTTPS gateway, and local capture of operation emails |

## Database Schema

Every table uses a UUID primary key. Foreign keys are UUIDs; timestamps include time
zones. The schema is defined in `backend/alembic/versions/initial_schema.py`.

| Table | Key fields and relationships |
|---|---|
| `users` | Unique email/username (strings), password hash or OAuth identity, role/status enums |
| `projects` | Name (string), description (text), owner → user |
| `project_members` | Project → project, user → user, owner/editor/viewer enum; unique membership pair |
| `tasks` | Project → project, title/description, status enum, nullable assignee → user, due date (date) |
| `attachments` | Task → task, nullable uploader → user, filename and storage URL (strings) |
| `comments` | Task → task, author → user, content (text) |
| `project_messages` | Project → project, author → user, content (text) |
| `api_keys` | User → user, unique key hash (string) |
| `notifications` | Recipient → user, type enum, content (text), read flag (boolean), nullable task/project context |
| `user_activities` | User → user, track (string), counted item UUID; unique user/track/item |
| `user_achievements` | User → user, achievement key (string), XP (integer), unlock timestamp |
| `user_badges` | User → user, badge key (string), award timestamp |

Projects contain memberships and tasks; tasks contain comments and attachments.
Deleting a project/task cascades to its dependent records. Deleted users leave nullable
assignees/uploaders, and deleted resources leave nullable notification context.
Account deletion transfers shared projects to another member or removes projects with
no remaining member.

## Features

| Feature | Functionality | Contributors |
|---|---|---|
| Accounts and administration | Email/username login, registration, profiles, optional Google login; admin search, editing, roles, bans, deletion | eraad; nratajcz (UI) |
| Projects and tasks | CRUD, owner/editor/viewer permissions, membership management, assignments, deadlines, task status | khderdou; nratajcz (UI) |
| Collaboration | Task comments, project messages, and notifications for invitations, assignments, and status changes | khderdou; nratajcz (UI) |
| Public API and search | API-key access, rate limiting, task/project search with filters, sorting, and pagination | ksupinsk; nratajcz (search UI) |
| Files and portability | Private attachments/banners, validation, upload progress, preview/download/deletion, JSON/CSV import/export | ksupinsk; nratajcz (UI) |
| Personal data | Readable GDPR export, confirmed deletion, and operation emails captured locally | khderdou; nratajcz (UI) |
| Gamification | Persistent achievements, XP, levels, badges/titles, progress, and unlock feedback | eraad; nratajcz (UI) |
| Operations | Health/status endpoints and page, scheduled database/upload backups, confirmed recovery | eraad |
| Interface and legal information | Responsive UI, FR/EN/ES translations, Chrome/Brave/Edge support, Privacy Policy, Terms of Service, About page | nratajcz |

## Modules

These are implemented module claims for evaluation.

| Module | Type | Points | Implementation and purpose | Contributors |
|---|---|---:|---|---|
| Frontend and backend frameworks | Major | 2 | React/FastAPI structure the interface and API | nratajcz, eraad |
| Public API | Major | 2 | Five documented routes with API-key auth and rate limiting enable external clients | ksupinsk |
| Advanced permissions | Major | 2 | Account administration and role-specific views/actions control access | eraad, nratajcz |
| Organization system | Major | 2 | Project CRUD, member add/remove, and permitted task actions organize team work | khderdou, nratajcz |
| ORM | Minor | 1 | SQLAlchemy maps the relational model to application objects | eraad |
| Advanced search | Minor | 1 | Text filters, sorting, and pagination help locate visible work | ksupinsk, nratajcz |
| File upload and management | Minor | 1 | Validated private uploads, progress, preview, and deletion support task files | ksupinsk, nratajcz |
| Remote authentication | Minor | 1 | Google OAuth/OIDC provides an alternative login method | eraad |
| Data export and import | Minor | 1 | JSON/CSV transfer with validated imports supports portability | ksupinsk |
| GDPR compliance | Minor | 1 | Data export, confirmed deletion, and operation emails support personal-data control | khderdou |
| Health/status/backups/disaster recovery | Minor | 1 | Status reporting and scheduled database/upload backups support recovery | eraad |
| Gamification | Minor | 1 | Stored achievements, levels, badges, rules, and feedback reward participation | eraad, nratajcz |
| Multiple languages | Minor | 1 | Complete FR/EN/ES UI translations and switching broaden access | nratajcz |
| Additional browsers | Minor | 1 | Brave and Edge compatibility extends browser support | nratajcz |

**Claimed total: 4 major × 2 + 10 minor × 1 = 18 points**.

## Individual Contributions

- **eraad** built Docker/Compose, the Make entry point, TLS/nginx, authentication,
  Google OAuth, administrator protections, health/backups, and server-side gamification.
- **khderdou** defined product priorities and coordinated the roadmap; implemented
  projects, tasks, memberships, comments/messages, notifications, and GDPR operations.
- **ksupinsk** implemented public API authorization/rate limiting, API-key management,
  search, private attachments/banners, and validated JSON/CSV transfer.
- **nratajcz** built React pages, routing, shared components, styling, backend integration,
  responsive layouts, translations, and legal pages.

Gamification arrived late and required changes across existing features. The team split
integration into smaller modules and assembled them in the respective application areas.
Refactoring existing functions was another challenge during integration and cleanup.

## Instructions

### Prerequisites

- Docker with Compose v2 supporting `up --wait`, and a running Docker daemon.
- Make, Python 3.9+ for the host wrapper, OpenSSL supporting `req -addext` and
  `x509 -ext`, and curl.
- Free local ports 80, 443, and 8025; network access for image/dependency downloads.
- A supported browser: Chrome, Brave, or Edge.

Python 3.12, Node 24, and PostgreSQL 17 run in containers; host application dependencies
are unnecessary. From the repository root:

```sh
make
```

This sets up `.env`, private secret files, and a local TLS certificate, checks configuration,
then builds, migrates, starts, and smoke-checks the stack. Open
[https://localhost](https://localhost); trust `nginx/certs/localhost.crt` if the browser
warns about the self-signed certificate. Use Make as the supported entry point.

The initial administrator uses `BOOTSTRAP_ADMIN_EMAIL`/`BOOTSTRAP_ADMIN_USERNAME` in
`.env` and the password in `secrets/bootstrap_admin_password`. Regular registrations
create ordinary users. Keep credentials private and preserve bootstrap settings after
initial startup. Database and uploads persist under `data/`.

For Google login, set `OAUTH_GOOGLE_CLIENT_ID` in `.env`, keep the registered callback
at `https://localhost/api/auth/oauth/google/callback`, and put the matching secret in
`secrets/oauth_google_client_secret`. Run `make check` then `make up`.

| Command | Purpose |
|---|---|
| `make` / `make all` | Set up and start the complete stack |
| `make setup` / `make check` | Prepare local configuration / validate it |
| `make up` | Build and start services |
| `make down` / `make clean` | Stop services; preserve data and images |
| `make ps` / `make logs` | Show services / follow logs |
| `make smoke` | Run read-only HTTPS smoke checks |
| `make test` | Run backend tests with an isolated PostgreSQL |
| `make backup` | Back up database and uploads now |
| `make restore BACKUP=<name>` | Restore a selected backup; omit `BACKUP` for latest |
| `make reset-db` | Delete database only; preserve uploads and backups |
| `make fclean` / `make re` | Remove project containers/images/volumes and database/uploads; `re` rebuilds |

Restore and destructive commands require typed confirmation. Backups remain in
`data/backups/`, including after full cleanup; defaults are hourly backups with 24 retained.
Mailpit captures GDPR operation emails at [http://localhost:8025](http://localhost:8025);
these messages are not delivered to external addresses.

Use [Swagger UI](https://localhost/docs), the
[OpenAPI specification](https://localhost/openapi.json), and the
[status page](https://localhost/status). Public requests authenticate with `X-API-Key`;
keys are issued through the authenticated API and shown once.
See [DEV_DOC.md](DEV_DOC.md) for setup details, examples, recovery, and developer checks.

## Resources

- [React](https://react.dev/) and [Tailwind CSS](https://tailwindcss.com/docs) — frontend and styling.
- [FastAPI](https://fastapi.tiangolo.com/) — validation and API documentation.
- [SQLAlchemy](https://docs.sqlalchemy.org/en/20/) and [Alembic](https://alembic.sqlalchemy.org/en/latest/) — ORM and schema management.
- [PostgreSQL 17](https://www.postgresql.org/docs/17/) — relational database reference.
- [i18next](https://www.i18next.com/) — internationalization.
- [Docker Compose](https://docs.docker.com/compose/) — container orchestration.
- [OWASP Top 10](https://owasp.org/projects/top-ten) — web security guidance.

### AI Usage

The team mainly used Claude Code and Codex to explain unfamiliar technologies, write
and revise documentation, generate task briefs, and rewrite selected code sections.
They also helped develop the test suite, and assisted backend cleanup: shared permission
helpers, schema consolidation. Each student reviewed and understood retained content
and ran the relevant code and tests; the team remains responsible for the documentation
and implementation.
