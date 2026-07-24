import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geoalchemy2.elements import WKTElement

from db.database import SessionLocal
from db.models import Venue
from scripts.places_client import fetch_venues

RADIUS_METERS = 3000

CITY_GRIDS = {
    "phoenix": [
        ("Tempe", 33.4255, -111.9400),
        ("Scottsdale", 33.4942, -111.9261),
        ("Chandler", 33.3062, -111.8413),
        ("Mesa", 33.4152, -111.8315),
        ("Downtown Phoenix", 33.4484, -112.0740),
        ("Glendale", 33.5387, -112.1860),
    ],
}


def collect_venues(city: str) -> list[dict]:
    grid = CITY_GRIDS.get(city)
    if grid is None:
        raise ValueError(f"No grid defined for city '{city}'. Available: {list(CITY_GRIDS)}")

    venues_by_place_id = {}
    for label, lat, lng in grid:
        print(f"Searching near {label} ({lat}, {lng})...")
        results = fetch_venues(lat=lat, lng=lng, radius=RADIUS_METERS)
        print(f"  found {len(results)} venues")
        for venue in results:
            venues_by_place_id.setdefault(venue["google_place_id"], venue)

    return list(venues_by_place_id.values())


def seed(city: str, dry_run: bool) -> None:
    venues = collect_venues(city)
    print(f"\n{len(venues)} venues found")

    if dry_run:
        for v in venues:
            print(v)
        print(f"\n{len(venues)} venues found, 0 new inserted, 0 skipped (dry run)")
        return

    db = SessionLocal()
    try:
        place_ids = [v["google_place_id"] for v in venues]
        existing_ids = {
            row.google_place_id
            for row in db.query(Venue.google_place_id).filter(Venue.google_place_id.in_(place_ids))
        }

        inserted = 0
        skipped = 0
        for v in venues:
            if v["google_place_id"] in existing_ids:
                skipped += 1
                continue
            db.add(
                Venue(
                    google_place_id=v["google_place_id"],
                    name=v["name"],
                    address=v["address"],
                    lat=v["lat"],
                    lng=v["lng"],
                    location=WKTElement(f"POINT({v['lng']} {v['lat']})", srid=4326),
                    website=v["website"],
                    phone=v["phone"],
                    google_rating=v["google_rating"],
                )
            )
            inserted += 1

        db.commit()
        print(f"\n{len(venues)} venues found, {inserted} new inserted, {skipped} skipped")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Seed Cincin venues from Google Places")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing to the database")
    parser.add_argument("--city", default="phoenix", help="City grid to seed (default: phoenix)")
    args = parser.parse_args()

    seed(city=args.city, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
