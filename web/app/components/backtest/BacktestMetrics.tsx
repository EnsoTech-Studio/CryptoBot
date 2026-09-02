"use client";

import { MOCK_KPIS } from "../../../lib/backtest-mock";
import { resolvedTradeKpis, type DerivedKpis } from "../../../lib/backtest";
import type { EquityPoint, Metrics } from "../../../lib/api";
import styles from "./backtest.module.css";

/* Six KPI cells plus the two explanation panels. Winrate, return and drawdown
   come from the evaluator; wins, losses and absolute profit are derived from the
   settled trade list because the metrics payload does not carry them. */
export function BacktestMetrics({
  metrics,
  kpis,
  equity,
  isMock,
}: {
  metrics: Metrics | null;
  kpis: DerivedKpis;
  equity: EquityPoint[];
  isMock: boolean;
}) {
  const winrate = isMock ? MOCK_KPIS.winratePct : metrics?.win_rate_pct ?? 0;
  const aggregateKpis = resolvedTradeKpis(metrics, kpis);
  const wins = isMock ? MOCK_KPIS.wins : aggregateKpis.wins;
  const losses = isMock ? MOCK_KPIS.losses : aggregateKpis.losses;
  const totalTrades = isMock ? MOCK_KPIS.totalTrades : metrics?.trade_count ?? kpis.settled;
  const profitAbs = isMock ? MOCK_KPIS.totalProfitUsd : aggregateKpis.netProfit;
  const profitPct = isMock ? MOCK_KPIS.totalProfitPct : metrics?.total_return_pct ?? 0;
  const drawdownPct = isMock ? MOCK_KPIS.maxDrawdownPct : metrics?.max_drawdown_pct ?? 0;
  const profitFactor = isMock ? 1.84 : metrics?.profit_factor ?? 0;
  const sharpeRatio = isMock ? 1.27 : metrics?.sharpe_ratio ?? 0;

  return (
    <div className={styles.metricsRow}>
      <div className={styles.kpiCell}>
        <span className={styles.kpiLabel}>Winrate</span>
        <span className={`${styles.kpiValue} ${styles.gain}`}>{winrate.toFixed(2)}%</span>
        <span className={styles.kpiCaption}>{wins} / {totalTrades}</span>
        <span className={styles.donut}>
          <Donut ratio={totalTrades > 0 ? wins / totalTrades : 0} />
        </span>
      </div>

      <div className={styles.kpiCell}>
        <span className={styles.kpiLabel}>Wins</span>
        <span className={`${styles.kpiValue} ${styles.gain}`}>{wins}</span>
        <span className={styles.kpiCaption}>Tổng lệnh thắng</span>
      </div>

      <div className={styles.kpiCell}>
        <span className={styles.kpiLabel}>Losses</span>
        <span className={`${styles.kpiValue} ${styles.loss}`}>{losses}</span>
        <span className={styles.kpiCaption}>Tổng lệnh thua</span>
      </div>

      <div className={styles.kpiCell}>
        <span className={styles.kpiLabel}>Total Profit</span>
        <span className={`${styles.kpiValue} ${profitAbs >= 0 ? styles.gain : styles.loss}`}>
          {profitAbs >= 0 ? "+" : ""}{profitAbs.toFixed(2)}<em>USD</em>
        </span>
        <span className={`${styles.kpiCaption} ${profitPct >= 0 ? styles.gain : styles.loss}`}>
          {profitPct >= 0 ? "+" : ""}{profitPct.toFixed(2)}%
        </span>
        <span className={styles.equityLabel}>Equity Curve</span>
        <span className={styles.kpiSpark}>
          <Sparkline points={equity.map((point) => point.equity)} rising={profitPct >= 0} isMock={isMock} />
        </span>
      </div>

      <div className={styles.kpiCell}>
        <span className={styles.kpiLabel}>Max Drawdown</span>
        <span className={`${styles.kpiValue} ${styles.loss}`}>
          {drawdownPct.toFixed(2)}<em>%</em>
        </span>
        <span className={`${styles.kpiCaption} ${styles.loss}`}>{drawdownPct.toFixed(2)}%</span>
        <span className={styles.kpiSpark}>
          <Sparkline points={equity.map((point) => point.drawdown_pct)} rising={false} isMock={isMock} />
        </span>
      </div>

      <div className={styles.kpiCell}>
        <span className={styles.kpiLabel}>Total Trades</span>
        <span className={styles.kpiValue}>{totalTrades}</span>
        <span className={styles.kpiCaption}>100%</span>
        <span className={styles.kpiSpark}>
          <Bars count={totalTrades > 0 ? 9 : 0} />
        </span>
      </div>

      <div className={styles.kpiCell}>
        <span className={styles.kpiLabel}>Profit Factor</span>
        <span className={styles.kpiValue}>{profitFactor.toFixed(2)}</span>
        <span className={styles.kpiCaption}>Gross profit / gross loss</span>
      </div>

      <div className={styles.kpiCell}>
        <span className={styles.kpiLabel}>Sharpe Ratio</span>
        <span className={styles.kpiValue}>{sharpeRatio.toFixed(2)}</span>
        <span className={styles.kpiCaption}>Risk-adjusted return</span>
      </div>
    </div>
  );
}

function Donut({ ratio }: { ratio: number }) {
  const circumference = 2 * Math.PI * 15;
  return (
    <svg viewBox="0 0 40 40" role="img" aria-label={`Tỉ lệ thắng ${Math.round(ratio * 100)}%`}>
      <circle cx="20" cy="20" r="15" fill="none" stroke="var(--line-2)" strokeWidth="9" />
      <circle
        cx="20"
        cy="20"
        r="15"
        fill="none"
        stroke="var(--data-up)"
        strokeWidth="9"
        strokeDasharray={circumference}
        strokeDashoffset={circumference * (1 - ratio)}
        transform="rotate(-90 20 20)"
      />
    </svg>
  );
}

/* Reference mode keeps its illustrative curve. Live runs with no result remain
   flat instead of suggesting a performance path that never happened. */
function Sparkline({ points, rising, isMock }: { points: number[]; rising: boolean; isMock: boolean }) {
  const series = isMock ? illustrative(rising) : points.length < 2 ? [0, 0] : points;
  const min = Math.min(...series);
  const max = Math.max(...series);
  const span = max - min || 1;
  const path = series
    .map((value, index) => {
      const x = (index / (series.length - 1)) * 100;
      const y = 30 - ((value - min) / span) * 26;
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
  const stroke = rising ? "var(--data-up)" : "var(--data-down)";
  const fill = rising ? "rgba(21, 146, 100, 0.12)" : "rgba(209, 70, 91, 0.12)";
  return (
    <svg viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true">
      <path d={`${path} L100 32 L0 32 Z`} fill={fill} stroke="none" />
      <path d={path} fill="none" stroke={stroke} strokeWidth="1.4" />
    </svg>
  );
}

function illustrative(rising: boolean): number[] {
  const base = [0, 1.2, 0.8, 2.1, 1.7, 3.2, 2.8, 4.6, 4.1, 6.0, 5.4, 7.2, 6.8, 8.4];
  return rising ? base : base.map((value) => -value);
}

function Bars({ count }: { count: number }) {
  const heights = [0.35, 0.55, 0.42, 0.7, 0.5, 0.85, 0.62, 1, 0.75];
  return (
    <svg viewBox={`0 0 ${count * 8} 32`} preserveAspectRatio="none" aria-hidden="true">
      {Array.from({ length: count }, (_, index) => {
        const height = (heights[index % heights.length] ?? 0.5) * 28;
        return <rect key={index} x={index * 8 + 1} y={30 - height} width="5" height={height} rx="1.4" fill="var(--ink-3)" opacity="0.55" />;
      })}
    </svg>
  );
}
