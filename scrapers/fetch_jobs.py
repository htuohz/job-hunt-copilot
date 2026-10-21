#!/usr/bin/env python3
"""
Job Fetcher - Combined Gmail (via Claude API) + Adzuna API
Triggered by dashboard /api/ai-update endpoint.

Setup:
  pip3 install anthropic
  export ANTHROPIC_API_KEY="your_key"
  export ADZUNA_APP_ID="your_id"      # optional but recommended
  export ADZUNA_APP_KEY="your_key"    # optional but recommended
"""

import json
import os
import sys
import re
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime
from env_utils import load_local_env

try:
    import anthropic
except ImportError:
    anthropic = None

BASE_DIR  = Path(__file__).parent
load_local_env(BASE_DIR)
JOBS_FILE = BASE_DIR / "all_jobs.json"

# ─── Scoring ──────────────────────────────────────────────────────────────────
SCORE_KEYWORDS = {
    "serverless": 12, "aws lambda": 12, "prisma": 12, "lambda": 10,
    "esbuild": 10, "snowflake": 8, "api gateway": 8, "event-driven": 8,
    "node": 10, "node.js": 10, "typescript": 10, "react": 8,
    "aws": 7, "postgresql": 8, "postgres": 8,
    "ci/cd": 6, "infrastructure as code": 6, "microservices": 5,
    "rest api": 4, "graphql": 4, "docker": 4,
    "cloud-native": 6, "cloud native": 6, "data migration": 5,
    "senior": 5, "lead": 4, "principal": 4,
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
    "team lead": -3, "team leader": -3,
}

def score_job(title, desc=""):
    text = (title + " " + desc).lower()
    score, matched = 0, []
    for kw, pts in SCORE_KEYWORDS.items():
        if kw in text:
            score += pts; matched.append(kw)
    for kw, pts in PENALTY_KEYWORDS.items():
        if kw in text:
            score += pts; matched.append(f"⚠{kw.strip()}")
    return score, matched

def load_jobs():
    return json.loads(JOBS_FILE.read_text()) if JOBS_FILE.exists() else {}

def save_jobs(jobs):
    JOBS_FILE.write_text(json.dumps(jobs, indent=2))


# ─── Gmail via Claude API ─────────────────────────────────────────────────────
GMAIL_SYSTEM = """You are a job alert email parser. Search Gmail for job alert emails from the last 7 days from:
- LinkedIn: from:jobalerts-noreply@linkedin.com
- Indeed: from:alert@indeed.com OR from:donotreply@match.indeed.com
- Seek: subject:seek job alert

Extract ALL job listings. For each job return:
- title, company, location, description (max 300 chars), url (clean direct URL), published (YYYY-MM-DD), source (linkedin/indeed/seek)

For LinkedIn URLs extract the job ID and use: https://www.linkedin.com/jobs/view/JOB_ID/
For Indeed URLs use: https://au.indeed.com/viewjob?jk=JOB_KEY

Return ONLY a valid JSON array, no markdown, no explanation:
[{"title":"...","company":"...","location":"...","description":"...","url":"...","published":"...","source":"..."}]

If nothing found return: []"""

def fetch_gmail_jobs():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  Skipping Gmail: ANTHROPIC_API_KEY not set")
        return []
    if anthropic is None:
        print("  Skipping Gmail: pip3 install anthropic")
        return []

    print("  Calling Claude API to read Gmail...")
    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.beta.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4096,
            system=GMAIL_SYSTEM,
            messages=[{"role": "user", "content": "Search my Gmail for job alert emails from the last 7 days and extract all jobs as JSON."}],
            mcp_servers=[{"type": "url", "url": "https://gmail.mcp.claude.com/mcp", "name": "gmail-mcp"}],
            betas=["mcp-client-2025-04-04"],
        )

        raw = "".join(b.text for b in response.content if hasattr(b, "text")).strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        jobs = json.loads(raw.strip())
        print(f"  Gmail: found {len(jobs)} jobs")
        return jobs

    except Exception as e:
        print(f"  Gmail error: {e}")
        return []


# ─── Adzuna API ───────────────────────────────────────────────────────────────
ADZUNA_QUERIES = [
    "full stack developer",
    "software engineer typescript",
    "node.js engineer",
    "aws serverless developer",
    "react developer",
    "typescript developer",
    "senior full stack engineer",
    "backend developer node",
]

def fetch_adzuna_jobs():
    app_id  = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        print("  Skipping Adzuna: ADZUNA_APP_ID/KEY not set")
        return []

    results = []
    for query in ADZUNA_QUERIES:
        params = urllib.parse.urlencode({
            "app_id": app_id, "app_key": app_key,
            "results_per_page": 20, "what": query,
            "where": "Melbourne", "distance": 30,
            "salary_min": 100000, "sort_by": "date",
        })
        url = f"https://api.adzuna.com/v1/api/jobs/au/search/1?{params}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                for item in data.get("results", []):
                    job_url = item.get("redirect_url", "")
                    if not job_url:
                        continue
                    s_min = item.get("salary_min")
                    s_max = item.get("salary_max")
                    salary = f"${int(s_min):,}" if s_min else ""
                    if s_min and s_max:
                        salary += f" - ${int(s_max):,}"
                    results.append({
                        "title":       item.get("title", ""),
                        "company":     item.get("company", {}).get("display_name", ""),
                        "location":    item.get("location", {}).get("display_name", "Melbourne VIC"),
                        "description": item.get("description", "")[:300],
                        "salary":      salary,
                        "url":         job_url,
                        "published":   item.get("created", "")[:10] if item.get("created") else "",
                        "source":      "adzuna",
                    })
        except Exception as e:
            print(f"  Adzuna error ({query}): {e}")

    print(f"  Adzuna: found {len(results)} jobs")
    return results


# ─── Merge & Save ─────────────────────────────────────────────────────────────
def merge_jobs(raw_jobs):
    existing = load_jobs()
    added = 0

    for j in raw_jobs:
        url = j.get("url", "").strip()
        if not url:
            continue

        # Canonicalise LinkedIn URLs
        li_match = re.search(r'/jobs/view/(\d+)', url)
        if li_match:
            url = f"https://www.linkedin.com/jobs/view/{li_match.group(1)}/"

        if url in existing:
            continue

        score, matched = score_job(
            f"{j.get('title','')} {j.get('company','')}",
            j.get("description", "")
        )

        existing[url] = {
            "title":       j.get("title", ""),
            "company":     j.get("company", ""),
            "location":    j.get("location", "Melbourne VIC"),
            "url":         url,
            "description": j.get("description", "")[:350],
            "salary":      j.get("salary", ""),
            "published":   j.get("published", ""),
            "score":       score,
            "matched":     matched,
            "search":      f"{j.get('source','?').title()} Alert",
            "source":      j.get("source", "unknown"),
            "fetched_at":  datetime.now().isoformat(),
        }
        added += 1

    save_jobs(existing)
    return added, len(existing)


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("Fetching jobs...")

    all_raw = []

    # 1. Gmail via Claude API
    gmail_jobs = fetch_gmail_jobs()
    all_raw.extend(gmail_jobs)

    # 2. Adzuna API
    adzuna_jobs = fetch_adzuna_jobs()
    all_raw.extend(adzuna_jobs)

    # 3. Merge & score
    added, total = merge_jobs(all_raw)
    print(f"\nDone: added {added} new jobs, total {total}")

    # Print top 10
    jobs = load_jobs()
    sorted_jobs = sorted(jobs.values(), key=lambda x: x["score"], reverse=True)
    print("\nTop 10:")
    for j in sorted_jobs[:10]:
        salary = f" [{j['salary']}]" if j.get("salary") else ""
        print(f"  {j['score']:3d} | [{j.get('source','?'):8s}] {j['title']} @ {j.get('company','')}{salary}")

    return {"added": added, "total": total}


if __name__ == "__main__":
    result = main()
