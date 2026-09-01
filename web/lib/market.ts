export const DEFAULT_MARKET: MarketSelection = {
  provider: "binance_usdm",
  symbol: "ETHUSDT",
};

export const DEFAULT_PANEL_TIMEFRAMES: readonly string[] = ["5m", "15m", "1h", "4h"];

export const REFERENCE_MARKET: MarketSelection = {
  provider: "binance_usdm",
  symbol: "BTCUSDT",
};

export const MARKET_CONFIG_HASH = `sha256:${"4".repeat(64)}`;
export const PANEL_BOOTSTRAP_CANDLE_LIMIT = 1_000;

export type Candle = {
  provider: string;
  symbol: string;
  timeframe: string;
  open_time: string;
  close_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  trade_count: number;
};

export type MarketPair = {
  provider: string;
  symbol: string;
  base_asset: string;
  quote_asset: string;
  timeframes: string[];
};

export type MarketSelection = {
  provider: string;
  symbol: string;
};

export type MarketStatus = {
  provider: string;
  symbol: string;
  timeframe: string;
  stale: boolean;
  last_closed_at: string | null;
  last_sequence: number | null;
  reconnect_count: number;
};

export type RecentMarketEvent = {
  id: string;
  occurredAt: string;
  bid: number;
  ask: number;
  bidQty: number;
  askQty: number;
  sourceSequence?: number;
};

export type NormalizedRealtimeFrame = {
  type: "subscribed" | "resync_required" | "kline" | "overlay_delta" | "bbo" | "stream_status" | "error" | "unknown";
  sequence?: number;
  serverTime?: string;
  final?: boolean;
  state?: "connecting" | "stale" | "connected" | "recovered";
  occurredAt?: string;
  reconnectNo?: number;
  kline?: {
    openTime: string;
    closeTime: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    tradeCount: number;
  };
  bbo?: RecentMarketEvent;
  overlay?: {
    revisedFrom?: string;
    series: RealtimeOverlaySeries[];
    markers: RealtimeOverlayMarker[];
  };
};

export type RealtimeOverlayPoint = { t: string; v: number | null };
export type RealtimeOverlaySeries = {
  name: string;
  overlay_type: string;
  pane: "main" | "sub";
  points?: RealtimeOverlayPoint[];
  band?: Record<string, RealtimeOverlayPoint[]>;
};
export type RealtimeOverlayMarker = {
  t: string;
  overlay_type: string;
  confidence: number | null;
  evidence: Record<string, unknown> | null;
};

export function marketRequestPath(
  endpoint: string,
  market: MarketSelection,
  options: Record<string, string | number | undefined> = {},
) {
  const params = new URLSearchParams({
    provider: market.provider,
    symbol: market.symbol.toUpperCase(),
  });
  Object.entries(options).forEach(([key, value]) => {
    if (value !== undefined) params.set(key, String(value));
  });
  return `${endpoint}?${params.toString()}`;
}

export function marketKey(market: MarketSelection) {
  return `${market.provider}|${market.symbol.toUpperCase()}`;
}

export function buildSubscriptionKey(market: MarketSelection, timeframe: string, strategy: string) {
  return `${market.provider}|${market.symbol.toUpperCase()}|${timeframe}|${strategy}|${MARKET_CONFIG_HASH}`;
}

export function upsertCandle(candles: Candle[], candle: Candle, limit = 1_000): Candle[] {
  const next = candles.filter((item) => item.open_time !== candle.open_time);
  next.push(candle);
  return next.sort((a, b) => a.open_time.localeCompare(b.open_time)).slice(-limit);
}

export function appendMarketEvent(events: RecentMarketEvent[], event: RecentMarketEvent, limit = 50) {
  return [event, ...events.filter((item) => item.id !== event.id)].slice(0, limit);
}

export function mergeOverlayDelta(
  current: { series: RealtimeOverlaySeries[]; markers: RealtimeOverlayMarker[] },
  delta: { series: RealtimeOverlaySeries[]; markers: RealtimeOverlayMarker[] },
) {
  const series = [...current.series];
  for (const next of delta.series) {
    const index = series.findIndex((item) => item.name === next.name && item.overlay_type === next.overlay_type && item.pane === next.pane);
    if (index < 0) {
      series.push(next);
      continue;
    }
    const previous = series[index];
    series[index] = {
      ...previous,
      ...next,
      ...(next.points ? { points: mergeOverlayPoints(previous.points, next.points) } : {}),
      ...(next.band ? { band: mergeOverlayBand(previous.band, next.band) } : {}),
    };
  }
  return { series, markers: mergeOverlayMarkers(current.markers, delta.markers) };
}

export function normalizeRealtimeFrame(value: unknown, market: MarketSelection): NormalizedRealtimeFrame {
  const frame = asRecord(value);
  const payload = asRecord(frame.payload);
  const body = Object.keys(payload).length > 0 ? { ...frame, ...payload } : frame;
  const type = frameType(body.type);
  const sequence = optionalNumber(body.sequence ?? body.seq);
  const serverTime = optionalString(body.server_time);

  if (type === "kline") {
    const kline = asRecord(body.kline);
    const openTime = optionalString(kline.open_time);
    const closeTime = optionalString(kline.close_time);
    const open = optionalNumber(kline.open);
    const high = optionalNumber(kline.high);
    const low = optionalNumber(kline.low);
    const close = optionalNumber(kline.close);
    const volume = optionalNumber(kline.volume);
    if (openTime && closeTime && open !== undefined && high !== undefined && low !== undefined && close !== undefined && volume !== undefined) {
      return {
        type,
        sequence,
        serverTime,
        final: Boolean(body.final),
        kline: {
          openTime,
          closeTime,
          open,
          high,
          low,
          close,
          volume,
          tradeCount: optionalNumber(kline.trade_count) ?? 0,
        },
      };
    }
  }

  if (type === "bbo") {
    const eventTime = optionalString(body.event_time) ?? serverTime;
    const bid = optionalNumber(body.bid);
    const ask = optionalNumber(body.ask);
    const bidQty = optionalNumber(body.bid_qty);
    const askQty = optionalNumber(body.ask_qty);
    const sourceSequence = optionalNumber(body.source_sequence);
    const updateID = optionalNumber(body.update_id);
    if (eventTime && bid !== undefined && ask !== undefined && bidQty !== undefined && askQty !== undefined) {
      const identity = sourceSequence ?? updateID ?? `${eventTime}|${bid}|${ask}`;
      return {
        type,
        sequence,
        serverTime,
        bbo: {
          id: `${marketKey(market)}|${identity}`,
          occurredAt: eventTime,
          bid,
          ask,
          bidQty,
          askQty,
          sourceSequence,
        },
      };
    }
  }

  if (type === "overlay_delta") {
    const series = asRecords(body.series).flatMap((item) => {
      const name = optionalString(item.name);
      const overlayType = optionalString(item.overlay_type);
      const pane: "main" | "sub" | undefined = item.pane === "main" || item.pane === "sub" ? item.pane : undefined;
      if (!name || !overlayType || !pane) return [];
      const points = asRecords(item.points).flatMap((point) => {
        const t = optionalString(point.t);
        const v = point.v === null ? null : optionalNumber(point.v);
        return t && (v !== undefined || point.v === null) ? [{ t, v: v as number | null }] : [];
      });
      const band = asRecord(item.band);
      const normalizedBand: Record<string, RealtimeOverlayPoint[]> = {};
      for (const bandName of ["upper", "middle", "lower"]) {
        normalizedBand[bandName] = asRecords(band[bandName]).flatMap((point) => {
          const t = optionalString(point.t);
          const v = point.v === null ? null : optionalNumber(point.v);
          return t && (v !== undefined || point.v === null) ? [{ t, v: v as number | null }] : [];
        });
      }
      return [{
        name,
        overlay_type: overlayType,
        pane,
        ...(points.length > 0 ? { points } : {}),
        ...(Object.values(normalizedBand).some((values) => values.length > 0) ? { band: normalizedBand } : {}),
      }];
    });
    const markers = asRecords(body.markers).flatMap((item) => {
      const t = optionalString(item.t);
      const overlayType = optionalString(item.overlay_type);
      if (!t || !overlayType) return [];
      const evidence = item.evidence !== null && typeof item.evidence === "object"
        ? item.evidence as Record<string, unknown>
        : null;
      return [{ t, overlay_type: overlayType, confidence: optionalNumber(item.confidence) ?? null, evidence }];
    });
    return {
      type,
      sequence,
      serverTime,
      overlay: { revisedFrom: optionalString(body.revised_from), series, markers },
    };
  }

  if (type === "stream_status") {
    return {
      type,
      sequence,
      serverTime,
      state: streamState(body.state),
      occurredAt: optionalString(body.occurred_at),
      reconnectNo: optionalNumber(body.reconnect_no),
    };
  }

  return { type, sequence, serverTime };
}

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" ? value as Record<string, unknown> : {};
}

function mergeOverlayPoints(previous: RealtimeOverlayPoint[] = [], next: RealtimeOverlayPoint[]) {
  return [...previous.filter((point) => !next.some((item) => item.t === point.t)), ...next]
    .sort((a, b) => a.t.localeCompare(b.t)).slice(-1_000);
}

function mergeOverlayBand(
  previous: Record<string, RealtimeOverlayPoint[]> = {},
  next: Record<string, RealtimeOverlayPoint[]>,
) {
  return Object.fromEntries(Object.keys({ ...previous, ...next }).map((name) => [
    name,
    mergeOverlayPoints(previous[name], next[name] ?? []),
  ]));
}

function mergeOverlayMarkers(previous: RealtimeOverlayMarker[], next: RealtimeOverlayMarker[]) {
  return [...previous.filter((marker) => !next.some((item) => item.t === marker.t && item.overlay_type === marker.overlay_type)), ...next]
    .sort((a, b) => a.t.localeCompare(b.t)).slice(-1_000);
}

function asRecords(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.map(asRecord) : [];
}

function optionalString(value: unknown) {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function optionalNumber(value: unknown) {
  if (value === null || value === undefined || value === "") return undefined;
  const number = Number(value);
  return Number.isFinite(number) ? number : undefined;
}

function frameType(value: unknown): NormalizedRealtimeFrame["type"] {
  switch (value) {
    case "subscribed":
    case "resync_required":
    case "kline":
    case "overlay_delta":
    case "bbo":
    case "stream_status":
    case "error":
      return value;
    default:
      return "unknown";
  }
}

function streamState(value: unknown): NormalizedRealtimeFrame["state"] {
  switch (value) {
    case "connecting":
    case "stale":
    case "connected":
    case "recovered":
      return value;
    default:
      return undefined;
  }
}
