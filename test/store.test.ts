/** Integration test against a real Postgres. Set TEST_DATABASE_URL to run it. */
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import pg from "pg";
import { migrate } from "../src/migrate.js";
import { upsertJob } from "../src/jobs/store.js";

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
