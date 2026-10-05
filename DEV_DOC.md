# Development and Operations Guide

Start with [README.md](README.md) for the project overview, module claims, and quick
start. Run commands here from the repository root. The stack is intended for local
use at **https://localhost**.

## Configuration and Credentials

`make setup` creates `.env`, secret files, and missing TLS files. `make check` validates
local tools, Docker, configuration, secret consistency, TLS, and Compose. The checked
settings are supplied to Compose by Make; a bare Compose invocation lacks the required
`DATA_DIR` value. Existing valid credentials are preserved, not regenerated.

`.env` contains non-secret settings listed in [.env.example](.env.example). Use plain
`KEY=value` entries: no quotes, variable expansion, inline comments, duplicate keys,
or extra keys. Secrets belong in the files below, not in `.env`.

| File under `secrets/` | Purpose |
|---|---|
| `postgres_password` | Database password |
| `database_url` | Connection URL matching the database name, user, and password |
| `jwt_secret` | JWT signing key |
| `oauth_session_secret` | OAuth session signing key |
| `oauth_google_client_secret` | Optional Google provider secret; empty when disabled |
| `bootstrap_admin_password` | Initial administrator password |

The directory must be private (`0700`). Generated files use `0644` inside that private
directory so their authorized containers can read them. Files must be regular,
non-symlink files containing one value without a newline. Keep them, private TLS keys,
exports, and persistent data out of version control. See [secrets/README.md](secrets/README.md).

### Administrator bootstrap

Before first startup, configure `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_USERNAME`
in `.env` if their defaults are unsuitable. The password is in
`secrets/bootstrap_admin_password`. Read it locally to log in; do not share it.

At later startup, the earliest account must still match these credentials and be an
active administrator. Changing them independently blocks startup. Restore the matching
settings when this happens; reset only disposable data. The application protects the
bootstrap administrator from rename, demotion, ban, or deletion.

Account deletion transfers shared projects to another member, choosing an existing
owner first and otherwise the oldest member. Projects with no remaining member are
removed. Task assignments to the departing user are cleared.

### Google OAuth

1. Create a Google OAuth client for a web application and authorize
   `https://localhost/api/auth/oauth/google/callback` as its redirect URI.
2. Set `OAUTH_GOOGLE_CLIENT_ID` in `.env`; keep `OAUTH_GOOGLE_REDIRECT_URI` equal to
   that callback.
3. Write the matching provider secret to `secrets/oauth_google_client_secret`, without
   a trailing newline.
4. Run `make check` and `make up`, then use Google sign-in on the login page.

To disable provider login, leave both the client ID and provider-secret file empty;
the callback setting remains unchanged. Direct OAuth requests then return a controlled
503 response. Signing secrets remain required even with Google login disabled.

The callback uses a short-lived Secure/HttpOnly browser handoff; the frontend exchanges
it once at `/api/auth/oauth/google/exchange`. Bearer tokens are not placed in redirect URLs.

## API Access and Data Transfer

The running application exposes [Swagger UI](https://localhost/docs) and its generated
[OpenAPI specification](https://localhost/openapi.json). Use those for current request
and response schemas. Browser/account APIs use bearer JWTs; public routes use `X-API-Key`.

### Issue and use an API key

Log in through `POST /api/auth/login` in Swagger UI using `identifier` (email or username)
and `password`. Copy `data.token` from the successful response. In a Bash or zsh terminal,
read it into a temporary variable without echoing it:

```sh
read -rs TM42_TOKEN
curl --cacert nginx/certs/localhost.crt \
  -X POST https://localhost/api/api-keys \
  -H "Authorization: Bearer ${TM42_TOKEN}"
```

Paste the token at the prompt and press Enter before the curl command runs. Issuance
returns `data.api_key.id` and `data.api_key.key`; the raw key appears only in this response.
Save it privately, then enter it at the next hidden prompt:

```sh
read -rs TM42_API_KEY
curl --cacert nginx/certs/localhost.crt \
  https://localhost/api/v1/public/projects \
  -H "X-API-Key: ${TM42_API_KEY}"
```

| Method and route | Behavior |
|---|---|
| `GET /api/api-keys` | List your key metadata using bearer authentication |
| `DELETE /api/api-keys/{key_id}` | Revoke your key using bearer authentication |
| `GET /api/v1/public/projects` | List projects of which the key owner is a member |
| `GET /api/v1/public/tasks` | List tasks visible to that member |
| `POST /api/v1/public/tasks` | Create a task with `project_id` and `title`; owner/editor only |
| `PUT /api/v1/public/tasks/{task_id}` | Update `status`; owner/editor only |
| `DELETE /api/v1/public/tasks/{task_id}` | Delete a task and its files/comments; owner only |

There is no rotation endpoint: issue a replacement and revoke the old key. Public calls
are limited to 60 requests per 60-second window per key, returning 429 and `Retry-After`
when exceeded. Windows are stored in memory, reset on backend restart, and are not shared
across backend processes. Keys are stored as hashes. Never paste real credentials into
shared transcripts or diagnostic reports.

### Search, attachments, and import/export

- `/api/search/tasks` and `/api/search/projects` support text search, safe sorting, and
  pagination restricted to visible projects. Task search also accepts status/project
  filters. The default page size is 20 and maximum is 100.
- Task attachment routes validate type/size and require current project permissions.
  Use `/api/attachments/{attachment_id}` with bearer authentication for file access;
  storage URLs are not public download links.
- `/api/export?format=json|csv` exports visible project/task data; add `project_id` to
  select one project. `/api/import` accepts a multipart `file` field.

For example, with the bearer token from above:

```sh
curl --cacert nginx/certs/localhost.crt \
  'https://localhost/api/export?format=json' \
  -H "Authorization: Bearer ${TM42_TOKEN}" -o task-export.json
curl --cacert nginx/certs/localhost.crt \
  https://localhost/api/import \
  -H "Authorization: Bearer ${TM42_TOKEN}" \
  -F 'file=@task-export.json;type=application/json'
unset TM42_TOKEN TM42_API_KEY
```

Import creates new tasks after validating the entire file. Writable existing projects
are reused; otherwise a named source project becomes a new project owned by the importer.
Assignees unavailable in a recreated project are cleared. Import/export transfers task
data, not uploaded file bytes, and importing does not award gamification progress.

## Backups and Recovery

The host directories `data/postgres` and `data/uploads` hold persistent database and
upload data. `data/backups` holds backups; stopping containers preserves all three.
Each complete backup contains `database.sql.gz` and `uploads.tar.gz` in a directory named
`<POSTGRES_DB>-<UTC timestamp>`.

The backup service defaults to a 60-minute interval and retains 24 complete backups.
Set `BACKUP_INTERVAL_MINUTES` and `BACKUP_RETENTION` in `.env` to change these defaults,
then run `make up`. Manual backups use the same retention policy and lock as scheduled
backups and restoration.

```sh
make backup
ls data/backups
make restore
make smoke
```

`make restore` selects the latest complete backup and requires typing `restore`.
To select another, use `make restore BACKUP=<directory-name>` with a name from the listing.
**Restoration replaces the current database and uploads.** Take a backup first when the
current state matters. The site is unavailable during recovery.

Recovery stops nginx/backend/backup, checks archives and referenced files, loads a
staging database, prepares uploads, then switches to the restored database and removes
extra files. The wrapper restarts the stack even if restoration fails. After a failure,
check service logs and current data before retrying. Restored data must still match
bootstrap administrator settings; startup applies the current migration.

The [status page](https://localhost/status) and `/api/status` report backups as `ok`,
`missing`, `stale`, or `failing`. Stale means the last successful backup is older than
twice its interval. `/health` separately checks database connectivity.

Up to one backup interval of changes may be lost. Backups share the disk with live data;
copy them elsewhere for protection against disk loss. They include password hashes and
private uploads, so protect the copies as sensitive data.

### Cleanup effects

| Command | Data effect |
|---|---|
| `make down` / `make clean` | Preserve database, uploads, backups, and images |
| `make reset-db` | Confirmed database removal; uploads and backups stay |
| `make fclean` | Confirmed container/image/volume cleanup and database/upload deletion; backups stay |
| `make re` | Same deletion as full cleanup, then rebuild/start |
| `make restore` | Confirmed replacement of database/uploads from a selected backup |

Cleanup preserves source, configuration, secret files, and certificates. Prefer fixing
configuration to resetting data. Do not use destructive commands as routine troubleshooting.

## Developer Checks

Backend integration tests run against isolated PostgreSQL 17 storage without mounting
development data or uploads:

```sh
make test
make test TESTS='tests/test_public_api.py tests/test_search.py'
python3 scripts/test.py -v
```

`TESTS` supplies pytest arguments. The wrapper removes the test database container after
the run, including on test failure. Avoid simultaneous test runs in the same stack.

Frontend checks can use Docker without host Node dependencies:

```sh
docker build -t task-manager-front:latest frontend
docker run --rm task-manager-front:latest npm run lint -- src
docker run --rm task-manager-front:latest npm run build
```

Scope linting to `src` to avoid scanning installed dependencies. Run `make smoke` after
startup for read-only TLS, health, frontend/CSP, and OpenAPI checks. It does not execute
browser JavaScript or test authenticated workflows.

Browser checks should cover registration/login, role-specific project/task actions,
search, uploads and downloads, data transfer, GDPR, gamification, responsive layouts,
FR/EN/ES switching, and the browser console. Include Google sign-in when configured.
Chrome is the baseline; Brave and Edge are the additional supported browsers.

## Troubleshooting

| Symptom | Check or action |
|---|---|
| Startup/configuration failure | Run `make check`; verify Docker is running and required ports are free |
| Existing database rejected | Restore matching bootstrap identity/password; do not automatically reset |
| Self-signed certificate warning | Trust the generated `nginx/certs/localhost.crt`; never share its private key |
| Google login unavailable | Check the local client ID/secret pair and exact registered callback; restart with `make up` |
| GDPR email absent from personal inbox | Open [Mailpit](http://localhost:8025); messages are captured locally |
| Backup stale/failing | Check `make logs`, disk space, and `data/backups`; retry with `make backup` after fixing the cause |
| Blank frontend or Swagger page | Check browser console/CSP and run `make smoke`; keep script policy strict |
| Database migration cannot find a revision | The shipped migration is `initial_schema`; preserve valuable data and recover from a compatible backup |

Swagger UI loads its assets from a CDN and needs network access. Its inline-script hash
in `nginx/default.conf` must match FastAPI's generated bootstrap script; `make smoke`
checks this after dependency changes. Frontend scripts use per-request CSP nonces.

Notification events are limited to project invites, task assignments, and task-status
changes. Stored notification bodies and GDPR operation emails currently use English.
