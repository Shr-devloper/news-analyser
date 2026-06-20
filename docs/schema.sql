-- =====================================================================
-- AI News Intelligence Agent — reference PostgreSQL schema
-- This DDL mirrors the SQLAlchemy models in app/db/models.py.
-- The canonical source of truth is Alembic (`alembic upgrade head`);
-- this file is for documentation / manual inspection.
-- =====================================================================

CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    full_name       VARCHAR(255),
    hashed_password VARCHAR(255) NOT NULL,
    role            VARCHAR(32) DEFAULT 'user',
    is_active       BOOLEAN DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    -- Briefing delivery config (read by the timezone scheduler every 5 min):
    timezone         VARCHAR(64) DEFAULT 'Asia/Kolkata',
    delivery_hour    INTEGER DEFAULT 7,
    delivery_minute  INTEGER DEFAULT 0,
    interests        JSONB,
    briefing_enabled BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_preferences (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    interests     JSONB DEFAULT '[]',
    categories    JSONB DEFAULT '[]',
    email_enabled BOOLEAN DEFAULT TRUE,
    send_hour     INTEGER DEFAULT 7,
    timezone      VARCHAR(64) DEFAULT 'Asia/Kolkata',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE news_sources (
    id                SERIAL PRIMARY KEY,
    slug              VARCHAR(64) UNIQUE NOT NULL,
    name              VARCHAR(128) NOT NULL,
    connector         VARCHAR(32) DEFAULT 'rss',
    url               VARCHAR(1024) NOT NULL,
    category_hint     VARCHAR(64),
    country           VARCHAR(8),
    enabled           BOOLEAN DEFAULT TRUE,
    reliability_score DOUBLE PRECISION DEFAULT 1.0,
    success_count     INTEGER DEFAULT 0,
    failure_count     INTEGER DEFAULT 0,
    last_fetched_at   TIMESTAMPTZ,
    last_error        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE deduplicated_events (
    id              SERIAL PRIMARY KEY,
    canonical_title TEXT NOT NULL,
    canonical_url   TEXT,
    best_source_id  INTEGER REFERENCES news_sources(id),
    publisher_count INTEGER DEFAULT 1,
    combined_text   TEXT,
    centroid        JSONB,
    event_date      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_events_date ON deduplicated_events(event_date);

CREATE TABLE raw_articles (
    id           SERIAL PRIMARY KEY,
    source_id    INTEGER REFERENCES news_sources(id),
    title        TEXT NOT NULL,
    url          TEXT NOT NULL,
    url_hash     VARCHAR(64) NOT NULL,
    summary      TEXT,
    content      TEXT,
    author       VARCHAR(255),
    published_at TIMESTAMPTZ,
    language     VARCHAR(8) DEFAULT 'en',
    embedding    JSONB,
    event_id     INTEGER REFERENCES deduplicated_events(id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_raw_article_url UNIQUE (url_hash)
);
CREATE INDEX ix_raw_articles_published ON raw_articles(published_at);

CREATE TABLE article_categories (
    id         SERIAL PRIMARY KEY,
    event_id   INTEGER REFERENCES deduplicated_events(id) ON DELETE CASCADE,
    category   VARCHAR(64) NOT NULL,
    confidence DOUBLE PRECISION DEFAULT 0.0,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_article_categories_category ON article_categories(category);

CREATE TABLE rankings (
    id                 SERIAL PRIMARY KEY,
    event_id           INTEGER UNIQUE REFERENCES deduplicated_events(id) ON DELETE CASCADE,
    score              DOUBLE PRECISION DEFAULT 0.0,
    coverage_score     DOUBLE PRECISION DEFAULT 0.0,
    global_impact      DOUBLE PRECISION DEFAULT 0.0,
    economic_impact    DOUBLE PRECISION DEFAULT 0.0,
    political_impact   DOUBLE PRECISION DEFAULT 0.0,
    technology_impact  DOUBLE PRECISION DEFAULT 0.0,
    audience_relevance DOUBLE PRECISION DEFAULT 0.0,
    recency_score      DOUBLE PRECISION DEFAULT 0.0,
    rationale          TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE summaries (
    id             SERIAL PRIMARY KEY,
    event_id       INTEGER UNIQUE REFERENCES deduplicated_events(id) ON DELETE CASCADE,
    headline       TEXT NOT NULL,
    two_line       TEXT,
    detailed       TEXT,
    why_it_matters TEXT,
    key_takeaways  JSONB,
    future_impact  TEXT,
    model          VARCHAR(64),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE reports (
    id                 SERIAL PRIMARY KEY,
    user_id            INTEGER REFERENCES users(id) ON DELETE SET NULL,  -- per-user report (null = shared)
    report_uid         VARCHAR(64),                                       -- e.g. RPT-20260620-070003-ab12cd
    report_date        TIMESTAMPTZ NOT NULL,
    title              VARCHAR(255) NOT NULL,
    kind               VARCHAR(32) DEFAULT 'daily',
    executive_summary  TEXT,
    data               JSONB,
    html_path          VARCHAR(512),
    pdf_path           VARCHAR(512),
    markdown_path      VARCHAR(512),
    event_count        INTEGER DEFAULT 0,
    articles_processed INTEGER DEFAULT 0,
    sources_used       JSONB,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_reports_date ON reports(report_date);
CREATE INDEX ix_reports_user_id ON reports(user_id);
CREATE INDEX ix_reports_report_uid ON reports(report_uid);

-- Story-cluster snapshots included in a report (decouples report from live data).
-- NOTE: deduplicated_events above IS the "story_clusters" concept referenced in docs.
CREATE TABLE report_articles (
    id         SERIAL PRIMARY KEY,
    report_id  INTEGER REFERENCES reports(id) ON DELETE CASCADE,
    event_id   INTEGER REFERENCES deduplicated_events(id) ON DELETE SET NULL,
    rank       INTEGER DEFAULT 0,
    score      DOUBLE PRECISION DEFAULT 0,
    section    VARCHAR(64),
    category   VARCHAR(64),
    headline   TEXT NOT NULL,
    url        TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_report_articles_report_id ON report_articles(report_id);

CREATE TABLE email_logs (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    report_id  INTEGER REFERENCES reports(id) ON DELETE SET NULL,
    recipient  VARCHAR(255) NOT NULL,
    subject    VARCHAR(512) NOT NULL,
    status     VARCHAR(32) DEFAULT 'pending',
    attempts   INTEGER DEFAULT 0,
    error      TEXT,
    sent_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Per-user, per-day delivery ledger — the dedupe guard for the scheduler.
CREATE TABLE email_delivery_logs (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER REFERENCES users(id) ON DELETE CASCADE,
    report_id     INTEGER REFERENCES reports(id) ON DELETE SET NULL,
    delivery_date DATE,                       -- the user's LOCAL date
    delivery_time VARCHAR(32),                -- local time string, e.g. "07:00 IST"
    status        VARCHAR(32) DEFAULT 'pending',  -- pending | sent | failed
    attempts      INTEGER DEFAULT 0,
    error         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_delivery_user_date UNIQUE (user_id, delivery_date)
);
CREATE INDEX ix_delivery_user_id ON email_delivery_logs(user_id);
CREATE INDEX ix_delivery_date ON email_delivery_logs(delivery_date);

CREATE TABLE audit_logs (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action     VARCHAR(128) NOT NULL,
    resource   VARCHAR(255),
    ip_address VARCHAR(64),
    detail     JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_action ON audit_logs(action);
