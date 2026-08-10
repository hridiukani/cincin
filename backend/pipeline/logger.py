from datetime import datetime, timezone

from db.database import get_db
from db.models import HappyHour, ScrapeLog

__all__ = ["log_scrape", "save_happy_hour", "get_db"]


def _parse_time(value):
    if value is None:
        return None
    return datetime.strptime(value, "%H:%M").time()


def log_scrape(db, venue_id, success, pattern, error=None):
    entry = ScrapeLog(
        venue_id=venue_id,
        scraped_at=datetime.now(timezone.utc),
        success=success,
        pattern_detected=pattern,
        error_message=error,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def save_happy_hour(db, venue_id, extraction_result, raw_text):
    now = datetime.now(timezone.utc)
    fields = {
        "days": extraction_result["days"],
        "start_time": _parse_time(extraction_result["start_time"]),
        "end_time": _parse_time(extraction_result["end_time"]),
        "deals": extraction_result["deals"],
        "confidence": extraction_result["confidence"],
        "source": extraction_result["source"],
        "raw_text": raw_text,
        "last_verified": now,
    }

    happy_hour = db.query(HappyHour).filter(HappyHour.venue_id == venue_id).first()
    if happy_hour is None:
        happy_hour = HappyHour(venue_id=venue_id, **fields)
        db.add(happy_hour)
    else:
        for key, value in fields.items():
            setattr(happy_hour, key, value)
        happy_hour.updated_at = now

    db.commit()
    db.refresh(happy_hour)
    return happy_hour
