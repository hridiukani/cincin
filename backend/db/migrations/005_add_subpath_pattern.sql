-- Allow 'subpath' as a detected scrape pattern: used when the homepage
-- itself yields nothing (pattern='none'), but a common subpath like
-- /happy-hour or /specials has the actual content.
ALTER TABLE scrape_log DROP CONSTRAINT IF EXISTS scrape_log_pattern_detected_check;
ALTER TABLE scrape_log ADD CONSTRAINT scrape_log_pattern_detected_check
    CHECK (pattern_detected IN ('link', 'location_selector', 'pdf', 'inline', 'image_menu', 'subpath', 'none'));
