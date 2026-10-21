/** Integration test against a real Postgres. Set TEST_DATABASE_URL to run it. */
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import pg from "pg";
import { migrate } from "../src/migrate.ts";
import { listJobs, setJobStatus, upsertJob } from "../src/jobs/store.ts";

const url = process.env.TEST_DATABASE_URL;
const pool = url ? new pg.Pool({ connectionString: url }) : null;

before(async () => {
  if (!pool) return;
  await pool.query("DROP SCHEMA public CASCADE; CREATE SCHEMA public;");
  await migrate(pool);
});
after(async () => pool?.end());

test("re-importing a job updates it without duplicating or resetting status", { skip: !pool }, async () => {
  const job = {
    title: "Full Stack Developer",
    company: "Movember",
    location: "Richmond VIC",
    url: "https://au.indeed.com/viewjob?jk=abc&utm_source=x",
    salary: "$140,000 - $160,000",
    published: "2026-03-16",
    score: 31,
    source: "indeed",
  };
  assert.equal(await upsertJob(pool!, job), true);
  await pool!.query("UPDATE jobs SET status = 'hidden'");
  assert.equal(await upsertJob(pool!, { ...job, score: 40 }), false);

  const { rows } = await pool!.query("SELECT status, score, salary_min, salary_max, url FROM jobs");
  assert.equal(rows.length, 1);
  assert.deepEqual(rows[0], {
    status: "hidden",
    score: 40,
    salary_min: 140000,
    salary_max: 160000,
    url: "https://au.indeed.com/viewjob?jk=abc",
  });
});

test("migrate is idempotent", { skip: !pool }, async () => {
  assert.deepEqual(await migrate(pool!), []);
});

test("listJobs shows one row per role and hides filtered or dismissed jobs", { skip: !pool }, async () => {
  await pool!.query("TRUNCATE jobs, companies RESTART IDENTITY CASCADE");
  const base = { title: "Software Engineer", company: "Canva", location: "Melbourne VIC", source: "seek" };
  await upsertJob(pool!, { ...base, url: "https://seek.com.au/job/1", score: 20 });
  await upsertJob(pool!, { ...base, url: "https://linkedin.com/jobs/view/2", score: 30, source: "linkedin" });
  await upsertJob(pool!, { ...base, title: "Graduate Developer", url: "https://seek.com.au/job/3" });
  await upsertJob(pool!, { ...base, title: "Backend Engineer", url: "https://seek.com.au/job/4", score: 10 });

  const jobs = await listJobs(pool!);
  assert.deepEqual(
    jobs.map((j) => [j.title, j.source]),
    [
      ["Software Engineer", "linkedin"],
      ["Backend Engineer", "seek"],
    ],
  );

  assert.equal(await setJobStatus(pool!, jobs[1]!.id, "hidden"), true);
  assert.equal((await listJobs(pool!)).length, 1);
  assert.equal((await listJobs(pool!, { status: "hidden" }))[0]!.title, "Backend Engineer");
  assert.equal((await listJobs(pool!, { includeFiltered: true })).length, 2);
  assert.equal(await setJobStatus(pool!, 9999, "saved"), false);
});
