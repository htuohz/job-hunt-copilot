/** Pure helpers for turning scraped job records into consistent rows. */

const LINKEDIN_JOB = /linkedin\.com\/(?:comm\/)?jobs\/view\/(\d+)/;

/** One URL per posting, so the same LinkedIn job from two emails is stored once. */
export function canonicalUrl(url: string): string {
  const trimmed = url.trim();
  const li = LINKEDIN_JOB.exec(trimmed);
  if (li) return `https://www.linkedin.com/jobs/view/${li[1]}/`;
  try {
    const u = new URL(trimmed);
    for (const p of [...u.searchParams.keys()]) {
      if (p.startsWith("utm_")) u.searchParams.delete(p);
    }
    return u.toString();
  } catch {
    return trimmed;
  }
}

export function companyKey(name: string): string {
  return name
    .toLowerCase()
    .replace(/\b(pty|ltd|limited|inc|australia|group)\b/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

/** Same company + same role title => same job, even when posted on several boards. */
export function dedupeKey(company: string, title: string): string {
  const t = title
    .toLowerCase()
    .replace(/\(.*?\)/g, "")
    .replace(/\b(hybrid|remote|melbourne|vic)\b/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
  return `${companyKey(company)}|${t}`;
}

/** "$140,000 - $170,000" -> { min: 140000, max: 170000 }. Values under 1000 are read as "k". */
export function parseSalary(text: string | undefined | null): { min: number | null; max: number | null } {
  if (!text) return { min: null, max: null };
  const nums = [...text.replace(/,/g, "").matchAll(/\$?\s*(\d+(?:\.\d+)?)\s*(k)?/gi)]
    .map((m) => Number(m[1]) * (m[2] || Number(m[1]) < 1000 ? 1000 : 1))
    .filter((n) => n >= 20000 && n <= 1_000_000);
  if (nums.length === 0) return { min: null, max: null };
  return { min: Math.min(...nums), max: Math.max(...nums) };
}

/** Accepts "2026-03-16" or an ISO timestamp; anything else becomes null. */
export function parseDate(text: string | undefined | null): string | null {
  if (!text) return null;
  const m = /^(\d{4}-\d{2}-\d{2})/.exec(text.trim());
  return m ? m[1]! : null;
}
