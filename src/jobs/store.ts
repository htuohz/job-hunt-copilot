import type pg from "pg";
import { canonicalUrl, companyKey, dedupeKey, parseDate, parseSalary } from "./normalize.js";
import { hardFilter } from "./filter.js";

/** A job as the Python scrapers produce it (one entry of all_jobs.json). */
export interface ScrapedJob {
  title: string;
  company?: string;
  location?: string;
  url: string;
  description?: string;
  salary?: string;
  published?: string;
  score?: number;
  matched?: string[];
  source?: string;
  fetched_at?: string;
  archived?: boolean;
}

export type Queryable = Pick<pg.Pool, "query">;

async function upsertCompany(db: Queryable, name: string): Promise<number | null> {
  const key = companyKey(name);
  if (!key) return null;
  const { rows } = await db.query<{ id: number }>(
    `INSERT INTO companies (name, name_key) VALUES ($1, $2)
     ON CONFLICT (name_key) DO UPDATE SET name = companies.name
     RETURNING id`,
    [name.trim(), key],
  );
  return rows[0]!.id;
}

/**
 * Inserts a scraped job, or refreshes its scraped fields if the URL is already stored.
 * Never overwrites status, so a job the user hid stays hidden after the next scrape.
 * Returns true when the job is new.
 */
export async function upsertJob(db: Queryable, job: ScrapedJob): Promise<boolean> {
  const company = job.company?.trim() ?? "";
  const companyId = company ? await upsertCompany(db, company) : null;
  const salary = parseSalary(job.salary);
  const filter = hardFilter({
    title: job.title,
    description: job.description,
    location: job.location,
    salaryMax: salary.max,
  });

  const { rows } = await db.query<{ inserted: boolean }>(
    `INSERT INTO jobs (url, dedupe_key, title, company_id, location, description, salary_text,
                       salary_min, salary_max, source, published_on, first_seen_at, score, matched,
                       filter_pass, filter_reasons, status, raw)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, COALESCE($12::timestamptz, now()), $13, $14,
             $15, $16, $17, $18)
     ON CONFLICT (url) DO UPDATE SET
       title = EXCLUDED.title, location = EXCLUDED.location, description = EXCLUDED.description,
       salary_text = EXCLUDED.salary_text, salary_min = EXCLUDED.salary_min, salary_max = EXCLUDED.salary_max,
       score = EXCLUDED.score, matched = EXCLUDED.matched,
       filter_pass = EXCLUDED.filter_pass, filter_reasons = EXCLUDED.filter_reasons, raw = EXCLUDED.raw
     RETURNING (xmax = 0) AS inserted`,
    [
      canonicalUrl(job.url),
      dedupeKey(company, job.title),
      job.title.trim(),
      companyId,
      job.location ?? null,
      job.description ?? null,
      job.salary || null,
      salary.min,
      salary.max,
      job.source ?? "unknown",
      parseDate(job.published),
      job.fetched_at ?? null,
      job.score ?? 0,
      job.matched ?? [],
      filter.pass,
      filter.reasons,
      job.archived ? "archived" : "new",
      JSON.stringify(job),
    ],
  );
  return rows[0]!.inserted;
}
