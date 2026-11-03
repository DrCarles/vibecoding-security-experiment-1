#!/usr/bin/env bash
# Inspect the Chirp database. Queries run inside the db container in a read-only
# session, so nothing here can modify data (except the interactive `psql` shell).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SQL_DIR="$ROOT/scripts/sql"
cd "$ROOT"

usage() {
  cat <<'EOF'
Usage: scripts/db-inspect.sh <command> [args]

  summary              Row counts, activity, most active users, table sizes
  users [limit]        List users, newest first (default 50)
  posts [limit]        List latest posts (default 20)
  user <username>      One user's full record and latest posts
  integrity            Data-quality checks (all results should be 0)
  media                Compare uploaded image files with database references
  sql "<query>"        Run an ad-hoc read-only query
  tables               Describe tables, columns, indexes and constraints
  psql                 Open an interactive psql shell (NOT read-only)
  all                  summary + integrity + media
EOF
}

# Run SQL from stdin with psql inside the db container, read-only.
run_psql() {
  docker compose exec -T -e PGOPTIONS='-c default_transaction_read_only=on' db \
    sh -c 'psql -X -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off -P null=NULL "$@" -f -' psql "$@"
}

run_file() {
  local file="$SQL_DIR/$1.sql"
  shift
  run_psql "$@" < "$file"
}

positive_int() {
  [[ "$1" =~ ^[1-9][0-9]*$ ]] || { echo "Limit must be a positive number, got '$1'" >&2; exit 2; }
}

cmd="${1:-help}"
shift || true

case "$cmd" in
  summary)   run_file summary ;;
  users)     limit="${1:-50}"; positive_int "$limit"; run_file users -v "limit=$limit" ;;
  posts)     limit="${1:-20}"; positive_int "$limit"; run_file posts -v "limit=$limit" ;;
  user)
    [[ $# -ge 1 ]] || { echo "Usage: $0 user <username>" >&2; exit 2; }
    run_file user -v "username=$1" -v "limit=${2:-10}"
    ;;
  integrity) run_file integrity ;;
  media)     docker compose exec -T backend python - < "$ROOT/scripts/check_media.py" ;;
  sql)
    [[ $# -ge 1 ]] || { echo "Usage: $0 sql \"SELECT ...\"" >&2; exit 2; }
    printf '%s\n' "$1" | run_psql
    ;;
  tables)    printf '\\d+ users\n\\d+ posts\n' | run_psql ;;
  psql)      docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' ;;
  all)
    echo "######## SUMMARY";   run_file summary
    echo "######## INTEGRITY"; run_file integrity
    echo "######## MEDIA";     docker compose exec -T backend python - < "$ROOT/scripts/check_media.py"
    ;;
  help|-h|--help) usage ;;
  *) echo "Unknown command: $cmd" >&2; usage >&2; exit 2 ;;
esac
