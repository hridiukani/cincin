"use client";

import SearchBar from "./SearchBar";
import type { SearchOptions } from "@/lib/types";

interface HeroProps {
  onSearch: (lat: number, lng: number, options: SearchOptions) => void;
  isLoading: boolean;
}

// left/top are the resting positions (in %) the drink drifts out to.
// Every source image is drawn with the wrist pointing down-left, so hands
// resting on the right side need `flip: true` (mirrored horizontally) to
// read as reaching in from the right instead of from the center.
const HANDS = [
  { src: "/hands/hand-1.png", alt: "Hand holding a tall highball cocktail", left: 2, top: 2, size: 20, rot: 20 },
  { src: "/hands/hand-2.png", alt: "Hand holding a rocks glass with citrus", left: 80, top: 25, size: 21, rot: -20, flip: true },
  { src: "/hands/hand-3.png", alt: "Hand holding a coupe with a straw", left: -2, top: 70, size: 22, rot: -8 ,flip: true},
  { src: "/hands/hand-4.png", alt: "Hand holding a champagne flute", left: 79, top: 60, size: 22, rot: -10, flip: true },
  { src: "/hands/hand-5.png", alt: "Hand tilting a martini with a cherry", left: 30, top: -4, size: 18, rot: 30 },
  { src: "/hands/hand-6.png", alt: "Hand holding a beer mug", left: 41, top: 70, size: 19, rot: -10 },
  { src: "/hands/hand-7.png", alt: "Hand holding a glass of red wine", left: 15, top: 30, size: 16, rot: 16 },
  { src: "/hands/hand-8.png", alt: "Hand holding a margarita", left: 65, top: 2, size: 16, rot: -16, flip: true },
];

export default function Hero({ onSearch, isLoading }: HeroProps) {
  return (
    <main className="relative min-h-screen overflow-hidden bg-background">
      <div className="pointer-events-none absolute inset-0 grain-bg opacity-60" aria-hidden />

      <div className="pointer-events-none absolute inset-0">
        {HANDS.map((h) => {
          const flip = h.flip ? " scaleX(-1)" : "";
          return (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={h.alt}
              src={h.src}
              alt={h.alt}
              width={768}
              height={768}
              className="ink-art absolute select-none"
              style={{
                left: `${h.left}%`,
                top: `${h.top}%`,
                width: `${h.size}%`,
                transform: `rotate(${h.rot}deg)${flip}`,
              }}
            />
          );
        })}
      </div>

      <section className="relative z-10 mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center px-6 text-center">
        <div>
          <h1 className="mt-4 font-display italic text-7xl leading-none tracking-tight text-text-primary sm:text-8xl">
            cin cin
          </h1>
          <p className="mx-auto mt-5 max-w-md text-sm text-text-muted sm:text-base">
            HAPPY HOUR, FOUND
          </p>
        </div>

        <div className="mt-10 w-full">
          <SearchBar onSearch={onSearch} isLoading={isLoading} />
        </div>
      </section>
    </main>
  );
}
