import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.database import SessionLocal
from db.models import Venue
from pipeline.extractor import extract_happy_hour
from pipeline.logger import log_scrape, save_happy_hour
from pipeline.scraper import scrape_venue

DELAY_SECONDS = 2


def _fetch_venues(db, venue_id, limit):
    query = db.query(Venue).filter(Venue.website.isnot(None), Venue.website != "")
    if venue_id:
        query = query.filter(Venue.id == venue_id)
    query = query.order_by(Venue.name)
    venues = query.all()
    if limit is not None:
        venues = venues[:limit]
    return venues


async def _process_venue(db, venue, index, total):
    label = f"[{index}/{total}] {venue.name}"

    try:
        result = await scrape_venue({"id": venue.id, "name": venue.name, "website": venue.website})
    except Exception as e:
        log_scrape(db, venue.id, success=False, pattern="none", error=str(e))
        print(f"{label} → pattern: none → extracted: no (scrape error)")
        return "failed"

    pattern = result["pattern"]
    log_scrape(db, venue.id, success=result["success"], pattern=pattern, error=None)

    if not result["success"] or not result["text"]:
        print(f"{label} → pattern: {pattern} → extracted: no (scrape failed)")
        return "failed"

    try:
        extraction = extract_happy_hour(result["text"], venue.name)
    except Exception as e:
        print(f"{label} → pattern: {pattern} → extracted: no (extract error: {e})")
        return "failed"

    if extraction is None:
        print(f"{label} → pattern: {pattern} → extracted: no")
        return "no_hh"

    save_happy_hour(db, venue.id, extraction, raw_text=result["text"])
    print(f"{label} → pattern: {pattern} → extracted: yes | confidence: {extraction['confidence']}")
    return "extracted"


async def run(venue_id=None, limit=None):
    db = SessionLocal()
    counts = {"extracted": 0, "no_hh": 0, "failed": 0}
    try:
        venues = _fetch_venues(db, venue_id, limit)
        total = len(venues)
        if total == 0:
            print("No venues matched.")
            return
        for index, venue in enumerate(venues, start=1):
            outcome = await _process_venue(db, venue, index, total)
            counts[outcome] += 1
            if index < total:
                await asyncio.sleep(DELAY_SECONDS)
    finally:
        db.close()

    print(
        f"\nDone: {counts['extracted']} extracted, "
        f"{counts['no_hh']} no happy hour found, {counts['failed']} failed"
    )


def main():
    parser = argparse.ArgumentParser(description="Run the Cincin scrape + extract pipeline")
    parser.add_argument("--limit", type=int, default=None, help="Max number of venues to process (default: all)")
    parser.add_argument("--venue-id", default=None, help="Process only this venue id")
    args = parser.parse_args()

    asyncio.run(run(venue_id=args.venue_id, limit=args.limit))


if __name__ == "__main__":
    main()
