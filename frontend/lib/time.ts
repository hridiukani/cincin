import type { Deal } from "./types";

const PHOENIX_TZ = "America/Phoenix";

export function formatTime12h(time: string): string {
  const [hourStr, minuteStr] = time.split(":");
  const hour = Number(hourStr);
  const minute = Number(minuteStr);
  const period = hour >= 12 ? "PM" : "AM";
  const hour12 = hour % 12 === 0 ? 12 : hour % 12;
  return `${hour12}:${minute.toString().padStart(2, "0")} ${period}`;
}

export function isLiveNow(deal: Deal): boolean {
  if (!deal.start_time || !deal.end_time) return false;

  const now = new Date();
  const currentDay = new Intl.DateTimeFormat("en-US", {
    timeZone: PHOENIX_TZ,
    weekday: "long",
  }).format(now);

  if (!deal.days.includes(currentDay)) return false;

  const currentTime = new Intl.DateTimeFormat("en-US", {
    timeZone: PHOENIX_TZ,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(now);

  return currentTime >= deal.start_time && currentTime <= deal.end_time;
}
