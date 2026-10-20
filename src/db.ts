import pg from "pg";
import "dotenv/config";

export function createPool(connectionString = process.env.DATABASE_URL): pg.Pool {
  if (!connectionString) {
    throw new Error("DATABASE_URL is not set. Copy .env.example to .env.");
  }
  return new pg.Pool({ connectionString });
}
