#!/usr/bin/env python3
"""
Seek Job Scraper
Fetches jobs from Seek RSS feeds, scores them by relevance, and emails a daily digest.
"""

import smtplib
import json
import os
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from env_utils import load_local_env

# ─── CONFIG ───────────────────────────────────────────────────────────────────

load_local_env(Path(__file__).parent)

EMAIL_SENDER   = os.environ.get("DIGEST_EMAIL", "")
EMAIL_RECEIVER = os.environ.get("DIGEST_EMAIL", "")
EMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")  # Set via environment variable

# Seen jobs cache (to avoid duplicate emails)
CACHE_FILE = Path(__file__).parent / "seen_jobs.json"

# ─── SEARCH QUERIES ───────────────────────────────────────────────────────────
# Each entry is a Seek RSS URL for a different search term
# Salary filter: $110k+ | Location: Melbourne

SEEK_SEARCHES = [
    ("Full Stack Developer",     "full stack developer"),
    ("Software Engineer TS",     "software engineer typescript"),
    ("Node.js Engineer",         "node.js engineer"),
    ("AWS Serverless",           "aws serverless developer"),
    ("React Developer",          "react developer"),
    ("Backend Node",             "backend developer node"),
    ("TypeScript Developer",     "typescript developer"),
    ("Senior Full Stack",        "senior full stack engineer"),
    ("Cloud Native",             "cloud native engineer"),
]

# ─── SCORING ──────────────────────────────────────────────────────────────────
# Tailored to my profile:
# Core: React, Node.js, TypeScript, AWS Lambda, Serverless, Prisma, PostgreSQL
# Rare skills (extra weight): Serverless, Lambda, Prisma, esbuild, Snowflake
# Targeting: senior roles, cloud-first, modern engineering teams in Melbourne
# Penalised: PHP, WordPress, React Native, .NET, Java-only, mobile-only

SCORE_KEYWORDS = {
    # my rare / high-value skills
    "serverless":            12,
    "aws lambda":            12,
    "prisma":                12,
    "lambda":                10,
    "esbuild":               10,
    "snowflake":              8,
    "api gateway":            8,
    "event-driven":           8,
    # Core stack
    "node":                  10,
    "node.js":               10,
    "typescript":            10,
    "react":                  8,
    "aws":                    7,
    "postgresql":             8,
    "postgres":               8,
    # Modern engineering practices
    "ci/cd":                  6,
    "infrastructure as code": 6,
    "microservices":          5,
    "rest api":               4,
    "graphql":                4,
    "docker":                 4,
    "cloud-native":           6,
    "cloud native":           6,
    "data migration":         5,
    # Seniority signals
    "senior":                 5,
    "lead":                   4,
    "principal":              4,
    "tech lead":              6,
    # Industry bonus
    "logistics":              4,
    "supply chain":           4,
    "fintech":                4,
    "saas":                   3,
    "scale-up":               3,
    "startup":                2,
    # Work arrangement
    "hybrid":                 3,
    "remote":                 3,
    "flexible":               2,
    "work from home":         2,
    # General
    "agile":                  2,
    "cloud":                  2,
}

# Keywords that reduce the score — roles/skills I do not want
PENALTY_KEYWORDS = {
    # Unwanted tech
    "php":                   -8,
    "wordpress":            -10,
    "react native":          -8,
    ".net":                  -6,
    "c#":                    -6,
    "java ":                 -6,
    "angular":               -5,
    "mobile developer":      -8,
    "ios developer":        -10,
    "android developer":    -10,
    "embedded":              -8,
    "sharepoint":           -10,
    "sap":                  -10,
    "mainframe":            -10,
    "cobol":                -10,
    # Unwanted job types
    "contract":             -10,
    "(contract)":           -10,
    "casual":                -8,
    "temporary":             -8,
    "fixed term":            -8,
    "fixed-term":            -8,
    "freelance":             -6,
    # Unwanted seniority
    "junior":                -5,
    "entry level":           -8,
    "entry-level":           -8,
    "graduate":              -6,
    # Management roles
    "team lead":             -3,
    "team leader":           -3,
}

def score_job(title: str, description: str) -> tuple[int, list[str]]:
    """Score a job based on keyword matches. Returns (score, matched_keywords)."""
    text = (title + " " + description).lower()
    score = 0
    matched = []

    for keyword, points in SCORE_KEYWORDS.items():
        if keyword in text:
            score += points
            matched.append(keyword)

    for keyword, points in PENALTY_KEYWORDS.items():
        if keyword in text:
            score += points
            matched.append(f"⚠{keyword.strip()}")

    return score, matched


# ─── FETCH JOBS ───────────────────────────────────────────────────────────────

import urllib.request
import urllib.parse

SEEK_SEARCH_API = "https://www.seek.com.au/api/chalice-search/v4/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-AU,en;q=0.9",
    "Referer": "https://www.seek.com.au/",
    "X-Seek-Site": "Candidate",
}

def seek_search(keywords: str) -> list[dict]:
    params = {
        "keywords": keywords,
        "where": "Melbourne VIC 3000",
        "page": "1",
        "pageSize": "20",
        "sortmode": "ListedDate",
    }
    url = SEEK_SEARCH_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("data", [])
    except Exception as e:
        print(f"  Seek API error for '{keywords}': {e}")
        return []

def load_seen_jobs() -> set:
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen_jobs(seen: set):
    with open(CACHE_FILE, "w") as f:
        json.dump(list(seen), f)

def fetch_jobs() -> list[dict]:
    seen = load_seen_jobs()
    jobs = {}

    for search_name, keywords in SEEK_SEARCHES:
        print(f"  Searching: {search_name}...")
        results = seek_search(keywords)
        for item in results:
            job_id = str(item.get("id", ""))
            if not job_id:
                continue
            job_url = f"https://www.seek.com.au/job/{job_id}"
            if job_url in seen or job_url in jobs:
                continue

            title    = item.get("title", "")
            company  = item.get("advertiser", {}).get("description", "")
            location = item.get("locationLabel", "Melbourne VIC")
            teaser   = item.get("teaser", "")
            salary   = item.get("salary", "")
            listed   = item.get("listingDate", "")[:10] if item.get("listingDate") else ""
            desc     = f"{teaser} {salary}".strip()
            score, matched = score_job(f"{title} {company}", desc)

            jobs[job_url] = {
                "title":       title,
                "company":     company,
                "location":    location,
                "url":         job_url,
                "description": desc[:350] + "..." if len(desc) > 350 else desc,
                "published":   listed,
                "score":       score,
                "matched":     matched,
                "search":      search_name,
                "source":      "seek",
                "fetched_at":  datetime.now().isoformat(),
            }

    new_seen = seen | set(jobs.keys())
    save_seen_jobs(new_seen)
    return sorted(jobs.values(), key=lambda x: x["score"], reverse=True)


# ─── EMAIL ────────────────────────────────────────────────────────────────────

def build_email_html(jobs: list[dict]) -> str:
    today = datetime.now().strftime("%A, %d %B %Y")
    count = len(jobs)

    if count == 0:
        body = "<p style='color:#666'>No new matching jobs found today. Check back tomorrow!</p>"
    else:
        cards = ""
        for job in jobs:
            score_color = "#16a34a" if job["score"] >= 30 else "#d97706" if job["score"] >= 15 else "#6b7280"
            tags = " ".join(
                f"<span style='background:#dbeafe;color:#1d4ed8;padding:2px 8px;border-radius:12px;font-size:12px;margin:2px;display:inline-block'>{k}</span>"
                for k in job["matched"][:8]
            )
            cards += f"""
            <div style='border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin-bottom:16px;background:#fff'>
                <div style='display:flex;justify-content:space-between;align-items:flex-start'>
                    <a href='{job["url"]}' style='font-size:16px;font-weight:600;color:#1d4ed8;text-decoration:none'>{job["title"]}</a>
                    <span style='color:{score_color};font-weight:700;font-size:14px;white-space:nowrap;margin-left:12px'>★ {job["score"]} pts</span>
                </div>
                <p style='color:#6b7280;font-size:12px;margin:4px 0 8px'>Found via: {job["search"]} · {job["published"]}</p>
                <p style='color:#374151;font-size:14px;margin:8px 0'>{job["description"]}</p>
                <div style='margin-top:8px'>{tags}</div>
                <a href='{job["url"]}' style='display:inline-block;margin-top:12px;padding:6px 16px;background:#1d4ed8;color:#fff;border-radius:6px;font-size:13px;text-decoration:none'>View Job →</a>
            </div>
            """
        body = cards

    return f"""
    <html><body style='font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;background:#f9fafb'>
        <div style='background:#1a1a2e;color:#fff;padding:24px;border-radius:8px;margin-bottom:24px'>
            <h1 style='margin:0;font-size:22px'>🔍 Daily Job Digest</h1>
            <p style='margin:8px 0 0;color:#94a3b8'>{today} · {count} new job{"s" if count != 1 else ""} found</p>
        </div>
        {body}
        <p style='color:#9ca3af;font-size:12px;text-align:center;margin-top:24px'>
            Jobs scored by keyword relevance · Only new jobs shown · Minimum salary $110k
        </p>
    </body></html>
    """

def send_email(jobs: list[dict]):
    if not EMAIL_PASSWORD:
        print("ERROR: GMAIL_APP_PASSWORD environment variable not set.")
        print("See setup instructions in README.")
        return

    today = datetime.now().strftime("%d %b %Y")
    subject = f"🔍 Seek Jobs – {len(jobs)} new match{'es' if len(jobs) != 1 else ''} · {today}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = EMAIL_RECEIVER
    msg.attach(MIMEText(build_email_html(jobs), "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
    print(f"Email sent: {len(jobs)} new jobs")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Fetching jobs...")
    jobs = fetch_jobs()
    print(f"Found {len(jobs)} new jobs")
    send_email(jobs)
