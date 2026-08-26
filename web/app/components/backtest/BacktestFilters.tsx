"use client";

import { PAGE_SIZES, STRATEGY_PRESETS, type BacktestDraft } from "../../../lib/backtest";
import { marketKey } from "../../../lib/market";
import type { MarketPair } from "../../../lib/api";
import { Field, Select, TextInput } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./backtest.module.css";

/* The eight-control filter strip. Every control writes into the draft that
   BacktestScreen submits, so nothing here is decorative. */
export function BacktestFilters({
  draft,
  pairs,
  timeframes,
  disabled,
  onChange,
}: {
  draft: BacktestDraft;
  pairs: MarketPair[];
  timeframes: string[];
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
        </Field>
      </div>

      <Field label="Timeframe">
        <Select value={draft.timeframe} disabled={disabled} onChange={(event) => onChange({ timeframe: event.target.value })}>
          {timeframes.map((timeframe) => (
            <option key={timeframe} value={timeframe}>{timeframe}</option>
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

      <Field label="Strategy">
        <Select value={draft.strategyId} disabled={disabled} onChange={(event) => onChange({ strategyId: event.target.value })}>
          {STRATEGY_PRESETS.map((preset) => (
            <option key={preset.id} value={preset.id}>{preset.label}</option>
          ))}
        </Select>
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
        <span>
          <Icon name="calendar" aria-hidden="true" />
          <TextInput type="date" value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)} />
        </span>
      </Field>
    </div>
  );
}

export { PAGE_SIZES };
