# Chirp

A small Twitter-style microblog. Registered users post short messages (up to 280 characters) with an optional image to a shared board, and manage their display name, avatar and password.

| Layer    | Tech                                                                |
| -------- | ------------------------------------------------------------------- |
| Frontend | Node.js 22 + Express: serves the single-page app, proxies the API   |
| Backend  | Python 3.13 + FastAPI, SQLAlchemy 2, Alembic migrations             |
| Database | PostgreSQL 17                                                       |
| Runtime  | Docker Compose                                                      |

## Quick start

```bash
cp .env.example .env        # then set POSTGRES_PASSWORD and JWT_SECRET
docker compose up -d --build
```

Open http://localhost:8080. Interactive API docs are at http://localhost:8080/api/docs.

Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## Features

- **Registration**: first name, last name, age (13+), address, plus email, username and password. Name, age and address are private; only the display name, username and avatar are public.
- **Main board**: newest-first feed with "load more" pagination. Signed-in users can post text, an image, or both, and delete their own posts. Click a name to see that user's posts.
- **Profile management** (`/settings`): change display name, upload or remove avatar (cropped to a square), and change password. Changing the password signs out every other session.

## Architecture

```
browser ──► frontend (Express :3000, published on HTTP_PORT)
               ├─ /            static SPA (index.html, app.js, styles.css)
               └─ /api, /media ──► backend (FastAPI :8000) ──► db (Postgres)
                                        └─ media volume (uploaded images)
```

- Only the frontend is published. `db` and `backend` sit on an internal Docker network with no outside access.
- A one-off `migrate` service runs `alembic upgrade head` before the API starts.
- Data lives in two named volumes: `pgdata` (database) and `media` (images).

## Security

- Passwords are hashed with Argon2id.
- Sessions use a signed JWT in an `HttpOnly`, `SameSite=Lax` cookie, so it can't be read by page JavaScript. Each user has a token version that is bumped on password change, which revokes old sessions.
- CSRF: every state-changing API call must carry `X-Requested-With: fetch`, which a cross-site page can't send without a CORS preflight the API never approves.
- Uploaded images are checked (JPEG/PNG/WebP/GIF, max 5 MB, decompression-bomb guard), then re-encoded to WebP with random file names. This strips EXIF data such as GPS location and means the server never serves the client's raw bytes.
- A strict Content-Security-Policy and Helmet security headers are applied, and the frontend never uses `innerHTML` with user content.
- Login, registration, posting and uploads are rate-limited per IP.

## Configuration (`.env`)

| Variable            | Default | Notes                                                           |
| ------------------- | ------- | --------------------------------------------------------------- |
| `HTTP_PORT`         | 8080    | Host port for the site                                          |
| `POSTGRES_PASSWORD` | —       | Required                                                        |
| `JWT_SECRET`        | —       | Required, at least 32 characters                                |
| `COOKIE_SECURE`     | false   | **Set to `true` in production** (requires HTTPS)                |
| `TRUST_PROXY`       | false   | `true` only if a TLS terminator or load balancer is in front    |
| `MAX_UPLOAD_MB`     | 5       | Per-image limit                                                 |
| `WEB_CONCURRENCY`   | 2       | Uvicorn worker processes                                        |

## Going to production

1. Put a TLS-terminating reverse proxy (Caddy, nginx, Traefik or a cloud load balancer) in front of the frontend. Then set `COOKIE_SECURE=true` and `TRUST_PROXY=true`.
2. Back up the `pgdata` and `media` volumes, or point `media` at durable storage.
3. Rate-limit counters are kept in memory per worker, so the effective limit is roughly the configured limit × `WEB_CONCURRENCY`. For strict limits across several instances, give the limiter a shared Redis store (see `backend/app/ratelimit.py`).

## Inspecting the database

`scripts/db-inspect.sh` (Git Bash, macOS, Linux) and `scripts/db-inspect.ps1` (PowerShell) take the same commands. They run psql inside the `db` container, so you don't need a local Postgres client. Every command except `psql` runs in a **read-only** session, so you can't change data by accident.

| Command               | Shows                                                               |
| --------------------- | ------------------------------------------------------------------- |
| `summary`             | Row counts, recent activity, most active users, table sizes         |
| `users [limit]`       | Users, newest first (password hashes are never shown)               |
| `posts [limit]`       | Latest posts with author and image path                             |
| `user <username>`     | One user's full record and latest posts                             |
| `integrity`           | 12 data-quality checks; every result should be 0                    |
| `media`               | Image files missing from disk, or files nothing in the database uses |
| `sql "<query>"`       | Any ad-hoc read-only query                                          |
| `tables`              | Columns, indexes and constraints                                    |
| `psql`                | Interactive shell (writable, so be careful)                         |
| `all`                 | `summary` + `integrity` + `media`                                   |

```bash
./scripts/db-inspect.sh summary
./scripts/db-inspect.sh user alice
./scripts/db-inspect.sh sql "SELECT count(*) FROM posts WHERE image_path IS NOT NULL"
```

```powershell
.\scripts\db-inspect.ps1 posts 50
```

The SQL lives in `scripts/sql/*.sql`; add a file there to add a report. The `media` check exits with code 1 if any image file is missing, so it can run in CI or a cron job.

## Running the backend tests

The tests need a disposable database; they refuse to run without `TEST_DATABASE_URL`.

```bash
source .env
docker compose exec db psql -U "$POSTGRES_USER" -c "CREATE DATABASE chirp_test"
# Start on the default network so pip can reach PyPI, then join the internal network to reach the db.
docker run -d --name chirp-test \
  -e TEST_DATABASE_URL="postgresql+psycopg://$POSTGRES_USER:$POSTGRES_PASSWORD@db:5432/chirp_test" \
  chirp-backend:latest sleep 600
docker exec chirp-test pip install --user -q -r requirements-dev.txt
docker network connect chirp_internal chirp-test
docker exec chirp-test python -m pytest -q -p no:cacheprovider
docker rm -f chirp-test
```

## Project layout

```
backend/
  app/            FastAPI app: config, models, schemas, security, media, routers/
  alembic/        database migrations
  tests/          API tests (pytest)
frontend/
  server.js       Express server: static files, security headers, API proxy
  public/         single-page app (vanilla JS, no build step)
docker-compose.yml
```
