#!/usr/bin/env python3
"""
LinkedIn Job Alert Parser
Reads LinkedIn job alert emails from Gmail and merges them into all_jobs.json
for display in the dashboard.

Setup: pip3 install google-auth google-auth-oauthlib google-api-python-client
Then run: python3 linkedin_parser.py
"""

import json
import re
import os
from pathlib import Path
from datetime import datetime

# ─── Try to import Gmail API libraries ────────────────────────────────────────
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    import base64
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

BASE_DIR  = Path(__file__).parent
JOBS_FILE = BASE_DIR / "all_jobs.json"
TOKEN_FILE = BASE_DIR / "gmail_token.json"
CREDS_FILE = BASE_DIR / "gmail_credentials.json"

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# ─── Scoring (same as seek_scraper.py) ────────────────────────────────────────
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
    "agile": 2, "cloud": 2,
}

PENALTY_KEYWORDS = {
    # Unwanted tech
    "php": -8, "wordpress": -10, "react native": -8,
    ".net": -6, "c#": -6, "java ": -6, "angular": -5,
    "mobile developer": -8, "ios developer": -10, "android developer": -10,
    "embedded": -8, "sharepoint": -10, "sap": -10, "mainframe": -10, "cobol": -10,
    # Unwanted job types
    "contract": -10, "(contract)": -10, "casual": -8, "temporary": -8,
    "fixed term": -8, "fixed-term": -8, "freelance": -6,
    # Unwanted seniority
    "junior": -5, "entry level": -8, "entry-level": -8, "graduate": -6,
    # Management roles — not a fit at this stage
    "team lead": -3, "team leader": -3,
}

def score_job(title, description=""):
    text = (title + " " + description).lower()
    score = 0
    matched = []
    for kw, pts in SCORE_KEYWORDS.items():
        if kw in text:
            score += pts
            matched.append(kw)
    for kw, pts in PENALTY_KEYWORDS.items():
        if kw in text:
            score += pts
            matched.append(f"⚠{kw.strip()}")
    return score, matched


# ─── Parse LinkedIn alert email body ──────────────────────────────────────────
def parse_linkedin_email(body):
    """
    Parse a LinkedIn job alert email body.
    Returns list of job dicts.

    Email format:
        Job Title
        Company Name
        Location
        [optional: "This company is actively hiring"]
        View job: https://www.linkedin.com/comm/jobs/view/JOBID/...
        ---------
    """
    jobs = []
    # Split on the separator line
    blocks = re.split(r'-{5,}', body)

    for block in blocks:
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        # Filter out noise lines
        lines = [l for l in lines if not l.startswith(('View job:', 'See all jobs', 'Job search',
                 'This email was', 'Learn why', 'You are receiving', 'Manage your',
                 'Unsubscribe', 'Help:', '©', 'LinkedIn and', 'New jobs match',
                 'Your job alert', 'http'))]

        # Extract URL
        url_match = re.search(r'View job:\s*(https://www\.linkedin\.com/comm/jobs/view/\d+/[^\s]+)', block)
        if not url_match:
            continue

        raw_url = url_match.group(1)
        # Clean to canonical job URL
        job_id_match = re.search(r'/jobs/view/(\d+)/', raw_url)
        if not job_id_match:
            continue
        job_id = job_id_match.group(1)
        clean_url = f"https://www.linkedin.com/jobs/view/{job_id}/"

        # Remove "actively hiring" noise
        lines = [l for l in lines if 'actively hiring' not in l.lower()]

        if len(lines) < 2:
            continue

        title   = lines[0] if len(lines) > 0 else "Unknown"
        company = lines[1] if len(lines) > 1 else "Unknown"
        location = lines[2] if len(lines) > 2 else "Melbourne, VIC"

        score, matched = score_job(title, company)

        jobs.append({
            "title":       title,
            "company":     company,
            "location":    location,
            "url":         clean_url,
            "description": f"{company} · {location}",
            "published":   "",
            "score":       score,
            "matched":     matched,
            "search":      "LinkedIn Alert",
            "source":      "linkedin",
            "fetched_at":  datetime.now().isoformat(),
        })

    return jobs


# ─── Gmail OAuth ───────────────────────────────────────────────────────────────
def get_gmail_service():
    if not GMAIL_AVAILABLE:
        print("ERROR: Gmail libraries not installed.")
        print("Run: pip3 install google-auth google-auth-oauthlib google-api-python-client")
        return None

    if not CREDS_FILE.exists():
        print(f"ERROR: {CREDS_FILE} not found.")
        print("See README for setup instructions.")
        return None

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


# ─── Main ──────────────────────────────────────────────────────────────────────
def fetch_linkedin_jobs(max_emails=50):
    """Fetch LinkedIn jobs from Gmail alerts. Returns dict of url -> job."""
    service = get_gmail_service()
    if not service:
        return {}

    existing = json.loads(JOBS_FILE.read_text()) if JOBS_FILE.exists() else {}
    new_jobs = {}

    print(f"Fetching up to {max_emails} LinkedIn alert emails...")

    results = service.users().messages().list(
        userId="me",
        q="from:jobalerts-noreply@linkedin.com",
        maxResults=max_emails
    ).execute()

    messages = results.get("messages", [])
    print(f"Found {len(messages)} LinkedIn alert emails")

    for msg_meta in messages:
        try:
            msg = service.users().messages().get(
                userId="me",
                id=msg_meta["id"],
                format="full"
            ).execute()

            # Decode body
            payload = msg.get("payload", {})
            body = ""
            if "body" in payload and payload["body"].get("data"):
                import base64
                body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
            elif "parts" in payload:
                for part in payload["parts"]:
                    if part.get("mimeType") == "text/plain" and part["body"].get("data"):
                        import base64
                        body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
                        break

            if not body:
                continue

            jobs = parse_linkedin_email(body)
            for job in jobs:
                if job["url"] not in existing and job["url"] not in new_jobs:
                    new_jobs[job["url"]] = job

        except Exception as e:
            print(f"Error processing email {msg_meta['id']}: {e}")

    # Merge into existing
    existing.update(new_jobs)
    JOBS_FILE.write_text(json.dumps(existing, indent=2))
    print(f"Added {len(new_jobs)} new LinkedIn jobs (total: {len(existing)})")
    return existing


if __name__ == "__main__":
    fetch_linkedin_jobs()
