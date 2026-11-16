-- The industry a Run used, so its result stays the same when the Company's industry changes later.
ALTER TABLE runs ADD COLUMN industry text;
