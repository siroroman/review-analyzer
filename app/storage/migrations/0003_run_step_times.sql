-- When a Run entered the classifying and analyzing steps: the Progress screen prices each step from them.
ALTER TABLE runs
    ADD COLUMN classifying_at timestamptz,
    ADD COLUMN analyzing_at   timestamptz;
