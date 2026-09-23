#!/bin/sh
# Automated backups and disaster recovery for the task-manager stack.
#
# Runs in postgres:17-alpine so pg_dump and psql match the server major version.
# One backup is one directory, renamed into place only once complete:
#   /backups/<POSTGRES_DB>-<YYYYMMDDTHHMMSSZ>/{database.sql.gz,uploads.tar.gz}
#
#   schedule        back up whenever the newest backup is older than the interval
#   once            take one backup now (make backup)
#   restore <name>  replace the database and uploads with one backup (make restore)
set -eu

: "${POSTGRES_DB:?}" "${POSTGRES_USER:?}"
INTERVAL="${BACKUP_INTERVAL_MINUTES:-60}"
RETENTION="${BACKUP_RETENTION:-24}"
ATTEMPTS=3
BACKUPS=/backups
UPLOADS=/uploads
STATUS_DIR=/status
STAGING="$UPLOADS/.restore"
STAGING_DB="${POSTGRES_DB}_restore"
PREVIOUS_DB="${POSTGRES_DB}_previous"
NAME_PATTERN="^${POSTGRES_DB}-[0-9]{8}T[0-9]{6}Z\$"

PGHOST=db
PGUSER="$POSTGRES_USER"
PGPASSWORD="$(cat /run/secrets/postgres_password)"
PGOPTIONS="-c client_min_messages=warning"
export PGHOST PGUSER PGPASSWORD PGOPTIONS
umask 077

now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[backup] $(now) $*"; }
die() { log "ERROR: $*"; exit 1; }

# Every backup and restore holds this lock, so runs never overlap.
locked() { ( flock 9 || exit 1; "$@" ) 9>"$STATUS_DIR/.lock"; }

list_backups() { ls -1 "$BACKUPS" | grep -E "$NAME_PATTERN" | sort; }

iso_from_name() {
    echo "$1" | sed -E 's/.*-([0-9]{4})([0-9]{2})([0-9]{2})T([0-9]{2})([0-9]{2})([0-9]{2})Z$/\1-\2-\3T\4:\5:\6Z/'
}

dump_is_complete() { tail -n 10 "$1" | grep -q "PostgreSQL database dump complete"; }

# Upload file names referenced by attachments.file_url and tasks.banner_url in a plain dump.
# A table whose column is not found yields an impossible name, so the check fails closed.
referenced_uploads() {
    awk -F '\t' '
        /^COPY public\.(attachments|tasks) \(/ {
            wanted = ($0 ~ /^COPY public\.attachments /) ? "file_url" : "banner_url"
            header = $0
            sub(/^[^(]*\(/, "", header)
            sub(/\).*$/, "", header)
            count = split(header, names, ", ")
            column = 0
            for (i = 1; i <= count; i++) if (names[i] == wanted) column = i
            if (!column) print "missing column " wanted
            copying = column
            next
        }
        copying && $0 == "\\." { copying = 0; next }
        copying && $copying != "\\N" { name = $copying; sub(/^.*\//, "", name); print name }
    ' "$1" | sort -u
}

archived_uploads() { tar -tzf "$1" | sed -n 's|^\./\(..*\)$|\1|p' | sort -u; }

# $1 plain dump, $2 sorted archived names: every upload the dump references must be archived.
uploads_complete() {
    missing="$(referenced_uploads "$1" | comm -23 - "$2")"
    [ -z "$missing" ] || { log "uploads referenced by the database but not archived: $(echo $missing)"; return 1; }
}

write_status() {
    [ -d "$STATUS_DIR" ] || return 0
    latest="$(list_backups | tail -n 1)"
    count="$(list_backups | wc -l | tr -d ' ')"
    success=null name=null failure=null
    if [ -n "$latest" ]; then
        success="\"$(iso_from_name "$latest")\"" name="\"$latest\""
    fi
    if [ -n "${1:-}" ]; then
        failure="\"$1\""
    fi
    temporary="$(mktemp "$STATUS_DIR/.status.XXXXXX")"
    printf '{"last_success_at": %s, "last_backup": %s, "count": %s, "interval_minutes": %s, "last_failure_at": %s}\n' \
        "$success" "$name" "$count" "$INTERVAL" "$failure" > "$temporary"
    chmod 644 "$temporary"
    mv "$temporary" "$STATUS_DIR/status.json"
}

prune() {
    excess=$(( $(list_backups | wc -l) - RETENTION ))
    [ "$excess" -gt 0 ] || return 0
    list_backups | head -n "$excess" | while read -r stale; do
        rm -rf "${BACKUPS:?}/$stale"
        log "pruned $stale"
    done
}

# Dump first, archive second: an upload is written before its row commits, so only a delete
# racing the two steps can leave a dumped row without its file, and the check catches it.
capture() {
    pg_dump --clean --if-exists --no-owner --no-privileges --file "$1/database.sql" "$POSTGRES_DB" \
        && dump_is_complete "$1/database.sql" \
        && tar -czf "$1/uploads.tar.gz" --exclude=./.restore -C "$UPLOADS" . \
        && archived_uploads "$1/uploads.tar.gz" > "$1/archived" \
        && uploads_complete "$1/database.sql" "$1/archived" \
        && rm "$1/archived" \
        && gzip "$1/database.sql" \
        && gzip -t "$1/database.sql.gz" \
        && gzip -t "$1/uploads.tar.gz"
}

take_backup() {
    name="$POSTGRES_DB-$(date -u +%Y%m%dT%H%M%SZ)"
    while [ -e "$BACKUPS/$name" ]; do
        sleep 1
        name="$POSTGRES_DB-$(date -u +%Y%m%dT%H%M%SZ)"
    done
    work="$BACKUPS/.$name.partial"
    attempt=1
    while :; do
        rm -rf "$work"
        mkdir "$work"
        if capture "$work" && mv "$work" "$BACKUPS/$name"; then
            log "wrote $name"
            prune
            return 0
        fi
        rm -rf "$work"
        [ "$attempt" -lt "$ATTEMPTS" ] || break
        attempt=$((attempt + 1))
        log "retrying $name (attempt $attempt of $ATTEMPTS)"
    done
    log "ERROR: backup $name failed"
    return 1
}

backup_once() {
    if take_backup; then
        write_status
    else
        write_status "$(now)"
        return 1
    fi
}

start_schedule() {
    rm -rf "$BACKUPS"/.*.partial
    write_status
}

scheduled_tick() {
    [ -z "$(find "$BACKUPS" -mindepth 1 -maxdepth 1 -type d -name "$POSTGRES_DB-*" -mmin "-$INTERVAL" | head -n 1)" ] || return 0
    backup_once
}

schedule() {
    trap 'exit 0' TERM INT
    locked start_schedule
    log "scheduler started: every $INTERVAL min, keeping $RETENTION backups"
    while :; do
        locked scheduled_tick || :
        sleep 60 &
        wait $!
    done
}

drop_database() { psql -d postgres -q -c "DROP DATABASE IF EXISTS \"$1\" WITH (FORCE)"; }

discard_staging() {
    rm -rf "$STAGING"
    [ -z "${sql:-}" ] || rm -f "$sql"
    drop_database "$STAGING_DB" || :
    drop_database "$PREVIOUS_DB" || :
}

restore_now() {
    name="$1"
    echo "$name" | grep -Eq "$NAME_PATTERN" || die "invalid backup name: '$name'"
    source="$BACKUPS/$name"
    [ -f "$source/database.sql.gz" ] && [ -f "$source/uploads.tar.gz" ] || die "incomplete backup: $name"

    trap discard_staging EXIT
    discard_staging
    mkdir -p "$STAGING/new"
    sql="$(mktemp)"

    log "checking $name"
    { gunzip -c "$source/database.sql.gz" > "$sql" && dump_is_complete "$sql"; } \
        || die "corrupt or truncated database dump in $name"
    tar -xzf "$source/uploads.tar.gz" -C "$STAGING/new" || die "corrupt uploads archive in $name"
    archived_uploads "$source/uploads.tar.gz" > "$STAGING/names"
    uploads_complete "$sql" "$STAGING/names" || die "inconsistent backup: $name"
    chown -R 10001:10001 "$STAGING/new"

    log "loading $name into $STAGING_DB"
    psql -d postgres -v ON_ERROR_STOP=1 -q -c "CREATE DATABASE \"$STAGING_DB\"" \
        || die "could not create $STAGING_DB"
    psql -d "$STAGING_DB" -v ON_ERROR_STOP=1 -q --single-transaction -f "$sql" > /dev/null \
        || die "the dump in $name does not load; live data unchanged"

    log "adding uploads from $name"
    for file in "$STAGING/new"/* "$STAGING/new"/.[!.]*; do
        [ -e "$file" ] || continue
        mv -f "$file" "$UPLOADS/" || die "could not add uploads; live database unchanged"
    done

    log "switching to the restored database"
    psql -d postgres -v ON_ERROR_STOP=1 -q -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('$POSTGRES_DB', '$STAGING_DB') AND pid <> pg_backend_pid()" \
        > /dev/null || die "could not disconnect database sessions; live database unchanged"
    psql -d postgres -v ON_ERROR_STOP=1 -q --single-transaction \
        -c "ALTER DATABASE \"$POSTGRES_DB\" RENAME TO \"$PREVIOUS_DB\"" \
        -c "ALTER DATABASE \"$STAGING_DB\" RENAME TO \"$POSTGRES_DB\"" \
        || die "could not switch databases; live database unchanged"

    log "removing uploads that are not in $name"
    ls -A "$UPLOADS" | while read -r entry; do
        [ "$entry" = .restore ] || grep -qxF "$entry" "$STAGING/names" || rm -rf "${UPLOADS:?}/$entry"
    done
    chown 10001:10001 "$UPLOADS"
    chmod 700 "$UPLOADS"
    log "restore of $name complete"
}

case "${1:-}" in
    schedule) schedule ;;
    once) locked backup_once ;;
    restore) locked restore_now "${2:-}" ;;
    *) die "usage: backup.sh schedule | once | restore <name>" ;;
esac
