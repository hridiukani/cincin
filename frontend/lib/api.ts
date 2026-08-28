import type { SearchOptions, Venue } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function searchVenues(
  lat: number,
  lng: number,
  options: SearchOptions
): Promise<Venue[]> {
  const params = new URLSearchParams({
    lat: String(lat),
    lng: String(lng),
    radius_miles: String(options.radius_miles),
    on_now: String(options.on_now),
  });
  if (options.deal_type) {
    params.set("deal_type", options.deal_type);
  }

  const response = await fetch(`${API_URL}/api/venues/search?${params.toString()}`);

  if (!response.ok) {
    throw new Error(`Search failed (${response.status})`);
  }

  return response.json();
}
