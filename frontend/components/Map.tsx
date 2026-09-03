"use client";

import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import type { Venue } from "@/lib/types";
import { isLiveNow } from "@/lib/time";

interface MapProps {
  venues: Venue[];
  userLocation: { lat: number; lng: number } | null;
  selectedVenueId: string | null;
  onVenueSelect: (id: string) => void;
}

const PHOENIX_CENTER: [number, number] = [-112.074, 33.4484];

export default function Map({ venues, userLocation, selectedVenueId, onVenueSelect }: MapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markersRef = useRef<Record<string, { marker: mapboxgl.Marker; el: HTMLDivElement }>>({});
  const userMarkerRef = useRef<mapboxgl.Marker | null>(null);
  const onVenueSelectRef = useRef(onVenueSelect);
  onVenueSelectRef.current = onVenueSelect;

  // Markers added before the map's style finishes loading can be silently
  // dropped during Mapbox's internal load setup, so marker effects wait
  // for this before touching the map.
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !containerRef.current || mapRef.current) return;

    mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";

    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: "mapbox://styles/mapbox/dark-v11",
      center: userLocation ? [userLocation.lng, userLocation.lat] : PHOENIX_CENTER,
      zoom: 12,
    });
    map.addControl(new mapboxgl.NavigationControl(), "top-right");
    map.on("load", () => setMapReady(true));
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !userLocation) return;

    if (!userMarkerRef.current) {
      const el = document.createElement("div");
      el.className = "user-location-dot";
      userMarkerRef.current = new mapboxgl.Marker({ element: el })
        .setLngLat([userLocation.lng, userLocation.lat])
        .addTo(map);
    } else {
      userMarkerRef.current.setLngLat([userLocation.lng, userLocation.lat]);
    }

    map.flyTo({ center: [userLocation.lng, userLocation.lat], zoom: 13, essential: true });
  }, [userLocation, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const currentIds = new Set(venues.map((v) => v.id));
    for (const id of Object.keys(markersRef.current)) {
      if (!currentIds.has(id)) {
        markersRef.current[id].marker.remove();
        delete markersRef.current[id];
      }
    }

    venues.forEach((venue) => {
      const active = isLiveNow(venue.deal);
      const color = active ? "#46f385" : "#f99549";
      const size = active ? 18 : 14;

      let entry = markersRef.current[venue.id];
      if (!entry) {
        const el = document.createElement("div");
        el.style.cursor = "pointer";
        el.style.borderRadius = "9999px";
        el.style.transition = "transform 0.15s ease, box-shadow 0.15s ease";
        el.addEventListener("click", () => onVenueSelectRef.current(venue.id));

        const marker = new mapboxgl.Marker({ element: el })
          .setLngLat([venue.lng, venue.lat])
          .addTo(map);

        entry = { marker, el };
        markersRef.current[venue.id] = entry;
      } else {
        entry.marker.setLngLat([venue.lng, venue.lat]);
      }

      entry.el.title = venue.name;
      entry.el.style.width = `${size}px`;
      entry.el.style.height = `${size}px`;
      entry.el.style.backgroundColor = color;

      const isSelected = venue.id === selectedVenueId;
      entry.el.style.transform = isSelected ? "scale(1.3)" : "scale(1)";
      entry.el.style.boxShadow = isSelected ? "0 0 0 3px #ffffff" : "none";
      entry.el.style.zIndex = isSelected ? "10" : "1";
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [venues, selectedVenueId, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !selectedVenueId) return;
    const venue = venues.find((v) => v.id === selectedVenueId);
    if (!venue) return;
    map.flyTo({ center: [venue.lng, venue.lat], zoom: 15, essential: true, speed: 0.8 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedVenueId, mapReady]);

  return (
    <div
      ref={containerRef}
      style={{ height: "calc(100vh - 57px)" }}
      className="w-full bg-surface"
    />
  );
}
