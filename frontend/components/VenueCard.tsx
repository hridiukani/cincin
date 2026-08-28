import type { Venue } from "@/lib/types";
import { formatTime12h, isLiveNow } from "@/lib/time";

interface VenueCardProps {
  venue: Venue;
  isSelected: boolean;
  onClick: () => void;
}

const DEAL_TYPE_STYLES: Record<string, { label: string; className: string }> = {
  happy_hour: { label: "Happy Hour", className: "bg-primary text-background" },
  lunch_special: { label: "Lunch Special", className: "bg-emerald-500 text-background" },
  late_night: { label: "Late Night", className: "bg-purple-500 text-white" },
  weekday_deal: { label: "Weekday Deal", className: "bg-deal text-white" },
  other: { label: "Deal", className: "bg-neutral-500 text-white" },
};

export default function VenueCard({ venue, isSelected, onClick }: VenueCardProps) {
  const dealStyle = DEAL_TYPE_STYLES[venue.deal.deal_type] ?? DEAL_TYPE_STYLES.other;
  const live = isLiveNow(venue.deal);
  const topDeals = venue.deal.deals.slice(0, 3);

  return (
    <div
      onClick={onClick}
      className={`bg-surface rounded-xl border cursor-pointer transition p-4 ${
        isSelected
          ? "border-l-[3px] border-l-primary border-t-border border-r-border border-b-border bg-white/[0.03]"
          : "border-border hover:brightness-125"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-bold text-text-primary text-base leading-snug">{venue.name}</h3>
        <span className="text-text-muted text-xs whitespace-nowrap shrink-0 mt-0.5">
          {venue.distance_miles} mi
        </span>
      </div>

      <div className="flex items-center gap-2 mt-2 flex-wrap">
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${dealStyle.className}`}>
          {dealStyle.label}
        </span>
        {live && (
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-live/20 text-live">
            ● Live now
          </span>
        )}
      </div>

      {venue.deal.days.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {venue.deal.days.map((day) => (
            <span
              key={day}
              className="text-[11px] text-text-muted bg-white/5 rounded px-1.5 py-0.5"
            >
              {day.slice(0, 3)}
            </span>
          ))}
        </div>
      )}

      <p className="text-primary text-sm font-medium mt-2">
        {venue.deal.start_time && venue.deal.end_time
          ? `${formatTime12h(venue.deal.start_time)} – ${formatTime12h(venue.deal.end_time)}`
          : <span className="text-text-muted font-normal">Hours vary</span>}
      </p>

      {topDeals.length > 0 && (
        <ul className="mt-2 space-y-0.5">
          {topDeals.map((d, i) => (
            <li key={i} className="text-text-muted text-xs">
              • {d}
            </li>
          ))}
        </ul>
      )}

      {venue.google_rating != null && (
        <p className="text-primary text-xs mt-2">★ {venue.google_rating}</p>
      )}
    </div>
  );
}
