#!/usr/bin/env python3
"""
AI Email Fetcher
Uses Claude API with Gmail MCP to read job alert emails and update all_jobs.json.

Setup:
  pip3 install anthropic
  Set ANTHROPIC_API_KEY environment variable

Usage:
  python3 fetch_emails.py
  Or triggered automatically from dashboard via /api/ai-update
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from env_utils import load_local_env

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip3 install anthropic")
    sys.exit(1)

BASE_DIR  = Path(__file__).parent
load_local_env(BASE_DIR)
JOBS_FILE = BASE_DIR / "all_jobs.json"

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


SYSTEM_PROMPT = """You are a job alert email parser. Your job is to:
1. Search Gmail for recent job alert emails from LinkedIn, Indeed, and Seek
2. Extract ALL job listings from those emails
3. Return them as a JSON array

Search for emails from these senders in the last 7 days:
- LinkedIn: from:jobalerts-noreply@linkedin.com
- Indeed: from:alert@indeed.com OR from:donotreply@match.indeed.com  
- Seek: subject:seek job alert

For each job found, extract:
- title: job title
- company: company name
- location: job location
- description: brief description or teaser (max 300 chars)
- url: the direct job application URL (clean URL without tracking params where possible)
- published: date posted (YYYY-MM-DD format)
- source: "linkedin", "indeed", or "seek"

Return ONLY a valid JSON array like this, with no other text:
[
  {
    "title": "Senior Software Engineer",
    "company": "Xero",
    "location": "Melbourne, VIC",
    "description": "Build scalable backend services using TypeScript and AWS",
    "url": "https://www.linkedin.com/jobs/view/1234567890/",
    "published": "2026-03-16",
    "source": "linkedin"
  }
]

If no jobs are found, return an empty array: []
Do not include any explanation or markdown, just the raw JSON array."""


def fetch_jobs_via_claude():
    """Use Claude API with Gmail MCP to fetch and parse job emails."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print("Calling Claude API to read Gmail job alerts...")

    response = client.beta.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": "Please search my Gmail for job alert emails from the last 7 days (LinkedIn, Indeed, Seek) and extract all job listings. Return them as a JSON array."
            }
        ],
        mcp_servers=[
            {
                "type": "url",
                "url": "https://gmail.mcp.claude.com/mcp",
                "name": "gmail-mcp"
            }
        ],
        betas=["mcp-client-2025-04-04"],
    )

    # Extract text response
    raw = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw += block.text

    # Parse JSON
    raw = raw.strip()
    # Strip markdown code blocks if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    jobs_list = json.loads(raw)
    print(f"Claude found {len(jobs_list)} jobs in emails")
    return jobs_list


def update_jobs_file(new_jobs):
    """Score and merge new jobs into all_jobs.json."""
    existing = json.loads(JOBS_FILE.read_text()) if JOBS_FILE.exists() else {}

    added = 0
    for j in new_jobs:
        url = j.get("url", "").strip()
        if not url or url in existing:
            continue

        # Extract LinkedIn job ID for canonical URL
        import re
        li_match = re.search(r'/jobs/view/(\d+)', url)
        if li_match:
            url = f"https://www.linkedin.com/jobs/view/{li_match.group(1)}/"
            j["url"] = url
            if url in existing:
                continue

        score, matched = score_job(
            f"{j.get('title','')} {j.get('company','')}",
            j.get("description", "")
        )

        existing[url] = {
            "title":       j.get("title", ""),
            "company":     j.get("company", ""),
            "location":    j.get("location", "Melbourne, VIC"),
            "url":         url,
            "description": j.get("description", "")[:350],
            "published":   j.get("published", ""),
            "score":       score,
            "matched":     matched,
            "search":      f"{j.get('source','?').title()} Alert",
            "source":      j.get("source", "unknown"),
            "fetched_at":  datetime.now().isoformat(),
        }
        added += 1

    JOBS_FILE.write_text(json.dumps(existing, indent=2))
    print(f"Added {added} new jobs. Total: {len(existing)}")
    return added, len(existing)


def main():
    new_jobs = fetch_jobs_via_claude()
    added, total = update_jobs_file(new_jobs)

    # Print top 10
    all_jobs = json.loads(JOBS_FILE.read_text())
    sorted_jobs = sorted(all_jobs.values(), key=lambda x: x["score"], reverse=True)
    print(f"\nTop 10 jobs:")
    for j in sorted_jobs[:10]:
        print(f"  {j['score']:3d} | [{j.get('source','?'):8s}] {j['title']} @ {j.get('company','')}")

    return {"added": added, "total": total}


if __name__ == "__main__":
    result = main()
    print(f"\nDone: {result}")
