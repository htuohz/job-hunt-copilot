# Scrapers

Python scrapers carried over from the old `job-picks` dashboard. Most of them merge what they find into `scrapers/all_jobs.json`, which the TypeScript side then loads into Postgres.

| Script | What it does | Extra packages |
|---|---|---|
| `fetch_adzuna.py` | Melbourne tech jobs from the Adzuna API | none |
| `fetch_jobs.py` | Job-alert emails via the Claude API, plus Adzuna | `anthropic` |
| `fetch_emails.py` | Job-alert emails via Claude and the Gmail MCP | `anthropic` |
| `linkedin_parser.py` | LinkedIn job-alert emails via the Gmail API | `google-api-python-client`, `google-auth-oauthlib` |
| `seek_scraper.py` | SEEK RSS feeds, scored and emailed as a daily digest | none |

The company career-page fetchers (Greenhouse, Lever, SmartRecruiters) still live inside the old dashboard and are not moved yet.

## Run

```bash
cp scrapers/.env.example scrapers/.env   # add your API keys
python3 scrapers/fetch_adzuna.py
npm run import:scraped                   # load scrapers/all_jobs.json into Postgres
```

Next step: have the scrapers write to Postgres directly so the JSON hop goes away.
