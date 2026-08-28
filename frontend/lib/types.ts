export type DealType =
  | "happy_hour"
  | "lunch_special"
  | "late_night"
  | "weekday_deal"
  | "early_bird"
  | "other";

export interface Deal {
  deal_type: DealType;
  days: string[];
  start_time: string | null;
  end_time: string | null;
  deals: string[];
  confidence: "high" | "medium" | "low";
}

export interface Venue {
  id: string;
  name: string;
  address: string;
  lat: number;
  lng: number;
  google_rating: number | null;
  distance_miles: number;
  deal: Deal;
}

export interface SearchOptions {
  radius_miles: number;
  on_now: boolean;
  deal_type: string | null;
}
