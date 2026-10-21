#!/usr/bin/env python3
"""
Adzuna Job Fetcher
Fetches Melbourne tech jobs directly from Adzuna API.

Setup:
  1. Register at https://developer.adzuna.com/
  2. Get your app_id and app_key
  3. Set environment variables:
       export ADZUNA_APP_ID="your_app_id"
       export ADZUNA_APP_KEY="your_app_key"

Usage:
  python3 fetch_adzuna.py
  Or triggered automatically from dashboard via /api/ai-update
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime
from env_utils import load_local_env

BASE_DIR  = Path(__file__).parent
load_local_env(BASE_DIR)
JOBS_FILE = BASE_DIR / "all_jobs.json"

# ─── Search queries tailored for my profile ───────────────────────────
SEARCH_QUERIES = [
    "full stack developer",
    "software engineer typescript",
    "node.js engineer",
    "aws serverless developer",
    "react developer",
    "typescript developer",
    "senior full stack engineer",
    "backend developer node",
]

SCORE_KEYWORDS = {
    "serverless": 12, "aws lambda": 12, "prisma": 12, "lambda": 10,
    "esbuild": 10, "snowflake": 8, "api gateway": 8, "event-driven": 8,
    "node": 10, "node.js": 10, "typescript": 10, "react": 8,
    "aws": 7, "postgresql": 8, "postgres": 8,
    "ci/cd": 6, "infrastructure as code": 6, "microservices": 5,
    "rest api": 4, "graphql": 4, "docker": 4,
    "cloud-native": 6, "cloud native": 6, "data migration": 5,
    "senior": 5, "lead": 4, "principal": 4, "tech lead": 6,
    "logistics": 4, "supply chain": 4, "fintech": 4,
    "saas": 3, "scale-up": 3, "startup": 2,
    "hybrid": 3, "remote": 3, "flexible": 2, "work from home": 2,
    "next.js": 6, "nextjs": 6, "agile": 2, "cloud": 2,
    "devops": 4, "github actions": 5, "kubernetes": 4,
}
PENALTY_KEYWORDS = {
    "php": -8, "wordpress": -10, "react native": -8,
    ".net": -6, "c#": -6, "java ": -6, "angular": -5,
    "mobile developer": -8, "ios developer": -10, "android developer": -10,
    "embedded": -8, "sharepoint": -10, "sap": -10, "mainframe": -10, "cobol": -10,
    "contract": -10, "(contract)": -10, "casual": -8, "temporary": -8,
    "fixed term": -8, "fixed-term": -8, "freelance": -6,
    "junior": -5, "entry level": -8, "entry-level": -8, "graduate": -6,
    # Management roles — not a fit at this stage
    "team lead": -3, "team leader": -3,
}

def score_job(title, desc=""):
    text = (title + " " + desc).lower()
    score, matched = 0, []
    for kw, pts in SCORE_KEYWORDS.items():
        if kw in text:
            score += pts
            matched.append(kw)
    for kw, pts in PENALTY_KEYWORDS.items():
        if kw in text:
            score += pts
            matched.append(f"⚠{kw.strip()}")
    return score, matched


def adzuna_search(app_id, app_key, keywords, page=1):
    """Search Adzuna API for Melbourne jobs."""
    params = urllib.parse.urlencode({
        "app_id":         app_id,
        "app_key":        app_key,
        "results_per_page": 20,
        "what":           keywords,
        "where":          "Melbourne",
        "distance":       30,
        "salary_min":     100000,
        "sort_by":        "date",
        "content-type":   "application/json",
    })
    url = f"https://api.adzuna.com/v1/api/jobs/au/search/{page}?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  Adzuna error ({keywords}): {e}")
        return {}


def fetch_all_jobs():
    app_id  = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")

    if not app_id or not app_key:
        print("ERROR: Set ADZUNA_APP_ID and ADZUNA_APP_KEY environment variables")
        print("Register at: https://developer.adzuna.com/")
        sys.exit(1)

    existing = json.loads(JOBS_FILE.read_text()) if JOBS_FILE.exists() else {}
    new_jobs = {}

    for query in SEARCH_QUERIES:
        print(f"  Searching: {query}...")
        data = adzuna_search(app_id, app_key, query)
        results = data.get("results", [])

        for item in results:
            job_id  = str(item.get("id", ""))
            job_url = item.get("redirect_url", "")
            if not job_url or job_url in existing or job_url in new_jobs:
                continue

            title       = item.get("title", "")
            company     = item.get("company", {}).get("display_name", "")
            location    = item.get("location", {}).get("display_name", "Melbourne VIC")
            description = item.get("description", "")[:350]
            salary_min  = item.get("salary_min")
            salary_max  = item.get("salary_max")
            salary_str  = ""
            if salary_min:
                salary_str = f"${int(salary_min):,}"
                if salary_max:
                    salary_str += f" - ${int(salary_max):,}"

            created = item.get("created", "")[:10] if item.get("created") else ""

            score, matched = score_job(f"{title} {company}", description)

            new_jobs[job_url] = {
                "title":       title,
                "company":     company,
                "location":    location,
                "url":         job_url,
                "description": description,
                "salary":      salary_str,
                "published":   created,
                "score":       score,
                "matched":     matched,
                "search":      f"Adzuna: {query}",
                "source":      "adzuna",
                "fetched_at":  datetime.now().isoformat(),
            }

        print(f"    → {len(results)} results, {sum(1 for u in new_jobs if new_jobs[u]['search'] == f'Adzuna: {query}')} new")

    existing.update(new_jobs)
    JOBS_FILE.write_text(json.dumps(existing, indent=2))

    added = len(new_jobs)
    total = len(existing)
    print(f"\nAdded {added} new Adzuna jobs. Total: {total}")

    # Print top 10
    sorted_jobs = sorted(existing.values(), key=lambda x: x["score"], reverse=True)
    print("\nTop 10 jobs:")
    for j in sorted_jobs[:10]:
        salary = f" [{j['salary']}]" if j.get("salary") else ""
        print(f"  {j['score']:3d} | [{j.get('source','?'):8s}] {j['title']} @ {j.get('company','')}{salary}")

    return {"added": added, "total": total}


if __name__ == "__main__":
    result = fetch_all_jobs()
    print(f"\nDone: {result}")
