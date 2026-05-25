#!/bin/sh
set -eu

printf '%s\n' \
  'https://mirrors.aliyun.com/alpine/v3.20/main' \
  'https://mirrors.aliyun.com/alpine/v3.20/community' \
  > /etc/apk/repositories
apk add --no-cache postgresql16 postgresql16-client su-exec

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
  su-exec postgres psql -v ON_ERROR_STOP=1 --username postgres -c "CREATE USER \"$POSTGRES_USER\" WITH PASSWORD '$POSTGRES_PASSWORD';"
  su-exec postgres psql -v ON_ERROR_STOP=1 --username postgres -c "CREATE DATABASE \"$POSTGRES_DB\" OWNER \"$POSTGRES_USER\";"
  su-exec postgres pg_ctl -D "$PGDATA" -m fast -w stop
fi

exec su-exec postgres postgres -D "$PGDATA"
