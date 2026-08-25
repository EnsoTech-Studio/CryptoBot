"use client";

import type { EquityPoint } from "../../../lib/api";

export function EquityChart({ points }: { points: EquityPoint[] }) {
  const width = 360;
  const height = 128;

  if (points.length === 0) {
    return (
      <svg className="equity-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Equity curve unavailable">
        <text x={width / 2} y={height / 2} textAnchor="middle">equity unavailable</text>
      </svg>
    );
  }

  const values = points.map((point) => point.equity);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const minDrawdown = Math.min(...points.map((point) => point.drawdown_pct), 0);

  const path = points.map((point, index) => {
    const px = (index / Math.max(1, points.length - 1)) * (width - 20) + 10;
    const py = 10 + (1 - (point.equity - minValue) / Math.max(1, maxValue - minValue)) * (height - 24);
    return `${index === 0 ? "M" : "L"}${px},${py}`;
  }).join(" ");

  const drawdownPath = points.map((point, index) => {
    const px = (index / Math.max(1, points.length - 1)) * (width - 20) + 10;
    const py = height - 12 - (Math.abs(point.drawdown_pct) / Math.max(1, Math.abs(minDrawdown))) * (height - 34);
    return `${index === 0 ? "M" : "L"}${px},${py}`;
  }).join(" ");

  return (
    <svg className="equity-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Equity curve with drawdown">
      <path className="drawdown" d={drawdownPath} />
      <path className="equity" d={path} />
    </svg>
  );
}
