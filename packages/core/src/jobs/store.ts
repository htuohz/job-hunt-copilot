import type pg from "pg";
import { canonicalUrl, companyKey, dedupeKey, parseDate, parseSalary } from "./normalize.ts";
import { hardFilter } from "./filter.ts";

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

export const JOB_STATUSES = ["new", "saved", "hidden", "archived"] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];

export interface JobRow {
  id: number;
  title: string;
  company: string | null;
  location: string | null;
  url: string;
  salaryText: string | null;
  source: string;
  publishedOn: string | null;
  firstSeenAt: Date;
  score: number;
  matched: string[];
  filterPass: boolean;
  filterReasons: string[];
  status: JobStatus;
}

export interface ListJobsOptions {
  status?: JobStatus;
  /** Include jobs that failed the hard filter. Off by default. */
  includeFiltered?: boolean;
  limit?: number;
}

/** Jobs for review, best match first. One row per dedupe_key, so a role posted on several boards shows once. */
export async function listJobs(db: Queryable, opts: ListJobsOptions = {}): Promise<JobRow[]> {
  const { rows } = await db.query<JobRow>(
    `SELECT DISTINCT ON (j.dedupe_key)
            j.id, j.title, c.name AS company, j.location, j.url, j.salary_text AS "salaryText",
            j.source, to_char(j.published_on, 'YYYY-MM-DD') AS "publishedOn", j.first_seen_at AS "firstSeenAt",
            j.score, j.matched, j.filter_pass AS "filterPass", j.filter_reasons AS "filterReasons", j.status
     FROM jobs j LEFT JOIN companies c ON c.id = j.company_id
     WHERE j.status = $1 AND ($2 OR j.filter_pass)
     ORDER BY j.dedupe_key, j.score DESC, j.first_seen_at DESC`,
    [opts.status ?? "new", opts.includeFiltered ?? false],
  );
  rows.sort((a, b) => b.score - a.score || b.firstSeenAt.getTime() - a.firstSeenAt.getTime());
  return rows.slice(0, opts.limit ?? 200);
}

/** Moves a job between new, saved, hidden and archived. Returns false if the job does not exist. */
export async function setJobStatus(db: Queryable, id: number, status: JobStatus): Promise<boolean> {
  const { rowCount } = await db.query("UPDATE jobs SET status = $2 WHERE id = $1", [id, status]);
  return rowCount === 1;
}
