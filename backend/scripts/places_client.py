import argparse
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

GOOGLE_PLACES_API_KEY = os.environ["GOOGLE_PLACES_API_KEY"]

SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.rating",
        "places.websiteUri",
        "places.internationalPhoneNumber",
        "nextPageToken",
    ]
)

PLACE_TYPES = ["bar", "restaurant"]
NEXT_PAGE_TOKEN_DELAY_SECONDS = 2


def _search_text_page(client: httpx.Client, lat: float, lng: float, radius: int, place_type: str, page_token: str | None = None) -> dict:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    body = {
        "textQuery": place_type,
        "includedType": place_type,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius,
            }
        },
    }
    if page_token:
        # A freshly issued nextPageToken isn't valid yet; Google requires
        # a short delay before it can be used.
        time.sleep(NEXT_PAGE_TOKEN_DELAY_SECONDS)
        body["pageToken"] = page_token

    response = client.post(SEARCH_TEXT_URL, headers=headers, json=body)
    response.raise_for_status()
    return response.json()


def _search_nearby(client: httpx.Client, lat: float, lng: float, radius: int, place_type: str) -> list[dict]:
    results = []
    page_token = None
    while True:
        data = _search_text_page(client, lat, lng, radius, place_type, page_token)
        results.extend(data.get("places", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            return results


def fetch_venues(lat: float, lng: float, radius: int) -> list[dict]:
    with httpx.Client(timeout=10.0) as client:
        places_by_id = {}
        for place_type in PLACE_TYPES:
            for place in _search_nearby(client, lat, lng, radius, place_type):
                places_by_id.setdefault(place["id"], place)

        venues = []
        for place_id, place in places_by_id.items():
            location = place.get("location", {})
            venues.append(
                {
                    "google_place_id": place_id,
                    "name": place.get("displayName", {}).get("text"),
                    "address": place.get("formattedAddress"),
                    "lat": location.get("latitude"),
                    "lng": location.get("longitude"),
                    "website": place.get("websiteUri"),
                    "phone": place.get("internationalPhoneNumber"),
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
