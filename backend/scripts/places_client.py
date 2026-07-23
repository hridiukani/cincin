import argparse
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

GOOGLE_PLACES_API_KEY = os.environ["GOOGLE_PLACES_API_KEY"]

NEARBY_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

PLACE_TYPES = ["bar", "restaurant"]
NEXT_PAGE_TOKEN_DELAY_SECONDS = 2


def _nearby_search_page(client: httpx.Client, lat: float, lng: float, radius: int, place_type: str, page_token: str | None = None) -> dict:
    params = {"key": GOOGLE_PLACES_API_KEY}
    if page_token:
        # A freshly issued next_page_token isn't valid yet; Google requires
        # a short delay before it can be used.
        time.sleep(NEXT_PAGE_TOKEN_DELAY_SECONDS)
        params["pagetoken"] = page_token
    else:
        params.update({"location": f"{lat},{lng}", "radius": radius, "type": place_type})

    response = client.get(NEARBY_SEARCH_URL, params=params)
    response.raise_for_status()
    data = response.json()

    if data["status"] not in ("OK", "ZERO_RESULTS"):
        raise RuntimeError(f"Places Nearby Search error: {data['status']} - {data.get('error_message', '')}")

    return data


def _search_nearby(client: httpx.Client, lat: float, lng: float, radius: int, place_type: str) -> list[dict]:
    results = []
    page_token = None
    while True:
        data = _nearby_search_page(client, lat, lng, radius, place_type, page_token)
        results.extend(data.get("results", []))
        page_token = data.get("next_page_token")
        if not page_token:
            return results


def _get_details(client: httpx.Client, place_id: str) -> dict:
    params = {
        "place_id": place_id,
        "fields": "website,formatted_phone_number",
        "key": GOOGLE_PLACES_API_KEY,
    }
    response = client.get(DETAILS_URL, params=params)
    response.raise_for_status()
    data = response.json()

    if data["status"] != "OK":
        return {}

    return data.get("result", {})


def fetch_venues(lat: float, lng: float, radius: int) -> list[dict]:
    with httpx.Client(timeout=10.0) as client:
        places_by_id = {}
        for place_type in PLACE_TYPES:
            for place in _search_nearby(client, lat, lng, radius, place_type):
                places_by_id.setdefault(place["place_id"], place)

        venues = []
        for place_id, place in places_by_id.items():
            details = _get_details(client, place_id)
            location = place.get("geometry", {}).get("location", {})
            venues.append(
                {
                    "google_place_id": place_id,
                    "name": place.get("name"),
                    "address": place.get("vicinity"),
                    "lat": location.get("lat"),
                    "lng": location.get("lng"),
                    "website": details.get("website"),
                    "phone": details.get("formatted_phone_number"),
                    "google_rating": place.get("rating"),
                }
            )

        return venues


def main():
    parser = argparse.ArgumentParser(description="Cincin Google Places client")
    parser.add_argument("--test", action="store_true", help="Run a test search around ASU Tempe")
    args = parser.parse_args()

    if args.test:
        venues = fetch_venues(lat=33.4242, lng=-111.9281, radius=1500)
        for venue in venues[:5]:
            print(venue)


if __name__ == "__main__":
    main()
