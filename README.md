# Job Hunt Copilot

A personal job-search platform. Scrapers collect roles from job boards and company career pages, this service stores and filters them in PostgreSQL, tracks applications, and (later) exposes the workflow to Claude through an MCP server.

## Status

Milestone 1 in progress: the database, deduplication, hard-requirement filtering and an import of the old `job-picks` data are done. Next: point the Python scrapers at the database and send a daily digest of new roles.

## Run it locally

```bash
cp .env.example .env
docker compose up -d          # Postgres 16 on localhost:5432
npm install
npm run db:migrate
npm run import:json -- ../job-picks/all_jobs.json
npm test                      # unit tests; set TEST_DATABASE_URL to also run the DB tests
```

## Layout

- `db/migrations/` – SQL schema: companies, jobs, applications, events, contacts
- `src/jobs/normalize.ts` – canonical URLs, cross-board dedupe keys, salary and date parsing
- `src/jobs/filter.ts` – hard requirements (Melbourne or AU-remote, permanent, IC level, salary floor)
- `src/jobs/store.ts` – upsert that refreshes scraped fields but never resets a status you set
- `src/scripts/` – CLI entry points for migrations and the JSON import
