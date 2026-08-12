-- Note: the originally-planned "rename has_happy_hour -> has_deal" step is a
-- no-op here. has_happy_hour was only ever a field in the extractor's JSON
-- output (used to decide whether to save a row); it was never a column in the
-- happy_hours table, so there is nothing to rename. The runner only saves rows
-- for venues that have a deal, so a stored has_deal column would be constant
-- true. We persist the useful part instead: the kind of deal.

ALTER TABLE happy_hours ADD COLUMN IF NOT EXISTS deal_type TEXT NOT NULL DEFAULT 'happy_hour';
