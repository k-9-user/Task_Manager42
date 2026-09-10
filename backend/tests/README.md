# Backend Tests

Run from `backend` with `python -m pytest tests`. Do not run multiple pytest
processes against the same database: integration fixtures commit transactions
and truncate application tables before and after each test so concurrency tests
can use independent connections.

## Database Safety

Integration tests require an explicit `TEST_DATABASE_URL`. Its database must be
exactly `taskmanager_test`, its host must be `test-db` or loopback, credentials
must be supplied, and connection query overrides are rejected. If supplied,
`DATABASE_URL` must match. Use a dedicated disposable database and test-only
credentials; the name/host guard does not replace database privilege isolation.

For the Compose tests profile, both URLs should identify the dedicated test-db
service, for example:

```text
postgresql://test-only:test-only@test-db:5432/taskmanager_test
```

The guard executes before migrations or cleanup. Without `TEST_DATABASE_URL`,
application imports use in-memory SQLite and integration fixtures fail closed;
unit tests do not connect to PostgreSQL. Tests use deterministic test-only
signing/OAuth settings, never deployment secrets. No live Google request is
needed by the OAuth tests; provider callbacks use doubles.

## Fixture Boundaries

- `client`: real application, real database sessions, no authentication override.
- `member_client`: real application with B's explicit current-user override;
  B modules import this fixture as `client`. `login_as` changes that identity.
- `user_factory`: committed, detached valid users; defaults to password
  `valid-password-42`. Supplying `oauth_id` creates a Google-only identity.
- `database_engine`: applies Alembic head, only when requested.
- `database`: clears migrated tables per integration test, not an autouse fixture.
- C router suites retain SQLite isolation and identity overrides; factories now
  provide valid OAuth identities and canonical owner memberships. These suites
  are not PostgreSQL migration or end-to-end authentication tests.

## Suggested Runs

Database-free checks, without starting services:

```sh
env -u DATABASE_URL -u TEST_DATABASE_URL python -m pytest -q tests/test_database_safety.py tests/test_config.py tests/test_rate_limiter.py tests/test_api_key_auth.py tests/test_api_key_model.py tests/test_attachment_model.py tests/test_foundation.py::test_real_app_registers_all_feature_routes
```

Inside the Compose test-runner service with both guarded URLs configured:

```sh
python -m pytest -q tests/test_database.py tests/test_foundation.py
python -m pytest -q tests
```

From the repository root, the supported wrapper provisions the isolated service
and removes it after the run:

```sh
make test
make test TESTS='tests/test_foundation.py'
```

## Migration Contract

The approved disposable database reset recreates a complete initial schema.
The former test for an incremental status migration/admin backfill has therefore
been replaced, not skipped: tests now verify base-to-head round-trip of all
seven tables, column parity, Alembic metadata parity, populated-head idempotency,
authentication constraints, and case-insensitive username uniqueness.
This does not claim compatibility with databases stamped by the old incomplete
`db_install`; those require the approved disposable reset.

## Remaining Feature Evidence

Do not relax failing permission, persistence, or validation assertions to make
the integration run green. GDPR's oldest-member test is a strict expected
failure identified as `AUD-B-GDPR`: the current model has no membership
timestamp, while the handler sorts random UUIDs. B must add an explicit
chronology/succession policy before removing the marker. Browser execution
remains outside these tests; Nginx/container readiness is covered separately by
`make up` and `make smoke`.
