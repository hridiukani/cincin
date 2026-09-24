import uuid
from contextlib import contextmanager
from datetime import datetime

from mcp.server.mcpserver import MCPServer
from sqlalchemy import text

from api.routes import METERS_PER_MILE, PHOENIX_TZ, SEARCH_SQL
from db.database import get_db
from db.models import HappyHour, Venue

mcp = MCPServer("cincin")

# get_db() is a plain generator with a single yield in a try/finally (written
# for FastAPI's Depends()) — that's exactly the shape contextmanager() wraps,
# so this reuses it as a real context manager instead of duplicating it.
db_session = contextmanager(get_db)


def _format_result(row) -> str:
    distance = f"{row['distance_miles']:.1f} mi"
    deal_type_label = row["deal_type"].replace("_", " ").title()
    days = ", ".join(row["days"]) if row["days"] else "days vary"
    if row["start_time"] and row["end_time"]:
        time_range = f"{row['start_time'].strftime('%H:%M')}-{row['end_time'].strftime('%H:%M')}"
    else:
        time_range = "hours vary"
    deals = ", ".join(row["deals"]) if row["deals"] else "no deal details listed"

    return (
        f"🍹 {row['name']} - {distance} away\n"
        f"   {deal_type_label} | {days} | {time_range}\n"
        f"   Deals: {deals}\n"
        f"   Address: {row['address']}"
    )


def _run_search(lat: float, lng: float, radius_miles: float, on_now: bool, deal_type: str | None) -> str:
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

    with db_session() as db:
        rows = db.execute(text(sql), params).mappings().all()

    if not rows:
        return f"No matching deals found within {radius_miles} miles."

    return "\n\n".join(_format_result(row) for row in rows)


@mcp.tool(description="Search for happy hours, lunch specials, and drink deals near a location in Phoenix AZ")
def search_happy_hours(
    lat: float,
    lng: float,
    radius_miles: float = 5.0,
    on_now: bool = False,
    deal_type: str | None = None,
) -> str:
    return _run_search(lat, lng, radius_miles, on_now, deal_type)


@mcp.tool(description="Get full details about a specific venue including all their deals and hours")
def get_venue_details(venue_id: str) -> str:
    try:
        parsed_id = uuid.UUID(venue_id)
    except ValueError:
        return f"'{venue_id}' is not a valid venue id."

    with db_session() as db:
        venue = db.query(Venue).filter(Venue.id == parsed_id).first()
        if venue is None:
            return f"No venue found with id {venue_id}."

        happy_hour = db.query(HappyHour).filter(HappyHour.venue_id == parsed_id).first()

    lines = [f"🍹 {venue.name}"]
    if happy_hour is not None:
        deal_type_label = happy_hour.deal_type.replace("_", " ").title()
        days = ", ".join(happy_hour.days) if happy_hour.days else "days vary"
        if happy_hour.start_time and happy_hour.end_time:
            time_range = f"{happy_hour.start_time.strftime('%H:%M')}-{happy_hour.end_time.strftime('%H:%M')}"
        else:
            time_range = "hours vary"
        deals = ", ".join(happy_hour.deals) if happy_hour.deals else "no deal details listed"
        lines.append(f"   {deal_type_label} | {days} | {time_range}")
        lines.append(f"   Deals: {deals}")
    else:
        lines.append("   No deals currently found for this venue.")

    lines.append(f"   Address: {venue.address}")
    if venue.phone:
        lines.append(f"   Phone: {venue.phone}")
    if venue.website:
        lines.append(f"   Website: {venue.website}")
    if venue.google_rating is not None:
        lines.append(f"   Rating: {venue.google_rating}")

    return "\n".join(lines)


@mcp.tool(
    description=(
        "Get all deals currently active right now near a location — "
        "perfect for finding somewhere to go immediately"
    )
)
def get_active_deals_now(lat: float, lng: float, radius_miles: float = 3.0) -> str:
    return _run_search(lat, lng, radius_miles, on_now=True, deal_type=None)


@mcp.tool(
    description="Find specific types of deals near a location, such as only happy hours or only lunch specials"
)
def get_deals_by_type(deal_type: str, lat: float, lng: float, radius_miles: float = 5.0) -> str:
    return _run_search(lat, lng, radius_miles, on_now=False, deal_type=deal_type)


if __name__ == "__main__":
    mcp.run()
