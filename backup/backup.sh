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
BACKUPS=/backups
UPLOADS=/uploads
STATUS_DIR=/status
NAME_PATTERN="^${POSTGRES_DB}-[0-9]{8}T[0-9]{6}Z\$"

PGHOST=db
PGUSER="$POSTGRES_USER"
PGPASSWORD="$(cat /run/secrets/postgres_password)"
export PGHOST PGUSER PGPASSWORD
umask 077

log() { echo "[backup] $(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }
die() { log "ERROR: $*"; exit 1; }

list_backups() { ls -1 "$BACKUPS" | grep -E "$NAME_PATTERN" | sort; }

iso_from_name() {
    echo "$1" | sed -E 's/.*-([0-9]{4})([0-9]{2})([0-9]{2})T([0-9]{2})([0-9]{2})([0-9]{2})Z$/\1-\2-\3T\4:\5:\6Z/'
}

dump_is_complete() { tail -n 10 "$1" | grep -q "PostgreSQL database dump complete"; }

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

take_backup() {
    name="$POSTGRES_DB-$(date -u +%Y%m%dT%H%M%SZ)"
    work="$BACKUPS/.$name.partial"
    [ ! -e "$BACKUPS/$name" ] || { log "ERROR: $name already exists"; return 1; }
    rm -rf "$work"
    mkdir "$work"
    if pg_dump --clean --if-exists --no-owner --no-privileges \
            --file "$work/database.sql" "$POSTGRES_DB" \
        && dump_is_complete "$work/database.sql" \
        && gzip "$work/database.sql" \
        && tar -czf "$work/uploads.tar.gz" -C "$UPLOADS" . \
        && gzip -t "$work/database.sql.gz" \
        && gzip -t "$work/uploads.tar.gz" \
        && mv "$work" "$BACKUPS/$name"; then
        log "wrote $name"
        prune
        return 0
    fi
    rm -rf "$work"
    log "ERROR: backup $name failed"
    return 1
}

once() {
    if take_backup; then
        write_status
    else
        write_status "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        exit 1
    fi
}

schedule() {
    trap 'exit 0' TERM INT
    rm -rf "$BACKUPS"/.*.partial
    write_status
    log "scheduler started: every $INTERVAL min, keeping $RETENTION backups"
    while :; do
        recent="$(find "$BACKUPS" -mindepth 1 -maxdepth 1 -type d -name "$POSTGRES_DB-*" -mmin "-$INTERVAL" | head -n 1)"
        if [ -z "$recent" ]; then
            if take_backup; then
                write_status
            else
                write_status "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
            fi
        fi
        sleep 60 &
        wait $!
    done
}

restore() {
    name="${1:-}"
    echo "$name" | grep -Eq "$NAME_PATTERN" || die "invalid backup name: '$name'"
    source="$BACKUPS/$name"
    [ -f "$source/database.sql.gz" ] && [ -f "$source/uploads.tar.gz" ] || die "incomplete backup: $name"

    sql="$(mktemp)"
    gzip -t "$source/uploads.tar.gz" || die "corrupt uploads archive in $name"
    gunzip -c "$source/database.sql.gz" > "$sql" || die "corrupt database dump in $name"
    dump_is_complete "$sql" || die "truncated database dump in $name"

    log "restoring database from $name"
    psql -d postgres -v ON_ERROR_STOP=1 -q \
        -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\" WITH (FORCE)" \
        -c "CREATE DATABASE \"$POSTGRES_DB\""
    psql -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -q --single-transaction -f "$sql" > /dev/null
    rm -f "$sql"

    log "restoring uploads from $name"
    find "$UPLOADS" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
    tar -xzf "$source/uploads.tar.gz" -C "$UPLOADS"
    chown -R 10001:10001 "$UPLOADS"
    chmod 700 "$UPLOADS"
    log "restore of $name complete"
}

case "${1:-}" in
    schedule) schedule ;;
    once) once ;;
    restore) restore "${2:-}" ;;
    *) die "usage: backup.sh schedule | once | restore <name>" ;;
esac
