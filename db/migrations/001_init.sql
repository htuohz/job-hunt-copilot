-- Core schema: jobs found by the scrapers, and the applications made from them.

CREATE TABLE companies (
  id         serial PRIMARY KEY,
  name       text NOT NULL,
  -- Lower-cased, punctuation-stripped name used to match the same company across sources.
  name_key   text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE jobs (
  id            serial PRIMARY KEY,
  url           text NOT NULL UNIQUE,
  -- Same role posted on several boards shares a dedupe_key (company + normalised title).
  dedupe_key    text NOT NULL,
  title         text NOT NULL,
  company_id    integer REFERENCES companies(id),
  location      text,
  description   text,
  salary_text   text,
  salary_min    integer,
  salary_max    integer,
  source        text NOT NULL,
  published_on  date,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  score         integer NOT NULL DEFAULT 0,
  matched       text[] NOT NULL DEFAULT '{}',
  -- Result of the hard requirements check (location, permanence, level, salary floor).
  filter_pass    boolean NOT NULL DEFAULT true,
  filter_reasons text[] NOT NULL DEFAULT '{}',
  status        text NOT NULL DEFAULT 'new'
                CHECK (status IN ('new', 'saved', 'hidden', 'archived')),
  raw           jsonb
);
CREATE INDEX jobs_dedupe_key_idx ON jobs (dedupe_key);
CREATE INDEX jobs_first_seen_idx ON jobs (first_seen_at DESC);

CREATE TABLE applications (
  id         serial PRIMARY KEY,
  job_id     integer NOT NULL REFERENCES jobs(id),
  status     text NOT NULL DEFAULT 'applied'
             CHECK (status IN ('applied', 'interviewing', 'offer', 'rejected', 'withdrawn', 'ghosted')),
  channel    text,
  applied_at timestamptz NOT NULL DEFAULT now(),
  notes      text,
  UNIQUE (job_id)
);

-- Anything that happens to an application: emails, interviews, follow-ups.
CREATE TABLE events (
  id             serial PRIMARY KEY,
  application_id integer NOT NULL REFERENCES applications(id),
  kind           text NOT NULL,
  occurred_at    timestamptz NOT NULL,
  -- External id (e.g. Gmail message id) so re-syncing never duplicates an event.
  source_ref     text UNIQUE,
  payload        jsonb
);

CREATE TABLE contacts (
  id           serial PRIMARY KEY,
  name         text NOT NULL,
  company_id   integer REFERENCES companies(id),
  role         text,
  email        text,
  linkedin_url text,
  notes        text
);
