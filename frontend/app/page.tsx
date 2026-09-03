"use client";

import { useState } from "react";
import Header from "@/components/Header";
import Hero from "@/components/Hero";
import SearchBar from "@/components/SearchBar";
import VenueCard from "@/components/VenueCard";
import Map from "@/components/Map";
import { searchVenues } from "@/lib/api";
import type { SearchOptions, Venue } from "@/lib/types";

type Phase = "idle" | "loading" | "results" | "error";

export default function Home() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [venues, setVenues] = useState<Venue[]>([]);
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [selectedVenueId, setSelectedVenueId] = useState<string | null>(null);

  async function handleSearch(lat: number, lng: number, options: SearchOptions) {
    setPhase("loading");
    setUserLocation({ lat, lng });
    try {
      const results = await searchVenues(lat, lng, options);
      setVenues(results);
      setSelectedVenueId(null);
      setPhase("results");
    } catch {
      setPhase("error");
    }
  }

  if (phase === "idle") {
    return <Hero onSearch={handleSearch} isLoading={false} />;
  }

  return (
    <main>
      <Header />
      <div className="px-4 py-4 border-b border-border bg-background sticky top-[57px] z-40">
        <SearchBar onSearch={handleSearch} isLoading={phase === "loading"} />
      </div>

      {phase === "loading" && (
        <div className="flex flex-col md:flex-row">
          <div className="w-full md:w-2/5 order-2 md:order-1 p-4 space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-40 rounded-xl bg-surface border border-border animate-skeleton" />
            ))}
          </div>
          <div
            className="w-full md:w-3/5 order-1 md:order-2 h-[40vh] md:h-auto bg-surface"
            style={{ minHeight: "40vh" }}
          />
        </div>
      )}

      {phase === "error" && (
        <div className="flex flex-col items-center justify-center text-center py-24 gap-2 px-4">
          <span className="text-3xl">⚠️</span>
          <p className="text-text-muted">Something went wrong fetching deals. Please try again.</p>
        </div>
      )}

      {phase === "results" && (
        <div className="flex flex-col md:flex-row">
          <div className="w-full md:w-2/5 order-2 md:order-1">
            <div className="p-4">
              {venues.length === 0 ? (
                <div className="flex flex-col items-center justify-center text-center py-16 gap-2">
                  <span className="text-3xl">🍹</span>
                  <p className="text-text-muted">No deals found — try a larger radius</p>
                </div>
              ) : (
                <>
                  <p className="text-text-muted text-sm mb-3">
                    {venues.length} deal{venues.length === 1 ? "" : "s"} found near you
                  </p>
                  <div className="space-y-3">
                    {venues.map((venue) => (
                      <VenueCard
                        key={venue.id}
                        venue={venue}
                        isSelected={venue.id === selectedVenueId}
                        onClick={() => setSelectedVenueId(venue.id)}
                      />
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
          <div className="w-full md:w-3/5 order-1 md:order-2 h-[40vh] md:h-auto md:sticky md:top-[57px]">
            <Map
              venues={venues}
              userLocation={userLocation}
              selectedVenueId={selectedVenueId}
              onVenueSelect={setSelectedVenueId}
            />
          </div>
        </div>
      )}
    </main>
  );
}
