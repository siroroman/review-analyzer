-- The industry is inferred from the downloaded Reviews, so a Company starts without one.
ALTER TABLE companies ALTER COLUMN industry DROP NOT NULL;
