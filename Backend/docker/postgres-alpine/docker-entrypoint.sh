#!/bin/sh
set -eu

POSTGRES_DB="${POSTGRES_DB:-gongji}"
POSTGRES_USER="${POSTGRES_USER:-gongji}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-gongji-password}"
PGDATA="${PGDATA:-/var/lib/postgresql/data}"

mkdir -p "$PGDATA" /run/postgresql
chown -R postgres:postgres "$PGDATA" /run/postgresql
chmod 700 "$PGDATA"

if [ ! -s "$PGDATA/PG_VERSION" ]; then
  su-exec postgres initdb -D "$PGDATA" --encoding=UTF8 --locale=C
  echo "listen_addresses = '*'" >> "$PGDATA/postgresql.conf"
  echo "host all all 0.0.0.0/0 md5" >> "$PGDATA/pg_hba.conf"

  su-exec postgres pg_ctl -D "$PGDATA" -w start
  su-exec postgres psql -v ON_ERROR_STOP=1 --username postgres <<-EOSQL
    CREATE USER "$POSTGRES_USER" WITH PASSWORD '$POSTGRES_PASSWORD';
    CREATE DATABASE "$POSTGRES_DB" OWNER "$POSTGRES_USER";
EOSQL
  su-exec postgres pg_ctl -D "$PGDATA" -m fast -w stop
fi

exec su-exec postgres postgres -D "$PGDATA"
