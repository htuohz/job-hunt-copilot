import { createPool } from "../db.ts";
import { migrate } from "../migrate.ts";

const pool = createPool();
try {
  const applied = await migrate(pool);
  console.log(applied.length ? `Applied: ${applied.join(", ")}` : "Database is up to date.");
} finally {
  await pool.end();
}
