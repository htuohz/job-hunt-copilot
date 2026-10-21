import { existsSync } from "node:fs";
import path from "node:path";
import { config } from "dotenv";
import pg from "pg";

/** Loads the nearest .env walking up from the working directory, so the repo-root .env serves every package. */
function loadEnv(): void {
  for (let dir = process.cwd(); ; dir = path.dirname(dir)) {
    const file = path.join(dir, ".env");
    if (existsSync(file)) {
      config({ path: file, quiet: true });
      return;
    }
    if (dir === path.dirname(dir)) return;
  }
}

export function createPool(connectionString?: string): pg.Pool {
  if (!connectionString) {
    loadEnv();
    connectionString = process.env.DATABASE_URL;
  }
  if (!connectionString) {
    throw new Error("DATABASE_URL is not set. Copy .env.example to .env at the repo root.");
  }
  return new pg.Pool({ connectionString });
}
