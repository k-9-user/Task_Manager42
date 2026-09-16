# Local Secrets

`make setup` creates ignored secret files in this directory. The directory is
private on the host; individual files remain readable by their explicitly
authorized Linux containers through Docker Compose secret mounts.

Expected generated files:

- `postgres_password`
- `database_url`
- `jwt_secret`
- `oauth_session_secret`
- `oauth_google_client_secret`
- `bootstrap_admin_password`

Never commit their contents. `make setup` preserves an existing new-format
configuration and refuses missing or conflicting files instead of rotating a
credential silently.
