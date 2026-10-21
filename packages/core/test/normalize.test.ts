import { test } from "node:test";
import assert from "node:assert/strict";
import { canonicalUrl, dedupeKey, parseDate, parseSalary } from "../src/jobs/normalize.ts";

test("canonicalUrl collapses LinkedIn tracking URLs to one job URL", () => {
  assert.equal(
    canonicalUrl("https://www.linkedin.com/comm/jobs/view/4012345678/?trackingId=abc"),
    "https://www.linkedin.com/jobs/view/4012345678/",
  );
});

test("canonicalUrl drops utm params but keeps meaningful ones", () => {
  assert.equal(
    canonicalUrl("https://au.indeed.com/viewjob?jk=51c6536db5f696fc&utm_source=alert"),
    "https://au.indeed.com/viewjob?jk=51c6536db5f696fc",
  );
});

test("dedupeKey matches the same role across boards", () => {
  assert.equal(
    dedupeKey("Culture Amp Pty Ltd", "Senior Software Engineer (Hybrid)"),
    dedupeKey("Culture Amp", "Senior Software Engineer - Melbourne"),
  );
});

test("parseSalary reads ranges and k suffixes", () => {
  assert.deepEqual(parseSalary("$140,000 - $170,000"), { min: 140000, max: 170000 });
  assert.deepEqual(parseSalary("120k-140k + super"), { min: 120000, max: 140000 });
  assert.deepEqual(parseSalary(""), { min: null, max: null });
  assert.deepEqual(parseSalary("Competitive"), { min: null, max: null });
});

test("parseDate keeps only valid dates", () => {
  assert.equal(parseDate("2026-03-16T06:40:11"), "2026-03-16");
  assert.equal(parseDate("last week"), null);
});
