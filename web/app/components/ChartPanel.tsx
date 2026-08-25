"use client";

import { formatPrice } from "../../lib/format";
import { strategyName } from "../../lib/strategies";
import type { Panel } from "../providers/workspace";
import type { Strategy } from "../../lib/api";
import { ChartCanvas } from "./charts/ChartCanvas";
import { ChartSkeleton } from "./States";

export function ChartPanel({ panel, strategies, variant, onTimeframe, onStrategy, onFocus }: {
  panel: Panel;
  strategies: Strategy[];
  variant: "primary" | "context";
  onTimeframe: (timeframe: string) => void;
  onStrategy: (strategy: string) => void;
  onFocus?: () => void;
}) {
  const hasCurrentStrategy = strategies.some((strategy) => `${strategy.strategy_id}@${strategy.version}` === panel.strategy);
  const lastCandle = panel.candles.at(-1);
  const priceChange = lastCandle && lastCandle.open !== 0 ? ((lastCandle.close - lastCandle.open) / lastCandle.open) * 100 : null;
  const isPrimary = variant === "primary";

  const identity = (
    <>
      <div className="pair-line">
        <strong>ETHUSDT</strong>
        <span>{panel.timeframe}</span>
      </div>
      <p>{panel.title} · {strategyName(strategies, panel.strategy)}</p>
    </>
  );

  return (
    <section className={`chart-panel ${variant}`} aria-current={isPrimary ? "true" : undefined}>
      <div className="chart-toolbar">
        {isPrimary ? (
          <div>{identity}</div>
        ) : (
          <button
            type="button"
            className="focus-trigger"
            onClick={onFocus}
            title={`Promote ${panel.title} to the primary chart`}
          >
            {identity}
          </button>
        )}
        <div className="chart-quote">
          <strong>{lastCandle ? formatPrice(lastCandle.close) : "—"}</strong>
          <span className={priceChange == null || priceChange >= 0 ? "positive" : "negative"}>
            {priceChange == null ? "awaiting feed" : `${priceChange >= 0 ? "+" : ""}${priceChange.toFixed(2)}%`}
          </span>
          <span className={`live-badge ${panel.liveState}`}><i />{panel.liveState}</span>
        </div>
      </div>

      {!panel.loaded && panel.candles.length === 0 ? (
        <ChartSkeleton size={isPrimary ? "primary" : "context"} />
      ) : (
        <ChartCanvas
          candles={panel.candles}
          series={panel.series ?? []}
          markers={panel.markers ?? []}
          size={isPrimary ? "primary" : "context"}
        />
      )}

      {panel.error ? <p className="panel-error">{panel.error}</p> : null}

      {isPrimary ? (
        <div className="chart-legend" aria-label="Chart layers">
          <span className="legend-item candle">Candle</span>
          <span className="legend-item volume">Volume</span>
          <span className="legend-item ma">MA</span>
          <span className="legend-item band">BB</span>
          <span className="legend-item structure">S/R</span>
          <span className="legend-item signal">Signal</span>
        </div>
      ) : null}

      <div className="chart-controls">
        <select value={panel.timeframe} onChange={(event) => onTimeframe(event.target.value)} aria-label={`${panel.title} timeframe`}>
          {["1m", "5m", "15m", "1h", "4h", "1d"].map((tf) => <option key={tf}>{tf}</option>)}
        </select>
        <select value={panel.strategy} onChange={(event) => onStrategy(event.target.value)} aria-label={`${panel.title} strategy`}>
          {!hasCurrentStrategy ? <option value={panel.strategy}>{panel.strategy}</option> : null}
          {strategies.map((strategy) => (
            <option key={`${strategy.strategy_id}@${strategy.version}`} value={`${strategy.strategy_id}@${strategy.version}`}>
              {strategy.display_name}
            </option>
          ))}
        </select>
      </div>
    </section>
  );
}
