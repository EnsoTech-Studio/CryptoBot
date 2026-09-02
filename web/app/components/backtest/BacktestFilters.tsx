"use client";

import { PAGE_SIZES, type BacktestDraft, type BacktestMode } from "../../../lib/backtest";
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
  datasets,
  disabled,
  onChange,
}: {
  draft: BacktestDraft;
  pairs: MarketPair[];
  timeframes: string[];
  strategies: Strategy[];
  datasets: MarketDataset[];
  disabled: boolean;
  onChange: (patch: Partial<BacktestDraft>) => void;
}) {
  const pairOptions = pairs.length > 0
    ? pairs
    : [{ ...draft.market, base_asset: draft.market.symbol, quote_asset: "", timeframes }];

  return (
    <div className={styles.filterStrip}>
      <div className={styles.coinField}>
        <Field label="Pair / Coin">
          <span className={styles.coinControl}>
            <span className={styles.coinBadge} aria-hidden="true">₿</span>
            <Select
              value={marketKey(draft.market)}
              disabled={disabled || pairs.length === 0}
              onChange={(event) => {
                const next = pairs.find((pair) => marketKey(pair) === event.target.value);
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
          disabled={disabled || datasets.length === 0}
          onChange={(event) => onChange({ datasetVersion: event.target.value })}
        >
          {datasets.length === 0 ? <option value="">Đang tải dataset…</option> : null}
          {datasets.map((dataset) => (
            <option key={dataset.dataset_version} value={dataset.dataset_version}>
              {dataset.dataset_version} · {dataset.candle_count.toLocaleString("en-US")} nến
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
      ) : (
        <Field label="Composite strategies" hint="Chọn từ 2 strategy; trọng số chia đều khi gửi.">
          <div className={styles.strategyChecks}>
            {strategies.map((strategy) => (
              <label key={strategy.strategy_id} className={styles.strategyCheck}>
                <input
                  type="checkbox"
                  checked={draft.selectedStrategyIds.includes(strategy.strategy_id)}
                  disabled={disabled}
                  onChange={(event) => onChange({
                    selectedStrategyIds: event.target.checked
                      ? [...new Set([...draft.selectedStrategyIds, strategy.strategy_id])]
                      : draft.selectedStrategyIds.filter((id) => id !== strategy.strategy_id),
                  })}
                />
                <span>{strategy.display_name}</span>
              </label>
            ))}
          </div>
        </Field>
      )}

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
  );
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
