/**
 * One-off import of the old job-picks data: `npm run import:json -- ../job-picks/all_jobs.json`
 * Safe to re-run: jobs are matched by URL.
 */
import { readFile } from "node:fs/promises";
import { z } from "zod";
import { createPool } from "../db.ts";
import { upsertJob } from "../jobs/store.ts";

const ScrapedJobSchema = z.object({
  title: z.string(),
  company: z.string().optional(),
  location: z.string().optional(),
  url: z.string().min(1),
  description: z.string().optional(),
  salary: z.string().optional(),
  published: z.string().optional(),
  score: z.number().optional(),
  matched: z.array(z.string()).optional(),
  source: z.string().optional(),
  fetched_at: z.string().optional(),
  archived: z.boolean().optional(),
});

const file = process.argv[2];
if (!file) {
  console.error("Usage: npm run import:json -- <path to all_jobs.json>");
  process.exit(1);
}

const data = z.record(z.string(), z.unknown()).parse(JSON.parse(await readFile(file, "utf8")));
const pool = createPool();
let added = 0;
let skipped = 0;
try {
  for (const [key, value] of Object.entries(data)) {
    const parsed = ScrapedJobSchema.safeParse(value);
    if (!parsed.success) {
      skipped++;
      console.warn(`Skipping ${key}: ${parsed.error.issues[0]?.message}`);
      continue;
    }
    if (await upsertJob(pool, parsed.data)) added++;
  }
  const { rows } = await pool.query<{ total: string; passing: string }>(
    "SELECT count(*) AS total, count(*) FILTER (WHERE filter_pass) AS passing FROM jobs",
  );
  console.log(`Imported ${added} new jobs (${skipped} skipped). Total ${rows[0]!.total}, passing hard filters ${rows[0]!.passing}.`);
} finally {
  await pool.end();
}
