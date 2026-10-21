import { test } from "node:test";
import assert from "node:assert/strict";
import { hardFilter } from "../src/jobs/filter.ts";

test("a Melbourne full-stack role passes", () => {
  const r = hardFilter({ title: "Full Stack Engineer", location: "Richmond VIC", salaryMax: 150000 });
  assert.deepEqual(r, { pass: true, reasons: [] });
});

test("tech lead, contract and citizenship roles are rejected", () => {
  assert.equal(hardFilter({ title: "Tech Lead - Platform" }).pass, false);
  assert.equal(hardFilter({ title: "Software Engineer", description: "12-month contract role" }).pass, false);
  assert.equal(hardFilter({ title: "Developer", description: "Must hold Australian citizenship" }).pass, false);
});

test("the word contract inside a description does not reject a permanent role", () => {
  assert.equal(hardFilter({ title: "Software Engineer", description: "Migrate user-contract data to Postgres" }).pass, true);
});

test("salary only rejects when stated and below the floor", () => {
  assert.equal(hardFilter({ title: "Developer", salaryMax: 100000 }).pass, false);
  assert.equal(hardFilter({ title: "Developer", salaryMax: null }).pass, true);
});

test("roles outside Melbourne are rejected", () => {
  assert.equal(hardFilter({ title: "Developer", location: "Sydney NSW" }).pass, false);
});

test("remote counts only when it is open to Australia", () => {
  assert.equal(hardFilter({ title: "Developer", location: "Remote" }).pass, true);
  assert.equal(hardFilter({ title: "Developer", location: "Remote - Australia" }).pass, true);
  assert.equal(hardFilter({ title: "Developer", location: "Remote (LATAM)" }).pass, false);
  assert.equal(hardFilter({ title: "Developer", location: "Remote (Europe,  Poland)" }).pass, false);
});

test("any lead title is rejected", () => {
  assert.equal(hardFilter({ title: "Lead Backend Developer - Node.js", location: "Melbourne" }).pass, false);
});
