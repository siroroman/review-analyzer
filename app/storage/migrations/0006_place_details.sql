-- Totals of a whole Place from its Source (rating, count, per star, business data). One row of JSON per Place,
-- replaced on every Run. No reviewer data and no Review text: do not add such fields.
ALTER TABLE places ADD COLUMN details jsonb;
