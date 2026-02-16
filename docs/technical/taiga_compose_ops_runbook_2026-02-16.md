# Taiga compose ops runbook (MVP baseline)

Ticket: #126  
Related: #119 (future unified compose stack)

## Scope and contract

This runbook targets the **current Taiga-only compose flow**:
- `docker-compose.taiga.yml`
- `.env.taiga`

When #119 lands, file names/service names may change, but the same operational concepts stay the same:
- backup
- restore
- retention
- health checks

## Security guardrail

- Keep **secrets out of git**.
- Commit only placeholder values in `.env.example`.
- Store real credentials in local `.env.taiga` or a secret manager.

## Required env placeholders

Example placeholders (do not commit real values):
- `TAIGA_DB_NAME=taiga`
- `TAIGA_DB_USER=taiga`
- `TAIGA_DB_PASSWORD=change_me`
- `TAIGA_PUBLIC_PORT=9000`

For API checks in this runbook, export a helper port variable:

```bash
export TAIGA_PORT="${TAIGA_PUBLIC_PORT:-9000}"
```

## Start / stop / restart

Start services:

```bash
docker compose -f docker-compose.taiga.yml --env-file .env.taiga up -d
```

Stop services:

```bash
docker compose -f docker-compose.taiga.yml --env-file .env.taiga down
```

Restart services:

```bash
docker compose -f docker-compose.taiga.yml --env-file .env.taiga down
docker compose -f docker-compose.taiga.yml --env-file .env.taiga up -d
```

Inspect running state:

```bash
docker compose -f docker-compose.taiga.yml --env-file .env.taiga ps
```

Inspect logs (compose-level and per-service):

```bash
docker compose -f docker-compose.taiga.yml --env-file .env.taiga logs --tail=200
docker compose -f docker-compose.taiga.yml --env-file .env.taiga logs --tail=200 taiga-back
docker compose -f docker-compose.taiga.yml --env-file .env.taiga logs --tail=200 taiga-front
```

## Health checks (mandatory)

1) Compose service status:

```bash
docker compose -f docker-compose.taiga.yml --env-file .env.taiga ps
```

2) Taiga API:

```bash
curl -f http://localhost:${TAIGA_PORT}/api/v1/
```

3) Postgres readiness:

```bash
docker compose -f docker-compose.taiga.yml --env-file .env.taiga exec taiga-db pg_isready
```

4) CyberneticAgents runtime logs (if running via unified stack or separate compose):

```bash
docker compose logs --tail=200 cyberagent
```

If any service is crash-looping, inspect service logs first and verify environment variables before restarting.

## Backup procedure (MVP docs-first)

Retention target: **7 daily backups**.

Create backup directory:

```bash
mkdir -p backups/taiga
```

Create timestamped Postgres dump:

```bash
TS="$(date -u +%Y%m%dT%H%M%SZ)"
docker compose -f docker-compose.taiga.yml --env-file .env.taiga exec -T taiga-db \
  pg_dump -U "${TAIGA_DB_USER}" "${TAIGA_DB_NAME}" > "backups/taiga/taiga_db_${TS}.sql"
```

Archive media/static volumes:

```bash
docker run --rm \
  -v cyberneticagents_taiga_media:/src_media \
  -v cyberneticagents_taiga_static:/src_static \
  -v "$(pwd)/backups/taiga:/backup" \
  alpine:3.20 sh -lc 'tar -czf "/backup/taiga_media_static_""'"${TS}""'.tgz" -C / src_media src_static'
```

Prune backups older than 7 days:

```bash
find backups/taiga -type f -name 'taiga_db_*.sql' -mtime +7 -delete
find backups/taiga -type f -name 'taiga_media_static_*.tgz' -mtime +7 -delete
```

## Restore procedure

Restore DB dump (replace dump filename):

```bash
DUMP_FILE="backups/taiga/taiga_db_YYYYMMDDTHHMMSSZ.sql"
cat "${DUMP_FILE}" | docker compose -f docker-compose.taiga.yml --env-file .env.taiga exec -T taiga-db \
  psql -U "${TAIGA_DB_USER}" "${TAIGA_DB_NAME}"
```

Restore media/static archive (replace archive filename):

```bash
ARCHIVE_FILE="backups/taiga/taiga_media_static_YYYYMMDDTHHMMSSZ.tgz"
docker run --rm \
  -v cyberneticagents_taiga_media:/dst_media \
  -v cyberneticagents_taiga_static:/dst_static \
  -v "$(pwd):/work" \
  alpine:3.20 sh -lc 'cd / && tar -xzf "/work/'"${ARCHIVE_FILE}"'"'
```

## Post-restore validation checklist

- Start stack and confirm all expected services are up.
- Run API check:
  - `curl -f http://localhost:${TAIGA_PORT}/api/v1/`
- Confirm DB readiness:
  - `docker compose -f docker-compose.taiga.yml --env-file .env.taiga exec taiga-db pg_isready`
- Spot-check media/static content in Taiga UI (avatars/uploads not missing).
- Check CyberneticAgents service logs for crash loops or recent traceback/ERROR lines.

## Failure-mode quick actions

- API check fails:
  - check `taiga-back` logs and DB readiness.
- Frontend unreachable:
  - verify `TAIGA_PUBLIC_PORT` binding and `taiga-front` container logs.
- DB auth errors:
  - re-check `TAIGA_DB_*` values in `.env.taiga`, then restart stack.
- Repeated crashes:
  - do not loop restarts blindly; capture logs and rollback to last known-good backup.
