/** Joins conditional class name fragments, skipping falsy values --
 * a tiny local stand-in for the common `clsx`/`cn` pattern, kept
 * dependency-free since this project only needs the simple case. */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/** Formats a seconds count as "Xh Ym" / "Ym" for coin-reset countdowns. */
export function formatDuration(totalSeconds: number): string {
  if (totalSeconds <= 0) return "any moment now";
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  if (hours > 0 && minutes > 0) return `${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h`;
  return `${minutes}m`;
}

/** Formats an ISO-ish timestamp string (as returned by the backend,
 * which serializes SQLite datetimes as plain strings) into a short,
 * locale-aware display string. Falls back to the raw string if
 * parsing fails, rather than throwing. */
export function formatTimestamp(raw: string): string {
  const date = new Date(raw.includes("T") ? raw : raw.replace(" ", "T") + "Z");
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatRelativeTime(raw: string): string {
  const date = new Date(raw.includes("T") ? raw : raw.replace(" ", "T") + "Z");
  if (Number.isNaN(date.getTime())) return raw;
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  return formatTimestamp(raw);
}
