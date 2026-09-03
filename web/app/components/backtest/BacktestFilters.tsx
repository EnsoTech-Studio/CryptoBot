"use client";

import { DISCOVERY_BACKTEST_COMPOSITE_ID, PAGE_SIZES, type BacktestDraft, type BacktestMode, type SavedCompositeStrategy } from "../../../lib/backtest";
import { marketKey } from "../../../lib/market";
import type { MarketDataset, MarketPair, Strategy } from "../../../lib/api";
import { Field, Select, TextInput } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./backtest.module.css";

/* The eight-control filter strip. Every control writes into the draft that
   BacktestScreen submits, so nothing here is decorative. */
export function BacktestFilters({
  draft,
  pairs,
  timeframes,
  strategies,
  savedComposites,
  datasets,
  datasetLoadState,
  disabled,
  onChange,
}: {
  draft: BacktestDraft;
  pairs: MarketPair[];
  timeframes: string[];
  strategies: Strategy[];
  savedComposites: SavedCompositeStrategy[];
  datasets: MarketDataset[];
  datasetLoadState: "loading" | "ready" | "empty" | "error";
  disabled: boolean;
  onChange: (patch: Partial<BacktestDraft>) => void;
}) {
  const pairOptions = pairs.length > 0
    ? dedupePairSymbols(pairs, draft.market)
    : [{ ...draft.market, base_asset: draft.market.symbol, quote_asset: "", timeframes }];
  const hasDiscoveryComposite = draft.selectedCompositeId === DISCOVERY_BACKTEST_COMPOSITE_ID
    && draft.selectedStrategyIds.length > 0;

  return (
    <div className={styles.filterStrip}>
      <div className={styles.coinField}>
        <Field label="Pair / Coin">
          <span className={styles.coinControl}>
            <span className={styles.coinBadge} aria-hidden="true">₿</span>
            <Select
              value={marketKey(draft.market)}
              disabled={disabled || pairOptions.length === 0}
              onChange={(event) => {
                const next = pairOptions.find((pair) => marketKey(pair) === event.target.value);
                if (next) onChange({ market: { provider: next.provider, symbol: next.symbol } });
              }}
            >
              {pairOptions.map((pair) => (
                <option key={marketKey(pair)} value={marketKey(pair)}>{pair.symbol}</option>
              ))}
            </Select>
          </span>
        </Field>
      </div>

      <Field label="Timeframe">
        <Select value={draft.timeframe} disabled={disabled} onChange={(event) => onChange({ timeframe: event.target.value })}>
          {timeframes.map((timeframe) => (
            <option key={timeframe} value={timeframe}>{timeframe}</option>
          ))}
        </Select>
      </Field>

      <Field label="Dataset lịch sử">
        <Select
          value={draft.datasetVersion}
          disabled={disabled || datasetLoadState !== "ready"}
          onChange={(event) => {
            const dataset = datasets.find((item) => item.dataset_version === event.target.value);
            onChange({
              datasetVersion: event.target.value,
              /* Selecting a snapshot also selects its legal date bounds.
                 The user can still narrow the range with From/To fields. */
              ...(dataset ? {
                rangeFrom: dataset.range_from.slice(0, 10),
                rangeTo: new Date(new Date(dataset.range_to).getTime() - 1).toISOString().slice(0, 10),
              } : {}),
            });
          }}
        >
          {datasets.length === 0 ? <option value="">
            {datasetLoadState === "loading" ? "Đang tải dataset…" : datasetLoadState === "empty" ? "Không có dataset cho timeframe này" : "Không tải được dataset"}
          </option> : null}
          {datasets.map((dataset) => (
            <option key={dataset.dataset_version} value={dataset.dataset_version}>
              {dataset.range_from.slice(0, 10)} → {dataset.range_to.slice(0, 10)} · {dataset.candle_count.toLocaleString("en-US")} nến · r{dataset.revision_no}
            </option>
          ))}
        </Select>
      </Field>

      <DateField
        label="From date"
        value={draft.rangeFrom}
        disabled={disabled}
        onChange={(rangeFrom) => onChange({ rangeFrom })}
      />
      <DateField
        label="To date"
        value={draft.rangeTo}
        disabled={disabled}
        onChange={(rangeTo) => onChange({ rangeTo })}
      />

      <Field label="Strategy mode">
        <Select
          value={draft.mode}
          disabled={disabled || strategies.length === 0}
          onChange={(event) => {
            const mode = event.target.value as BacktestMode;
            onChange({
              mode,
              selectedStrategyIds: mode === "composite" && draft.selectedStrategyIds.length < 2
                ? strategies.slice(0, 3).map((strategy) => strategy.strategy_id)
                : draft.selectedStrategyIds,
            });
          }}
        >
          <option value="single">Single strategy</option>
          <option value="composite">Composite strategy</option>
        </Select>
      </Field>

      {draft.mode === "single" ? (
        <Field label="Strategy">
          <Select value={draft.strategyId} disabled={disabled || strategies.length === 0} onChange={(event) => onChange({ strategyId: event.target.value })}>
            {strategies.map((strategy) => (
              <option key={strategy.strategy_id} value={strategy.strategy_id}>{strategy.display_name}</option>
            ))}
          </Select>
        </Field>
      ) : savedComposites.length > 0 || hasDiscoveryComposite ? (
        <Field label="Strategy kết hợp" hint="Chọn strategy đã lưu hoặc tự chọn từ registry.">
          <Select
            aria-label="Strategy kết hợp đã lưu"
            value={draft.selectedCompositeId ?? ""}
            disabled={disabled}
            onChange={(event) => {
              const selected = savedComposites.find((item) => item.id === event.target.value);
              onChange({
                selectedCompositeId: event.target.value,
                ...(selected ? { selectedStrategyIds: selected.children.map((child) => child.strategy_id) } : {}),
              });
            }}
          >
            <option value="">Tự chọn strategy</option>
            {hasDiscoveryComposite ? (
              <option value={DISCOVERY_BACKTEST_COMPOSITE_ID}>
                Discovery · {draft.selectedStrategyIds.map((id) => strategies.find((strategy) => strategy.strategy_id === id)?.display_name ?? id).join(" + ")}
              </option>
            ) : null}
            {savedComposites.map((composite) => (
              <option key={composite.id} value={composite.id}>{composite.displayName}</option>
            ))}
          </Select>
        </Field>
      ) : null}

      <details className={styles.executionDetails}>
        <summary>Execution settings</summary>
        <div className={styles.executionFields}>
          <Field label="Vốn (USD)">
            <TextInput
              type="number"
              min={1}
              step={1}
              suffix="USD"
              value={draft.initialEquity}
              disabled={disabled}
              onChange={(event) => onChange({ initialEquity: Number(event.target.value) })}
            />
          </Field>
          <Field label="Transaction Cost" hint="Phí giao dịch tính theo phần trăm; API nhận basis points.">
            <TextInput
              type="number"
              min={0}
              max={100}
              step={0.01}
              suffix="%"
              value={draft.feePercent}
              disabled={disabled}
              onChange={(event) => onChange({ feePercent: Number(event.target.value) })}
            />
          </Field>
          <Field label="Slippage">
            <TextInput
              type="number"
              min={0}
              max={10_000}
              step={1}
              suffix="bps"
              value={draft.slippageBps}
              disabled={disabled}
              onChange={(event) => onChange({ slippageBps: Number(event.target.value) })}
            />
          </Field>
        </div>
      </details>
    </div>
  );
}

/* Pair/Coin displays the tradable symbol, not the exchange venue. Keep one
   option per symbol so Binance/OKX rows do not look like duplicate coins;
   preserve the currently selected venue when it is already known. */
function dedupePairSymbols(pairs: MarketPair[], selected: BacktestDraft["market"]) {
  const bySymbol = new Map<string, MarketPair>();
  for (const pair of pairs) {
    const symbol = pair.symbol.toUpperCase();
    const current = bySymbol.get(symbol);
    if (!current || marketKey(pair) === marketKey(selected)) bySymbol.set(symbol, pair);
  }
  return [...bySymbol.values()];
}

function DateField({
  label,
  value,
  disabled,
  onChange,
}: {
  label: string;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <div className={styles.dateField}>
      <Field label={label}>
        <span className={styles.dateControl}>
          <Icon name="calendar" aria-hidden="true" />
          <TextInput type="date" value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)} />
        </span>
      </Field>
    </div>
  );
}

export { PAGE_SIZES };
