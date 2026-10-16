#!/bin/sh
# Prepare a docker DB container for trial run

set -e

if [ $# -ne 2 ]; then
    echo "usage: $0 <container> <image>" >&2
    exit 1
fi

container=$1
image=$2

psql_exec() {
    docker exec "$container" psql -v ON_ERROR_STOP=1 -U buildbot -d bbtest "$@"
}

case "$image" in
    mariadb:*|mysql:*)
        ;;
    postgres:*)
        # limit WAL size and autovacuum often in tests
        # each test recreate the DB, generating WAL churn.
        for setting in \
            "max_wal_size = '64MB'" \
            "min_wal_size = '32MB'" \
            "fsync = off" \
            "full_page_writes = off" \
            "synchronous_commit = off" \
            "autovacuum_naptime = 1" \
            "autovacuum_vacuum_cost_delay = 0" \
            "autovacuum_vacuum_scale_factor = 0" \
            "autovacuum_vacuum_threshold = 1000"
        do
            psql_exec -c "ALTER SYSTEM SET $setting"
        done
        psql_exec -c "SELECT pg_reload_conf()"
        ;;
    *)
        echo "Unknown database image: $image" >&2
        exit 1
        ;;
esac
