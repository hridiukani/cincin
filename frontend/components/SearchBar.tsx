"use client";

import { useState } from "react";
import type { SearchOptions } from "@/lib/types";

interface SearchBarProps {
  onSearch: (lat: number, lng: number, options: SearchOptions) => void;
  isLoading: boolean;
  userLocation?: { lat: number; lng: number } | null;
}

const RADIUS_OPTIONS = [1, 3, 5, 10];
const DEAL_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All" },
  { value: "happy_hour", label: "Happy Hour" },
  { value: "lunch_special", label: "Lunch Special" },
  { value: "late_night", label: "Late Night" },
  { value: "weekday_deal", label: "Weekday Deal" },
];

const PHOENIX_PROXIMITY = "-111.9281,33.4242";

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  );
}

const inputClasses =
  "bg-background border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary transition";

export default function SearchBar({ onSearch, isLoading, userLocation }: SearchBarProps) {
  const [address, setAddress] = useState("");
  const [geocoding, setGeocoding] = useState(false);
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [radiusMiles, setRadiusMiles] = useState(5);
  const [onNow, setOnNow] = useState(false);
  const [dealType, setDealType] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const options: SearchOptions = { radius_miles: radiusMiles, on_now: onNow, deal_type: dealType };

  function handleUseLocation() {
    setError(null);
    if (!navigator.geolocation) {
      setError("Geolocation isn't supported by your browser.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false);
        onSearch(position.coords.latitude, position.coords.longitude, options);
      },
      () => {
        setLocating(false);
        setError("Couldn't get your location. Try entering an address instead.");
      }
    );
  }

  async function handleAddressSearch(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!address.trim()) {
      // No new address typed: re-run the search with the updated filters
      // against wherever the last search was centered, instead of no-op'ing.
      if (userLocation) {
        onSearch(userLocation.lat, userLocation.lng, options);
      } else {
        setError("Enter an address, or use your location first.");
      }
      return;
    }

    setGeocoding(true);
    try {
      const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
      const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(
        address
      )}.json?access_token=${token}&country=us&limit=1&proximity=${PHOENIX_PROXIMITY}`;

      const response = await fetch(url);
      if (!response.ok) {
        setError("Address search is temporarily unavailable. Please try again shortly.");
        return;
      }
      const data = await response.json();
      const feature = data.features?.[0];
      if (!feature) {
        setError("Couldn't find that address. Try being more specific.");
        return;
      }
      const [lng, lat] = feature.center;
      onSearch(lat, lng, options);
    } catch {
      setError("Address search is temporarily unavailable. Please try again shortly.");
    } finally {
      setGeocoding(false);
    }
  }

  const busy = isLoading || geocoding || locating;

  return (
    <div className="bg-surface border border-border rounded-xl p-4 w-full max-w-3xl mx-auto">
      <div className="flex flex-col sm:flex-row gap-3 items-stretch">
        <button
          type="button"
          onClick={handleUseLocation}
          disabled={busy}
          className="flex items-center justify-center gap-2 bg-primary hover:bg-primary-hover disabled:opacity-60 text-background font-semibold rounded-lg px-4 py-2 text-sm whitespace-nowrap transition"
        >
          {locating && <Spinner />}
          Use my location
        </button>

        <div className="flex items-center text-text-muted text-sm px-1 sm:px-2 select-none">or</div>

        <form onSubmit={handleAddressSearch} className="flex flex-1 gap-2">
          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="Enter an address in Phoenix"
            className={`${inputClasses} flex-1 min-w-0`}
          />
          <button
            type="submit"
            disabled={busy}
            className="bg-background border border-border hover:border-primary disabled:opacity-60 text-text-primary rounded-lg px-4 py-2 text-sm transition"
          >
            {geocoding ? <Spinner /> : "Search"}
          </button>
        </form>
      </div>

      {error && <p className="text-red-400 text-sm mt-2">{error}</p>}

      <button
        type="button"
        onClick={() => setFiltersOpen((v) => !v)}
        className="md:hidden mt-3 text-sm text-text-muted"
      >
        Filters {filtersOpen ? "▴" : "▾"}
      </button>

      <div className={`${filtersOpen ? "flex" : "hidden"} md:flex flex-col sm:flex-row gap-3 mt-3 items-stretch sm:items-center`}>
        <select
          value={radiusMiles}
          onChange={(e) => setRadiusMiles(Number(e.target.value))}
          className={inputClasses}
        >
          {RADIUS_OPTIONS.map((r) => (
            <option key={r} value={r}>
              {r} mi
            </option>
          ))}
        </select>

        <label className="flex items-center gap-2 text-sm text-text-primary select-none cursor-pointer">
          <input
            type="checkbox"
            checked={onNow}
            onChange={(e) => setOnNow(e.target.checked)}
            className="accent-primary w-4 h-4"
          />
          On now
        </label>

        <select
          value={dealType ?? ""}
          onChange={(e) => setDealType(e.target.value || null)}
          className={inputClasses}
        >
          {DEAL_TYPE_OPTIONS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
