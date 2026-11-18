-- Quality metrics database. Postgres runs this file once, when its data volume is first created.

-- One row per CI run (GitHub Actions workflow run).
CREATE TABLE ci_runs (
    run_id      bigint PRIMARY KEY,
    branch      text        NOT NULL,
    event       text        NOT NULL,  -- pull_request or push
    conclusion  text        NOT NULL,  -- success or failure
    commit_sha  text        NOT NULL,
    title       text        NOT NULL,
    started_at  timestamptz NOT NULL,
    finished_at timestamptz NOT NULL
);

-- One row per test per CI run, read from the JUnit XML reports the run uploaded.
CREATE TABLE test_results (
    run_id     bigint NOT NULL REFERENCES ci_runs (run_id),
    stage      text   NOT NULL,  -- which CI step produced it: fast, smoke or live
    test_id    text   NOT NULL,  -- module path :: test name
    outcome    text   NOT NULL,  -- passed, failed, error, skipped or xfailed
    duration_s double precision NOT NULL,
    message    text
);
CREATE INDEX test_results_run ON test_results (run_id);

-- The bug list. In a real team this table would be filled from Jira.
CREATE TABLE bugs (
    bug_id                text PRIMARY KEY,
    title                 text NOT NULL,
    component             text NOT NULL,
    severity              text NOT NULL,  -- Critical, High, Medium, Low
    priority              text NOT NULL,  -- P0 to P3
    status                text NOT NULL,  -- Open or Fixed
    found_by              text NOT NULL,
    escaped_to_production boolean NOT NULL,
    opened_on             date NOT NULL,
    fixed_on              date
);
