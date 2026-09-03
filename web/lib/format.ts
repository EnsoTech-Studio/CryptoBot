/* Formatting helpers shared by every workspace surface. */

export const DISPLAY_TIME_ZONE = "Asia/Ho_Chi_Minh";

export function formatNumber(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return "0.00";
  return value.toFixed(2);
}

export function formatPrice(value: number): string {
  return value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatCompact(value: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 }).format(value);
}

export function compactDate(value: string): string {
  return new Date(value).toLocaleDateString("en-US", { month: "2-digit", day: "2-digit", timeZone: "UTC" });
}

export function compactTime(value: string): string {
  return `${new Date(value).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" })} UTC`;
}

export function compactDateTime(value: string): string {
  return new Date(value).toLocaleString("en-US", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "UTC",
  });
}

export function messageFromError(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed";
}
