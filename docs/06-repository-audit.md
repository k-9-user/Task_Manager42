# Remaining Route Fixes

## Backend API

### Owner A - Authentication and users

#### `GET /api/auth/oauth/google/callback`

- [ ] Complete a safe browser handoff to the frontend instead of ending on a JSON token response.
- [ ] Keep bearer tokens out of URLs and browser history.
- [ ] Verify the complete Google sign-in, cancellation and provider-error flows with real configuration.

#### Missing API-key lifecycle routes - shared with C

- [ ] Add an authenticated mechanism to issue, list, revoke and rotate API keys.
- [ ] Show a raw key only once and persist only its hash.
- [ ] Document and test issued, rotated and revoked key behavior.
- [ ] Allow `X-API-Key` through CORS only if browser clients are explicitly supported.

### Owner B - Projects, tasks, GDPR and notifications

#### `GET /api/projects/{project_id}`

- [ ] Avoid returning an unbounded task collection; use the paginated task route or define a bounded project-detail response.

#### `PUT /api/projects/{project_id}`

- [ ] Reject explicit `null` for `name` instead of passing it to the non-null database column.
- [ ] Document `description: null` as the way to clear an optional description.

#### `POST /api/projects/{project_id}/members`

- [x] Provide project owners with a supported user lookup or invitation identifier; the admin-only user list cannot be the normal member-discovery flow. — `GET /api/users/lookup?email=` (2026-09-11).
- [ ] Define whether an existing member can have their project role changed; add a dedicated route only if that behavior is required.

#### `DELETE /api/projects/{project_id}/members/{user_id}`

- [ ] Clear that user's task assignments in the project when membership is removed, or explicitly define and enforce a different stale-assignment policy.
- [ ] Add the task-assignment update to the same locked transaction as membership removal.

#### `GET /api/projects/{project_id}/tasks`

- [ ] Add `Task.id` as a deterministic tie-breaker after `created_at` so pagination cannot duplicate or skip equal-timestamp tasks.
- [ ] Expose the fixed page size in the API contract or add a bounded `limit` parameter.

#### `POST /api/projects/{project_id}/tasks`

- [ ] Finalize whether `description` is required or nullable and make the schema and contract agree.
- [ ] Emit every notification required by the agreed creation event matrix, not only assignment notifications.

#### `PUT /api/tasks/{task_id}`

- [ ] Reject explicit `null` for non-null fields such as `title` and `status`.
- [ ] Document explicit `null` as the way to clear nullable fields such as `assignee_id` and `due_date`.
- [ ] Emit all required update notifications, including title, assignment, due-date and status changes according to the agreed recipient matrix.

#### `DELETE /api/tasks/{task_id}`

- [ ] Emit the required deletion notifications while retaining enough non-sensitive context for the notification to remain readable.
- [ ] Keep the existing attachment conflict explicit in the client workflow before retrying deletion.

#### `GET /api/gdpr/export`

- [ ] Inventory and export every agreed item of personal data, including newer profile fields, notifications and attachment metadata where applicable.
- [ ] Document which shared project/task data remains after account deletion.

#### `DELETE /api/gdpr/account`

- [ ] Add membership chronology if successor selection must use the oldest member; UUID order is not chronology.
- [ ] Define successor eligibility for banned users and projects with several owners.
- [ ] Define and implement the attachment-conflict workflow for account deletion.
- [ ] Send the required confirmation email and define behavior when email delivery fails.

#### `GET /api/notifications`

- [ ] Add bounded pagination and a deterministic tie-breaker.
- [ ] Complete notification production across all agreed project/task create, update and delete routes, including public API and import paths.

### Owner C - Public API, search, attachments and data transfer

#### `GET /api/v1/public/tasks`

- [ ] Add bounded pagination, a total count and deterministic ordering.
- [ ] Add supported filters only if they are included in the public API contract.

#### `POST /api/v1/public/tasks`

- [ ] Reuse the private task validation rules that apply to common fields.
- [ ] Emit the same required creation notifications as the private task route.

#### `PUT /api/v1/public/tasks/{task_id}`

- [ ] Reject an explicitly supplied `status: null` instead of treating it as a no-op.
- [ ] Emit the same required status-change notifications as the private task route.

#### `DELETE /api/v1/public/tasks/{task_id}`

- [ ] Emit the same required deletion notifications as the private task route.
- [ ] Keep attachment conflicts explicit and documented for API clients.

#### `GET /api/v1/public/projects`

- [ ] Add bounded pagination, a total count and deterministic ordering.

#### `GET /api/search/tasks`

- [ ] Add allow-listed, user-selectable sorting with a deterministic `Task.id` tie-breaker.
- [ ] Document the supported sort fields and direction parameters.
- [ ] Test combined text, status, project, sort and pagination filters without cross-project disclosure.

#### `POST /api/tasks/{task_id}/attachments`

- [ ] Check task visibility before returning MIME-specific validation errors so unsupported uploads cannot reveal whether a task ID exists.
- [ ] End the preliminary read transaction before slow filesystem I/O so the upload does not remain idle in a database transaction.
- [ ] Make rollback, upload-close and staged-file cleanup failures best-effort without masking the original error; log orphaned filenames safely.
- [ ] Add server-side content validation where declared MIME type and extension are insufficient.
- [ ] Reconcile the backend size limit with Nginx multipart overhead.

#### `DELETE /api/attachments/{attachment_id}`

- [ ] Add an operational orphan-file inventory and retry mechanism for post-commit unlink failures.

#### Missing attachment list/download routes

- [ ] Add authenticated attachment listing or include attachment metadata in task responses.
- [ ] Add an authenticated download route that rechecks current project membership.
- [ ] Do not expose the upload directory as unrestricted static content.

#### `GET /api/export`

- [ ] Prevent spreadsheet formula injection in CSV cells that begin with formula or control prefixes.
- [ ] Define whether CSV is a task-copy format or a round-trip export; preserve empty projects and null/empty distinctions only if round-trip behavior is promised.

#### `POST /api/import`

- [ ] Require every non-null assignee to be a member of the target project.
- [ ] Reuse private task title, status, length and nullable-field validation.
- [ ] Define and test duplicate headers, duplicate records, empty projects and null/empty CSV values.
- [ ] Make task-copy semantics explicit so repeated imports are not mistaken for idempotent restore operations.
- [ ] Emit required creation and assignment notifications only after the complete import has validated successfully.

## Frontend Routes

### Owner D - Shared route infrastructure

#### All frontend routes

- [x] Replace `useTranslation()` inside ordinary service functions with component translation or a non-hook i18n API. — `api.js`/`taskService.js` now import the `i18n` singleton directly (2026-09-11).
- [ ] Make the API client handle HTTP status, empty responses, non-JSON proxy errors and binary downloads.
- [ ] Use one shared session provider backed by `GET /api/users/me`; token presence alone is not authentication.
- [ ] Clear shared session state on logout, token expiry, ban, deletion and authorization failure.
- [x] Fix `PrivateRoute` so unauthenticated users redirect and authenticated users receive the actual child element. (2026-09-11)
- [ ] Add an admin-only route guard and a not-found route.
- [ ] Complete EN/FR/ES translations for visible copy, errors, loading states, legal text and notifications.
- [ ] Add semantic labels, keyboard focus behavior, responsive layouts and a clean browser-console check.

#### `/`

- [ ] Redirect authenticated users to the application and unauthenticated users to `/login`.

#### `/login`

- [ ] Remove all credential logging.
- [x] Call `POST /api/auth/login`, store the returned token through shared session state and navigate on success. — stored in `localStorage`, not yet a shared session provider (2026-09-11).
- [ ] Label and validate the identifier as email to match the backend payload.
- [ ] Disable duplicate submissions and display backend authentication errors.
- [ ] Add the Google sign-in entry point and complete the frontend side of the OAuth callback flow.

#### `/register`

- [x] Call `POST /api/auth/register` and establish the shared authenticated session from its response. — stored in `localStorage`, not yet a shared session provider (2026-09-11).
- [x] Display backend validation and uniqueness conflicts without logging submitted account data. (2026-09-11)
- [ ] Disable duplicate submissions and navigate only after confirmed success.

#### `/projects`

- [x] Remove `USE_MOCK` and all production mock project data. (2026-09-11)
- [x] Load projects from `GET /api/projects` and persist creation through `POST /api/projects`. (2026-09-11)
- [ ] Add empty, loading and recoverable error states.
- [ ] Show project actions only when the current project role permits them.

#### `/projects/:id`

- [x] Remove shared mock tasks and load the requested project ID from the real API. (2026-09-11)
- [ ] Add paginated task loading and persistent task create, edit, status, assignment, due-date and delete actions. — create/status done, edit/assignment/due-date/delete/pagination still missing (2026-09-11).
- [ ] Add project update/delete and member list/invite/remove controls. — member list/invite/remove done via `MembersPanel`; project update/delete still missing (2026-09-11).
- [ ] Render owner, editor and viewer capabilities correctly; viewers must remain read-only.
- [ ] Load attachment metadata after refresh and add validated upload, progress, authenticated download/preview and delete controls.
- [ ] Roll back optimistic UI changes when the server rejects a mutation.

#### `/Profile`

- [ ] Remove `USE_MOCK`, external default-avatar assumptions and fake profile data.
- [ ] Load `GET /api/users/me` and persist supported profile fields through `PUT /api/users/me`.
- [ ] Add accessible export, import and confirmed account-deletion actions.
- [ ] Handle account deletion conflicts and clear the shared session only after confirmed deletion.

#### `/admin/users`

- [ ] Protect the route with the shared admin guard.
- [ ] Correct API paths and consume `data.users`, `user.id` and `role` consistently.
- [ ] Await mutations and retain or restore rows when the server rejects an action.
- [ ] Replace invalid `<thread>` markup with `<thead>` and remove undefined identifiers.
- [ ] Add pagination using the backend `total` value.
- [ ] Add rename/display-name, ban/unban, role and delete controls with clear `409` conflict feedback.
- [ ] Reconcile the active session after self-demotion, self-ban or self-deletion.

#### `/Search`

- [x] Consume `data.tasks` rather than `data.task`. (2026-09-11)
- [ ] Allow filter-only searches without requiring text.
- [ ] Add project, sorting, page and limit controls that match `GET /api/search/tasks`.
- [ ] Display total results and navigable links to each task's project.
- [x] Remove duplicate error rendering. (2026-09-11)

#### `/PrivacyPolicy`

- [ ] Correct password-hashing, external-font/avatar, contact, retention and deletion statements to match actual behavior.
- [ ] Provide complete EN/FR/ES versions.

#### `/TermsOfService`

- [ ] Review the terms against actual application behavior and supported features.
- [ ] Provide complete EN/FR/ES versions.

#### Missing notification view

- [ ] Add an authenticated notification view or panel using the list, single-read and read-all endpoints.
- [ ] Show unread state, related project/task navigation, empty state and pagination.

#### Missing status view

- [ ] Add the user-facing status page required by the selected health module.
- [ ] Keep operational backup scheduling, retention and restore drills outside the browser route but link documented status and recovery information where appropriate.
