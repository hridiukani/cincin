-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS postgis;

-- venues: canonical bar/restaurant records seeded from Google Places
CREATE TABLE venues (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    google_place_id  TEXT UNIQUE NOT NULL,
    name             TEXT NOT NULL,
    address          TEXT NOT NULL,
    lat              DOUBLE PRECISION NOT NULL,
    lng              DOUBLE PRECISION NOT NULL,
    location         GEOGRAPHY(POINT, 4326) NOT NULL,
    website          TEXT,
    phone            TEXT,
    google_rating    DOUBLE PRECISION,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Spatial index for fast "near me" radius/distance queries
CREATE INDEX idx_venues_location ON venues USING GIST (location);

-- happy_hours: structured deal data extracted by the AI pipeline
CREATE TABLE happy_hours (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    venue_id       UUID NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    days           TEXT[] NOT NULL,
    start_time     TIME NOT NULL,
    end_time       TIME NOT NULL,
    deals          TEXT[] NOT NULL,
    confidence     TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    source         TEXT NOT NULL CHECK (source IN ('website', 'reviews', 'both')),
    raw_text       TEXT,
    last_verified  TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_happy_hours_venue_id ON happy_hours (venue_id);

-- scrape_log: audit trail of each scrape attempt for a venue
CREATE TABLE scrape_log (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    venue_id          UUID NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    scraped_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    success           BOOLEAN NOT NULL,
    pattern_detected  TEXT CHECK (pattern_detected IN ('link', 'location_selector', 'pdf', 'none')),
    error_message     TEXT
);

CREATE INDEX idx_scrape_log_venue_id ON scrape_log (venue_id);
