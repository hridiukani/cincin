import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func as sa_func

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.database import SessionLocal
from db.models import HappyHour, ScrapeLog, Venue
from pipeline.extractor import extract_happy_hour
from pipeline.logger import log_scrape, save_happy_hour
from pipeline.scraper import scrape_venue

DELAY_SECONDS = 4


def _fetch_venues(db, venue_id, limit, skip=False):
    query = db.query(Venue).filter(Venue.website.isnot(None), Venue.website != "")
    if venue_id:
        query = query.filter(Venue.id == venue_id)

    if skip:
        already_scraped = db.query(ScrapeLog.venue_id).distinct()
        eligible_count = query.count()
        query = query.filter(Venue.id.notin_(already_scraped))
        remaining_count = query.count()
        skipped_count = eligible_count - remaining_count
        print(f"Skipping {skipped_count} already-scraped venues, running {remaining_count} remaining")

    query = query.order_by(Venue.name)
    venues = query.all()
    if limit is not None:
        venues = venues[:limit]
    return venues


def _fetch_failed_venues(db, venue_id, limit):
    failed_ids = db.query(ScrapeLog.venue_id).filter(ScrapeLog.success.is_(False)).distinct()
    query = db.query(Venue).filter(Venue.id.in_(failed_ids))
    if venue_id:
        query = query.filter(Venue.id == venue_id)
    query = query.order_by(Venue.name)
    venues = query.all()
    if limit is not None:
        venues = venues[:limit]
    print(f"Retrying {len(venues)} previously failed venues")
    return venues


def _fetch_none_venues(db, venue_id, limit, since=None):
    # Scraped successfully at least once, but never produced a happy_hours row.
    successful_ids = db.query(ScrapeLog.venue_id).filter(ScrapeLog.success.is_(True)).distinct()
    has_deal_ids = db.query(HappyHour.venue_id).distinct()
    # Already tried the Gemini Vision path — a repeat run would just re-detect
    # the same image and get the same (non-)answer, so treat it as settled.
    image_menu_ids = db.query(ScrapeLog.venue_id).filter(ScrapeLog.pattern_detected == "image_menu").distinct()

    # Most recent scrape per venue. Ordering by this ascending — instead of
    # by name — is what makes daily batches actually progress: once a venue
    # is scraped today its "last scraped" moves to today, sinking it to the
    # bottom of tomorrow's queue so the next batch naturally picks up where
    # today's left off.
    last_scraped = (
        db.query(ScrapeLog.venue_id, sa_func.max(ScrapeLog.scraped_at).label("last_scraped_at"))
        .group_by(ScrapeLog.venue_id)
        .subquery()
    )

    query = (
        db.query(Venue)
        .join(last_scraped, Venue.id == last_scraped.c.venue_id)
        .filter(
            Venue.id.in_(successful_ids),
            Venue.id.notin_(has_deal_ids),
            Venue.id.notin_(image_menu_ids),
        )
    )
    if since is not None:
        query = query.filter(last_scraped.c.last_scraped_at < since)
    if venue_id:
        query = query.filter(Venue.id == venue_id)
    query = query.order_by(last_scraped.c.last_scraped_at.asc())
    venues = query.all()
    if limit is not None:
        venues = venues[:limit]
    print(f"Retrying {len(venues)} venues that scraped successfully but found no deal")
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
        extraction = extract_happy_hour(result["text"], venue.name, image_source=(pattern == "image_menu"))
    except Exception as e:
        print(f"{label} → pattern: {pattern} → extracted: no (extract error: {e})")
        return "failed"

    if extraction is None:
        print(f"{label} → pattern: {pattern} → extracted: no")
        return "no_hh"

    save_happy_hour(db, venue.id, extraction, raw_text=result["text"])
    print(f"{label} → pattern: {pattern} → extracted: yes | confidence: {extraction['confidence']}")
    return "extracted"


async def run(venue_id=None, limit=None, skip=False, retry_failed=False, retry_none=False, since=None):
    db = SessionLocal()
    counts = {"extracted": 0, "no_hh": 0, "failed": 0}
    try:
        if retry_failed:
            venues = _fetch_failed_venues(db, venue_id, limit)
        elif retry_none:
            venues = _fetch_none_venues(db, venue_id, limit, since=since)
        else:
            venues = _fetch_venues(db, venue_id, limit, skip=skip)
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
    parser.add_argument(
        "--skip", action="store_true", help="Skip venues that already have a scrape_log row"
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Only run venues with a failed scrape_log row (ignores --skip for those venues)",
    )
    parser.add_argument(
        "--retry-none",
        action="store_true",
        help="Only run venues that scraped successfully but found no deal (e.g. to pick up image_menu detection)",
    )
    parser.add_argument(
        "--since",
        default=None,
        help=(
            "With --retry-none, only retry venues last scraped before this date "
            "(YYYY-MM-DD). Use it to run in daily batches without redoing venues "
            "from earlier batches."
        ),
    )
    args = parser.parse_args()

    if args.since and not args.retry_none:
        parser.error("--since only applies together with --retry-none")

    since = None
    if args.since:
        try:
            since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            parser.error(f"--since must be in YYYY-MM-DD format, got: {args.since}")

    asyncio.run(
        run(
            venue_id=args.venue_id,
            limit=args.limit,
            skip=args.skip,
            retry_failed=args.retry_failed,
            retry_none=args.retry_none,
            since=since,
        )
    )


if __name__ == "__main__":
    main()
