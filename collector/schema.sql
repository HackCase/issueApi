CREATE TABLE IF NOT EXISTS repos (
    id           BIGINT PRIMARY KEY,
    name         TEXT NOT NULL,
    full_name    TEXT NOT NULL,
    archived     BOOLEAN DEFAULT FALSE,
    pushed_at    TIMESTAMPTZ,
    updated_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS issues (
    id            BIGINT PRIMARY KEY,
    repo_id       BIGINT REFERENCES repos(id),
    number        INT NOT NULL,
    title         TEXT,
    state         TEXT NOT NULL,
    author        TEXT,
    assignee      TEXT,
    labels        TEXT[] DEFAULT '{}',
    comments      INT DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL,
    closed_at     TIMESTAMPTZ,
    updated_at    TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_issues_repo    ON issues(repo_id);
CREATE INDEX IF NOT EXISTS idx_issues_created ON issues(created_at);
CREATE INDEX IF NOT EXISTS idx_issues_closed  ON issues(closed_at);

CREATE TABLE IF NOT EXISTS pull_requests (
    id                BIGINT PRIMARY KEY,
    repo_id           BIGINT REFERENCES repos(id),
    number            INT NOT NULL,
    title             TEXT,
    state             TEXT NOT NULL,
    author            TEXT,
    draft             BOOLEAN DEFAULT FALSE,
    additions         INT,
    deletions         INT,
    changed_files     INT,
    review_comments   INT,
    created_at        TIMESTAMPTZ NOT NULL,
    first_review_at   TIMESTAMPTZ,
    merged_at         TIMESTAMPTZ,
    closed_at         TIMESTAMPTZ,
    updated_at        TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pr_repo    ON pull_requests(repo_id);
CREATE INDEX IF NOT EXISTS idx_pr_created ON pull_requests(created_at);

CREATE TABLE IF NOT EXISTS sync_state (
    resource   TEXT PRIMARY KEY,
    last_sync  TIMESTAMPTZ NOT NULL
);