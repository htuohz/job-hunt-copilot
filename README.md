# Job Hunt Copilot

A personal job-search platform. Scrapers collect roles from job boards and alert emails, a shared TypeScript core stores, dedupes and filters them in PostgreSQL, and a Next.js app is where I review them. Later, the same core will be exposed to Claude through an MCP server.

## Layout

```
apps/web/        Next.js app: job list with save / hide, server actions for status changes
packages/core/   Shared TypeScript: Postgres access, dedupe, hard filter, job queries (+ tests)
scrapers/        Python scrapers that collect roles into scrapers/all_jobs.json
db/migrations/   SQL schema: companies, jobs, applications, events, contacts
```

## Run it locally

```bash
cp .env.example .env
docker compose up -d          # Postgres 16 on localhost:5432
npm install
npm run db:migrate
npm run import:scraped        # or: npm run import:json -- <path to all_jobs.json>
npm run dev                   # http://localhost:3000
```

Tests: `npm test`. Set `TEST_DATABASE_URL` to also run the database tests.

## Status

- Done: schema, cross-board dedupe, hard-requirement filter (Melbourne or AU-remote, permanent, IC level, salary floor), JSON import, job list UI.
- Next: scrapers write to Postgres directly, daily digest of new roles, application tracking pages, MCP server.
