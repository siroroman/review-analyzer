-- The drops and rises of a Run, saved with its trend so a later read matches the Run's Insights.
CREATE TABLE run_changes (
    seq             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id          text NOT NULL REFERENCES runs (id),
    kind            text NOT NULL,
    source          text NOT NULL,
    period_start    date NOT NULL,
    delta           double precision NOT NULL,
    main_topic_key  text
);
CREATE INDEX run_changes_run ON run_changes (run_id, seq);
