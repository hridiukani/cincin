-- 1. Allow 'inline' as a detected scrape pattern.
ALTER TABLE scrape_log DROP CONSTRAINT IF EXISTS scrape_log_pattern_detected_check;
ALTER TABLE scrape_log ADD CONSTRAINT scrape_log_pattern_detected_check
    CHECK (pattern_detected IN ('link', 'location_selector', 'pdf', 'inline', 'none'));

-- 2. Low-confidence happy hours can be known to exist without exact times,
--    so start_time / end_time must be nullable.
ALTER TABLE happy_hours ALTER COLUMN start_time DROP NOT NULL;
ALTER TABLE happy_hours ALTER COLUMN end_time DROP NOT NULL;

-- 3. Persist the extractor's free-text notes field.
ALTER TABLE happy_hours ADD COLUMN IF NOT EXISTS notes TEXT;
