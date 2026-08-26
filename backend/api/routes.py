from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.database import get_db

router = APIRouter()

METERS_PER_MILE = 1609.344
# All venues are in the Phoenix metro; happy_hours.start_time/end_time were
# extracted as local wall-clock times, so "now" must be Arizona time too.
PHOENIX_TZ = ZoneInfo("America/Phoenix")


class DealOut(BaseModel):
    deal_type: str
    days: list[str]
    start_time: str | None
    end_time: str | None
    deals: list[str]
    confidence: str


class VenueSearchResult(BaseModel):
    id: str
    name: str
    address: str
    lat: float
    lng: float
    google_rating: float | None
    distance_miles: float
    deal: DealOut


SEARCH_SQL = """
    SELECT
        v.id,
        v.name,
        v.address,
        v.lat,
        v.lng,
        v.google_rating,
        ST_Distance(v.location, ST_MakePoint(:lng, :lat)::geography) / :meters_per_mile AS distance_miles,
        h.deal_type,
        h.days,
        h.start_time,
        h.end_time,
        h.deals,
        h.confidence
    FROM venues v
    JOIN happy_hours h ON h.venue_id = v.id
    WHERE ST_DWithin(v.location, ST_MakePoint(:lng, :lat)::geography, :radius_meters)
      AND h.confidence IN ('high', 'medium')
      {deal_type_clause}
      {on_now_clause}
    ORDER BY distance_miles ASC
"""


@router.get("/api/venues/search", response_model=list[VenueSearchResult])
def search_venues(
    lat: float = Query(..., description="Search center latitude"),
    lng: float = Query(..., description="Search center longitude"),
    radius_miles: float = Query(5.0, gt=0, description="Search radius in miles"),
    on_now: bool = Query(False, description="Only include deals active right now"),
    deal_type: str | None = Query(
        None,
        description="Filter by deal_type, e.g. happy_hour, lunch_special, late_night, weekday_deal, early_bird",
    ),
    db: Session = Depends(get_db),
):
    params = {
        "lat": lat,
        "lng": lng,
        "radius_meters": radius_miles * METERS_PER_MILE,
        "meters_per_mile": METERS_PER_MILE,
    }

    deal_type_clause = ""
    if deal_type:
        deal_type_clause = "AND h.deal_type = :deal_type"
        params["deal_type"] = deal_type

    on_now_clause = ""
    if on_now:
        now = datetime.now(PHOENIX_TZ)
        on_now_clause = (
            "AND h.start_time IS NOT NULL AND h.end_time IS NOT NULL "
            "AND :current_day = ANY(h.days) "
            "AND :current_time BETWEEN h.start_time AND h.end_time"
        )
        params["current_day"] = now.strftime("%A")
        params["current_time"] = now.time()

    sql = SEARCH_SQL.format(deal_type_clause=deal_type_clause, on_now_clause=on_now_clause)
    rows = db.execute(text(sql), params).mappings().all()

    return [
        {
            "id": str(row["id"]),
            "name": row["name"],
            "address": row["address"],
            "lat": row["lat"],
            "lng": row["lng"],
            "google_rating": row["google_rating"],
            "distance_miles": round(row["distance_miles"], 2),
            "deal": {
                "deal_type": row["deal_type"],
                "days": row["days"],
                "start_time": row["start_time"].strftime("%H:%M") if row["start_time"] else None,
                "end_time": row["end_time"].strftime("%H:%M") if row["end_time"] else None,
                "deals": row["deals"],
                "confidence": row["confidence"],
            },
        }
        for row in rows
    ]
