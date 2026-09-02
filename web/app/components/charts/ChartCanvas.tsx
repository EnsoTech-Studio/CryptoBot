"use client";

import type { ReactElement } from "react";

import type { Candle, ExecutionMarker, OverlayMarker, OverlayPoint, OverlaySeries } from "../../../lib/api";

export type ChartSize = "primary" | "context" | "result" | "realtime";

/* One frame per role. The old single frame drew the same 900x280 geometry into
   a ~340px box, so axis text and the sub pane were rendered at roughly a third
   of their design size. Context charts now drop axis labels, the sub pane and
   half the history, because none of it survives that downscale. */
const CHART_FRAMES: Record<ChartSize, {
  width: number;
  height: number;
  pad: { left: number; right: number; top: number; bottom: number };
  gap: number;
  volumeH: number;
  subH: number;
  visible: number;
  gridTicks: number[];
  showAxis: boolean;
}> = {
  primary: {
    width: 900,
    height: 386,
    pad: { left: 54, right: 54, top: 16, bottom: 24 },
    gap: 8,
    volumeH: 56,
    subH: 62,
    visible: 120,
    gridTicks: [0, 0.25, 0.5, 0.75, 1],
    showAxis: true,
  },
  result: {
    width: 900,
    height: 560,
    pad: { left: 58, right: 58, top: 20, bottom: 28 },
    gap: 10,
    volumeH: 72,
    subH: 70,
    visible: 120,
    gridTicks: [0, 0.25, 0.5, 0.75, 1],
    showAxis: true,
  },
  realtime: {
    width: 640,
    height: 300,
    pad: { left: 38, right: 58, top: 12, bottom: 20 },
    gap: 6,
    volumeH: 48,
    subH: 0,
    visible: 60,
    gridTicks: [0, 0.25, 0.5, 0.75, 1],
    showAxis: true,
  },
  context: {
    width: 460,
    height: 112,
    pad: { left: 8, right: 8, top: 6, bottom: 6 },
    gap: 4,
    volumeH: 16,
    subH: 0,
    visible: 60,
    gridTicks: [0, 0.5, 1],
    showAxis: false,
  },
};

export function ChartCanvas({
  candles,
  series,
  markers,
  executionMarkers = [],
  size = "primary",
  visibleLimit,
  ariaLabel = "Candlestick chart with volume and strategy overlays",
}: {
  candles: Candle[];
  series: OverlaySeries[];
  markers: OverlayMarker[];
  executionMarkers?: ExecutionMarker[];
  size?: ChartSize;
  /* Result charts can opt into an explicit selected window. Other chart roles
     retain their compact trailing viewport. */
  visibleLimit?: number;
  ariaLabel?: string;
}) {
  const frame = CHART_FRAMES[size];
  const { width, height, pad, gap, volumeH } = frame;
  const subSeries = series.filter((item) => item.pane === "sub");
  const subH = subSeries.length > 0 ? frame.subH : 0;
  const plotH = height - pad.top - pad.bottom - volumeH - subH - gap * (subH > 0 ? 2 : 1);
  const plotW = width - pad.left - pad.right;
  const volumeTop = pad.top + plotH + gap;
  const subTop = volumeTop + volumeH + (subH > 0 ? gap : 0);
  const view = candles.slice(-(visibleLimit ?? frame.visible));
  const visibleTimes = new Set(view.map((candle) => candle.open_time));

  const priceValues = view.flatMap((candle) => [candle.high, candle.low]);
  series.filter((item) => item.pane === "main").forEach((item) => {
    item.points?.forEach((point) => { if (point.v != null && visibleTimes.has(point.t)) priceValues.push(point.v); });
    item.band?.upper.forEach((point) => { if (point.v != null && visibleTimes.has(point.t)) priceValues.push(point.v); });
    item.band?.lower.forEach((point) => { if (point.v != null && visibleTimes.has(point.t)) priceValues.push(point.v); });
    item.zones?.forEach((zone) => priceValues.push(zone.price_low, zone.price_high));
  });
  executionMarkers.forEach((marker) => {
    if (marker.price != null) priceValues.push(marker.price);
  });

  const minPrice = Number.isFinite(Math.min(...priceValues)) ? Math.min(...priceValues) : 0;
  const maxPrice = Number.isFinite(Math.max(...priceValues)) ? Math.max(...priceValues) : 1;
  const pricePadding = Math.max(1, (maxPrice - minPrice) * 0.08);
  const priceMin = minPrice - pricePadding;
  const priceMax = maxPrice + pricePadding;
  const maxVolume = Math.max(1, ...view.map((candle) => candle.volume));
  const x = (index: number) => pad.left + (index / Math.max(1, view.length - 1)) * plotW;
  const y = (value: number) => pad.top + (1 - (value - priceMin) / Math.max(1, priceMax - priceMin)) * plotH;
  const vy = (value: number) => volumeTop + (1 - value / maxVolume) * volumeH;
  const candleWidth = Math.max(2, plotW / Math.max(1, view.length) * 0.58);

  return (
    <svg
      className="chart-svg"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label={ariaLabel}
    >
      <title>{ariaLabel}</title>
      <rect x="0" y="0" width={width} height={height} className="chart-bg" />
      <rect x={pad.left} y={pad.top} width={plotW} height={plotH} className="pane-bg main-pane" />
      <rect x={pad.left} y={volumeTop} width={plotW} height={volumeH} className="pane-bg volume-pane" />
      {subH > 0 ? <rect x={pad.left} y={subTop} width={plotW} height={subH} className="pane-bg sub-pane" /> : null}
      {view.length === 0 ? (
        <text x={width / 2} y={height / 2} textAnchor="middle" className="empty-chart">market data unavailable</text>
      ) : null}
      {frame.gridTicks.map((tick) => (
        <line key={tick} x1={pad.left} x2={width - pad.right} y1={pad.top + tick * plotH} y2={pad.top + tick * plotH} className="grid-line" />
      ))}
      {frame.gridTicks.map((tick) => (
        <line key={`x-${tick}`} x1={pad.left + tick * plotW} x2={pad.left + tick * plotW} y1={pad.top} y2={volumeTop + volumeH} className="grid-line soft" />
      ))}
      {[0, 0.5, 1].map((tick) => (
        <line key={`v-${tick}`} x1={pad.left} x2={width - pad.right} y1={volumeTop + tick * volumeH} y2={volumeTop + tick * volumeH} className="grid-line soft" />
      ))}
      {subH > 0 ? [0, 0.5, 1].map((tick) => (
        <line key={`s-${tick}`} x1={pad.left} x2={width - pad.right} y1={subTop + tick * subH} y2={subTop + tick * subH} className="grid-line soft" />
      )) : null}
      {view.map((candle, index) => {
        const cx = x(index);
        const up = candle.close >= candle.open;
        const bodyTop = y(Math.max(candle.open, candle.close));
        const bodyBottom = y(Math.min(candle.open, candle.close));
        const volumeY = vy(candle.volume);
        return (
          <g key={candle.open_time}>
            <rect x={cx - candleWidth / 2} y={volumeY} width={candleWidth} height={Math.max(1, volumeTop + volumeH - volumeY)} className={up ? "volume-bar up" : "volume-bar down"} />
            <line x1={cx} x2={cx} y1={y(candle.high)} y2={y(candle.low)} className={up ? "wick up" : "wick down"} />
            <rect x={cx - candleWidth / 2} y={bodyTop} width={candleWidth} height={Math.max(2, bodyBottom - bodyTop)} className={up ? "body up" : "body down"} />
          </g>
        );
      })}
      {series.filter((item) => item.pane === "main").flatMap((item, index) => renderMainSeries(item, view, index, x, y))}
      {renderSignalMarkers(markers, view, x, y, size === "context" ? 0.5 : 1)}
      {renderExecutionMarkers(executionMarkers, view, x, y, width - pad.right)}
      {subH > 0 ? subSeries.flatMap((item, index) => renderSubSeries(item, view, index, x, subTop, subH, pad.left, width - pad.right)) : null}
      {frame.showAxis ? (
        <>
          {frame.gridTicks.map((tick) => {
            const candle = view[Math.round(tick * Math.max(0, view.length - 1))];
            const anchor = tick === 0 ? "start" : tick === 1 ? "end" : "middle";
            return (
              <text key={`time-${tick}`} x={pad.left + tick * plotW} y={height - 8} textAnchor={anchor} className="axis-label">
                {candle ? chartTimeLabel(candle.open_time, candle.timeframe) : ""}
              </text>
            );
          })}
          {frame.gridTicks.map((tick) => (
            <text key={`price-${tick}`} x={width - pad.right + 6} y={pad.top + tick * plotH + (tick === 0 ? 9 : tick === 1 ? -2 : 3)} className="price-label">
              {(priceMax - tick * (priceMax - priceMin)).toFixed(2)}
            </text>
          ))}
          <text x={pad.left + 6} y={volumeTop + 12} className="axis-label">
            Volume <tspan className="volume-value">{view.at(-1) ? compactVolume(view.at(-1)!.volume) : ""}</tspan>
          </text>
          {size === "realtime" ? (
            <>
              <text x={width - pad.right + 6} y={volumeTop + 10} className="price-label">{compactVolume(maxVolume)}</text>
              <text x={width - pad.right + 6} y={volumeTop + volumeH - 1} className="price-label">0</text>
            </>
          ) : null}
        </>
      ) : null}
      {size === "realtime" && view.at(-1) ? (() => {
        const latest = view.at(-1)!;
        const direction = latest.close >= latest.open ? "up" : "down";
        const latestY = y(latest.close);
        return (
          <>
            <line x1={pad.left} x2={width - pad.right} y1={latestY} y2={latestY} className={`current-price-line ${direction}`} />
            <rect x={width - pad.right + 2} y={latestY - 8} width="54" height="16" rx="3" className={`current-price-box ${direction}`} />
            <text x={width - pad.right + 29} y={latestY + 3} textAnchor="middle" className="current-price-label">{latest.close.toFixed(2)}</text>
          </>
        );
      })() : null}
    </svg>
  );
}

function renderMainSeries(
  item: OverlaySeries,
  candles: Candle[],
  seriesIndex: number,
  x: (index: number) => number,
  y: (value: number) => number,
) {
  const paths: ReactElement[] = [];
  const keyPrefix = `${item.name}-${seriesIndex}`;
  if (item.points) {
    const d = pointPath(item.points, candles, x, y);
    if (d) paths.push(<path key={`${keyPrefix}-line`} d={d} className={`overlay-line ${item.overlay_type} ${item.style ?? "solid"}`} />);
  }
  if (item.band) {
    const area = bandAreaPath(item.band.upper, item.band.lower, candles, x, y);
    if (area) paths.push(<path key={`${keyPrefix}-fill`} d={area} className="band-fill" />);
    for (const [name, points] of Object.entries(item.band)) {
      const d = pointPath(points as OverlayPoint[], candles, x, y);
      if (d) paths.push(<path key={`${keyPrefix}-${name}`} d={d} className={`overlay-line bollinger ${name}`} />);
    }
  }
  item.zones?.forEach((zone, index) => {
    const startIndex = clampIndex(indexForTime(candles, zone.from), candles.length);
    const endIndex = clampIndex(indexForTime(candles, zone.to), candles.length, candles.length - 1);
    paths.push(
      <rect
        key={`${keyPrefix}-zone-${index}`}
        x={x(startIndex)}
        y={y(zone.price_high)}
        width={Math.max(1, x(endIndex) - x(startIndex))}
        height={Math.max(2, y(zone.price_low) - y(zone.price_high))}
        className={item.overlay_type.includes("support") ? "zone support" : "zone resistance"}
      />,
    );
  });
  return paths;
}

function renderSubSeries(
  item: OverlaySeries,
  candles: Candle[],
  seriesIndex: number,
  x: (index: number) => number,
  top: number,
  height: number,
  left: number,
  right: number,
) {
  const values = item.points?.map((point) => point.v).filter((value): value is number => value != null) ?? [];
  const min = item.scale?.min ?? Math.min(...values, 0);
  const max = item.scale?.max ?? Math.max(...values, 1);
  const y = (value: number) => top + (1 - (value - min) / Math.max(1, max - min)) * height;
  const paths: ReactElement[] = [];
  if (item.constant != null) {
    const lineY = y(item.constant);
    paths.push(<line key={`${item.name}-constant-${seriesIndex}`} x1={left} x2={right} y1={lineY} y2={lineY} className="sub-constant" />);
  }
  if (item.points) {
    const d = pointPath(item.points, candles, x, y);
    if (d) paths.push(<path key={`${item.name}-sub-${seriesIndex}`} d={d} className={`overlay-line sub ${item.overlay_type}`} />);
  }
  return paths;
}

function renderSignalMarkers(
  markers: OverlayMarker[],
  candles: Candle[],
  x: (index: number) => number,
  y: (value: number) => number,
  scale = 1,
) {
  return markers.flatMap((marker): ReactElement[] => {
    const index = indexForTime(candles, marker.t);
    if (index < 0) return [];
    const candle = candles[index];
    const isBuy = marker.overlay_type.includes("buy");
    const cx = x(index);
    const cy = isBuy ? y(candle.low) + 18 * scale : y(candle.high) - 18 * scale;
    const shape = (
      <path
        key={`${marker.t}-${marker.overlay_type}-shape`}
        d={isBuy ? triangleUp(cx, cy, scale) : triangleDown(cx, cy, scale)}
        className={isBuy ? "signal-marker buy" : "signal-marker sell"}
      />
    );
    /* The B/S glyph is illegible on a context chart, so the shape carries the
       meaning alone at small scale. */
    if (scale < 1) return [shape];
    return [
      shape,
      <text key={`${marker.t}-${marker.overlay_type}-text`} x={cx} y={isBuy ? cy + 4 : cy + 3} textAnchor="middle" className="signal-text">{isBuy ? "B" : "S"}</text>,
    ];
  });
}

function renderExecutionMarkers(
  markers: ExecutionMarker[],
  candles: Candle[],
  x: (index: number) => number,
  y: (value: number) => number,
  maxX: number,
) {
  return markers.flatMap((marker, index): ReactElement[] => {
    if (marker.price == null) return [];
    const markerIndex = indexForTime(candles, marker.t);
    if (markerIndex < 0) return [];
    const cx = x(markerIndex);
    const cy = y(marker.price);
    if (marker.overlay_type === "take_profit" || marker.overlay_type === "stop_loss") {
      const endIndex = clampIndex(indexForTime(candles, marker.line_until ?? marker.t), candles.length, candles.length - 1);
      const label = marker.overlay_type === "take_profit" ? "Take Profit" : "Stop Loss";
      return [
        <line key={`${marker.overlay_type}-${index}`} x1={cx} x2={x(endIndex)} y1={cy} y2={cy} className={`risk-line ${marker.overlay_type}`} />,
        <text key={`${marker.overlay_type}-${index}-label`} x={Math.min(x(endIndex) + 5, maxX - 12)} y={cy - 4} className={`risk-label ${marker.overlay_type}`}>{label}</text>,
      ];
    }
    if (marker.overlay_type === "entry" || marker.overlay_type.endsWith("_entry")) {
      const label = marker.overlay_type.startsWith("short") ? "SHORT Entry" : marker.overlay_type.startsWith("long") ? "LONG Entry" : "ENTRY";
      return [
        <circle key={`entry-${index}`} cx={cx} cy={cy} r="5" className={`exec-marker entry${marker.selected ? " selected" : ""}`} />,
        <text key={`entry-${index}-label`} x={cx + 8} y={cy - 8} className={`exec-label${marker.selected ? " selected" : ""}`}>{label}</text>,
      ];
    }
    if (marker.overlay_type === "exit") {
      return [
        <path key={`exit-${index}`} d={crossPath(cx, cy)} className={`exec-marker exit ${marker.exit_reason ?? ""}${marker.selected ? " selected" : ""}`} />,
        <text key={`exit-${index}-label`} x={cx + 8} y={cy + 13} className={`exec-label${marker.selected ? " selected" : ""}`}>EXIT</text>,
      ];
    }
    return [];
  });
}

function pointPath(points: OverlayPoint[], candles: Candle[], x: (index: number) => number, y: (value: number) => number) {
  const visible = points
    .map((point) => ({ point, index: indexForTime(candles, point.t) }))
    .filter(({ point, index }) => index >= 0 && point.v != null);
  return visible.map(({ point, index }, i) => `${i === 0 ? "M" : "L"}${x(index)},${y(point.v as number)}`).join(" ");
}

function bandAreaPath(
  upper: OverlayPoint[],
  lower: OverlayPoint[],
  candles: Candle[],
  x: (index: number) => number,
  y: (value: number) => number,
) {
  const upperCoords = upper
    .map((point) => ({ point, index: indexForTime(candles, point.t) }))
    .filter(({ point, index }) => index >= 0 && point.v != null)
    .map(({ point, index }) => `${x(index)},${y(point.v as number)}`);
  const lowerCoords = lower
    .map((point) => ({ point, index: indexForTime(candles, point.t) }))
    .filter(({ point, index }) => index >= 0 && point.v != null)
    .map(({ point, index }) => `${x(index)},${y(point.v as number)}`)
    .reverse();
  if (upperCoords.length < 2 || lowerCoords.length < 2) return "";
  return `M${upperCoords.join(" L")} L${lowerCoords.join(" L")} Z`;
}

function indexForTime(candles: Candle[], value: string): number {
  const direct = candles.findIndex((candle) => candle.open_time === value);
  if (direct >= 0) return direct;
  const target = Date.parse(value);
  if (!Number.isFinite(target)) return -1;
  return candles.findIndex((candle) => Date.parse(candle.open_time) === target);
}

function clampIndex(value: number, length: number, fallback = 0): number {
  if (length <= 0) return 0;
  if (value < 0) return Math.max(0, Math.min(length - 1, fallback));
  return Math.max(0, Math.min(length - 1, value));
}

function triangleUp(x: number, y: number, s = 1) {
  return `M${x},${y - 11 * s} L${x - 9 * s},${y + 7 * s} L${x + 9 * s},${y + 7 * s} Z`;
}

function triangleDown(x: number, y: number, s = 1) {
  return `M${x},${y + 11 * s} L${x - 9 * s},${y - 7 * s} L${x + 9 * s},${y - 7 * s} Z`;
}

function crossPath(x: number, y: number) {
  return `M${x - 7},${y - 7} L${x + 7},${y + 7} M${x + 7},${y - 7} L${x - 7},${y + 7}`;
}

function compactVolume(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toFixed(0);
}

function chartTimeLabel(value: string, timeframe: string) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  if (timeframe === "1h" || timeframe === "4h") {
    return `${String(date.getUTCDate()).padStart(2, "0")}/${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
  }
  return `${String(date.getUTCHours()).padStart(2, "0")}:${String(date.getUTCMinutes()).padStart(2, "0")}`;
}
