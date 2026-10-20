/**
 * Hard requirements: a job failing any of these is never worth reviewing,
 * whatever its keyword score.
 */
export interface HardFilterJob {
  title: string;
  description?: string | null;
  location?: string | null;
  salaryMax?: number | null;
}

export interface FilterResult {
  pass: boolean;
  reasons: string[];
}

const EXCLUDE_TITLE = [
  /\blead\b/i,
  /\bhead of\b/i,
  /\b(manager|director|principal|architect)\b/i,
  /\b(junior|graduate|intern)\b/i,
  /\bcontract(or)?\b/i,
];
const EXCLUDE_TEXT = [
  // Bare "contract" is too common in descriptions ("contract data"), so only match it as a role type.
  { re: /\b(\d+[- ]month contract|contract (role|position)|fixed[- ]term|temporary|casual)\b/i, reason: "not permanent" },
  { re: /\b(australian citizen(ship)?|baseline clearance|nv1|nv2|security clearance)\b/i, reason: "requires citizenship/clearance" },
];
const MELBOURNE = /\b(melbourne|cbd|richmond|south yarra|cremorne|docklands|southbank|vic|victoria)\b/i;
const REMOTE = /\bremote\b/i;
const AU_REGION = /\b(australia|au|anz|apac)\b/i;

/** Melbourne itself, or remote work that is open to Australia ("Remote (LATAM)" is not). */
function isMelbourneOrAuRemote(location: string): boolean {
  if (MELBOURNE.test(location)) return true;
  if (!REMOTE.test(location)) return false;
  const rest = location.replace(REMOTE, "").replace(/[()\s,-]/g, "");
  return rest === "" || AU_REGION.test(location);
}

export function hardFilter(job: HardFilterJob, minSalary = 120_000): FilterResult {
  const reasons: string[] = [];
  for (const re of EXCLUDE_TITLE) {
    if (re.test(job.title)) reasons.push(`title: ${re.source}`);
  }
  const text = `${job.title} ${job.description ?? ""}`;
  for (const { re, reason } of EXCLUDE_TEXT) {
    if (re.test(text)) reasons.push(reason);
  }
  if (job.location && !isMelbourneOrAuRemote(job.location)) reasons.push("outside Melbourne");
  // Only reject on salary when the ad states one; most ads don't.
  if (job.salaryMax != null && job.salaryMax < minSalary) reasons.push(`salary below ${minSalary}`);
  return { pass: reasons.length === 0, reasons };
}
