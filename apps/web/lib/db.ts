import "server-only";
import { createPool } from "@jhc/core";

type Pool = ReturnType<typeof createPool>;

// Reuse one pool across hot reloads in dev instead of opening a new one per edit.
const globalForDb = globalThis as unknown as { pool?: Pool };

export function db(): Pool {
  globalForDb.pool ??= createPool();
  return globalForDb.pool;
}
