-- Run once:  psql -U postgres -c "CREATE DATABASE annotation_db;"
--            psql -U postgres -d annotation_db -f schema.sql
CREATE TABLE annotators (
    id   SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE clips (
    id           SERIAL PRIMARY KEY,
    filename     TEXT UNIQUE NOT NULL,              -- prevents duplicate clips
    duration_sec NUMERIC(6,2) CHECK (duration_sec > 0),
    language     TEXT
);

CREATE TABLE annotations (
    id           SERIAL PRIMARY KEY,
    clip_id      INT NOT NULL REFERENCES clips(id) ON DELETE CASCADE,       -- foreign key
    annotator_id INT NOT NULL REFERENCES annotators(id),                    -- foreign key
    label        TEXT NOT NULL CHECK (label IN ('speech','music','noise','multimodal')),
    transcript   TEXT,
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','reviewed')),
    created_at   TIMESTAMP DEFAULT NOW()
);

-- Query optimization: speeds up filtering and joins
CREATE INDEX idx_ann_status ON annotations(status);
CREATE INDEX idx_ann_clip   ON annotations(clip_id);

INSERT INTO annotators(name) VALUES ('Devesh'), ('Reviewer');
