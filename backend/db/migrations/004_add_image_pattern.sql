-- Allow 'image_menu' as a detected scrape pattern (a menu shown only as an
-- image, extracted via Gemini vision instead of HTML/PDF text).
ALTER TABLE scrape_log DROP CONSTRAINT IF EXISTS scrape_log_pattern_detected_check;
ALTER TABLE scrape_log ADD CONSTRAINT scrape_log_pattern_detected_check
    CHECK (pattern_detected IN ('link', 'location_selector', 'pdf', 'inline', 'image_menu', 'none'));
