import Link from "next/link";
import { listJobs, type JobRow, type JobStatus } from "@jhc/core";
import { db } from "@/lib/db";
import { updateStatus } from "./actions";

export const dynamic = "force-dynamic";

const TABS: { status: JobStatus; label: string }[] = [
  { status: "new", label: "New" },
  { status: "saved", label: "Saved" },
  { status: "hidden", label: "Hidden" },
];

export default async function JobsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; all?: string }>;
}) {
  const params = await searchParams;
  const status = TABS.find((t) => t.status === params.status)?.status ?? "new";
  const includeFiltered = params.all === "1";
  const jobs = await listJobs(db(), { status, includeFiltered });

  return (
    <main>
      <header>
        <h1>Job Hunt Copilot</h1>
        <nav>
          {TABS.map((t) => (
            <Link key={t.status} href={`/?status=${t.status}`} aria-current={t.status === status ? "page" : undefined}>
              {t.label}
            </Link>
          ))}
          <Link href={`/?status=${status}${includeFiltered ? "" : "&all=1"}`} className="toggle">
            {includeFiltered ? "Hide filtered out" : "Show filtered out"}
          </Link>
        </nav>
      </header>

      <p className="count">{jobs.length} roles</p>
      {jobs.length === 0 ? (
        <p className="empty">Nothing here. Run the scrapers or import some jobs.</p>
      ) : (
        <ul className="jobs">
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
        </ul>
      )}
    </main>
  );
}

function JobCard({ job }: { job: JobRow }) {
  const actions = (["saved", "hidden", "new"] as const).filter((s) => s !== job.status);
  return (
    <li className={job.filterPass ? "job" : "job filtered"}>
      <div className="main">
        <a href={job.url} target="_blank" rel="noreferrer" className="title">
          {job.title}
        </a>
        <div className="meta">
          {[job.company, job.location, job.salaryText, job.source, job.publishedOn].filter(Boolean).join(" · ")}
        </div>
        {job.matched.length > 0 && <div className="tags">{job.matched.join(", ")}</div>}
        {!job.filterPass && <div className="reasons">Filtered out: {job.filterReasons.join("; ")}</div>}
      </div>
      <div className="side">
        <span className="score">{job.score}</span>
        {actions.map((s) => (
          <form key={s} action={updateStatus}>
            <input type="hidden" name="id" value={job.id} />
            <input type="hidden" name="status" value={s} />
            <button type="submit">{s === "saved" ? "Save" : s === "hidden" ? "Hide" : "Restore"}</button>
          </form>
        ))}
      </div>
    </li>
  );
}
