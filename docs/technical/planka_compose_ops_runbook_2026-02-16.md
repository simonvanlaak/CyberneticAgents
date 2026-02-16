# Planka compose ops runbook (MVP baseline)

Ticket: #131

## Scope and contract

This runbook targets the current Planka compose flow:
- `docker-compose.planka.yml`
- `.env.planka` (from `.env.planka.example`)

This is intended for an **IP-only** deployment (no domain required).

## Required env placeholders

Initialize env file:

```bash
cp .env.planka.example .env.planka
```

Set in `.env.planka` (do not commit real values):
- `PLANKA_BASE_URL=http://<SERVER_IP>:3000`
- `PLANKA_SECRET_KEY=<long-random-string>`
- `PLANKA_DB_PASSWORD=<strong-password>`

Optional first admin seed:
- `PLANKA_DEFAULT_ADMIN_EMAIL`
- `PLANKA_DEFAULT_ADMIN_USERNAME`
- `PLANKA_DEFAULT_ADMIN_NAME`
- `PLANKA_DEFAULT_ADMIN_PASSWORD`

## Start / stop / restart

Start services:

```bash
docker compose -f docker-compose.planka.yml --env-file .env.planka up -d
```

Stop services:

```bash
docker compose -f docker-compose.planka.yml --env-file .env.planka down
```

Restart services:

```bash
docker compose -f docker-compose.planka.yml --env-file .env.planka down
docker compose -f docker-compose.planka.yml --env-file .env.planka up -d
```

Inspect state:

```bash
docker compose -f docker-compose.planka.yml --env-file .env.planka ps
```

Inspect logs:

```bash
docker compose -f docker-compose.planka.yml --env-file .env.planka logs --tail=200
docker compose -f docker-compose.planka.yml --env-file .env.planka logs --tail=200 planka
docker compose -f docker-compose.planka.yml --env-file .env.planka logs --tail=200 planka-db
```

## Health checks

1) DB readiness:

```bash
docker compose -f docker-compose.planka.yml --env-file .env.planka exec planka-db pg_isready -U "${PLANKA_DB_USER:-planka}" -d "${PLANKA_DB_NAME:-planka}"
```

2) HTTP:

```bash
curl -f "http://localhost:${PLANKA_PUBLIC_PORT:-3000}/" >/dev/null
```

## Backup procedure (MVP)

Retention target: **7 daily backups**.

Create backup directory:

```bash
mkdir -p backups/planka
TS="$(date -u +%Y%m%dT%H%M%SZ)"
```

Postgres dump:

```bash
docker compose -f docker-compose.planka.yml --env-file .env.planka exec -T planka-db \
  pg_dump -U "${PLANKA_DB_USER:-planka}" "${PLANKA_DB_NAME:-planka}" > "backups/planka/planka_db_${TS}.sql"
```

Archive planka data volume:

```bash
docker run --rm \
  -v cyberneticagents_planka_data:/src_data \
  -v "$(pwd)/backups/planka:/backup" \
  alpine:3.20 sh -lc 'tar -czf "/backup/planka_data_'"${TS}"'.tgz" -C / src_data'
```

Prune backups older than 7 days:

```bash
find backups/planka -type f -name 'planka_db_*.sql' -mtime +7 -delete
find backups/planka -type f -name 'planka_data_*.tgz' -mtime +7 -delete
```

## Restore procedure

Restore DB dump:

```bash
DUMP_FILE="backups/planka/planka_db_YYYYMMDDTHHMMSSZ.sql"
cat "${DUMP_FILE}" | docker compose -f docker-compose.planka.yml --env-file .env.planka exec -T planka-db \
  psql -U "${PLANKA_DB_USER:-planka}" "${PLANKA_DB_NAME:-planka}"
```

Restore data archive:

```bash
ARCHIVE_FILE="backups/planka/planka_data_YYYYMMDDTHHMMSSZ.tgz"
docker run --rm \
  -v cyberneticagents_planka_data:/dst_data \
  -v "$(pwd):/work" \
  alpine:3.20 sh -lc 'cd / && tar -xzf "/work/'"${ARCHIVE_FILE}"'"'
```
