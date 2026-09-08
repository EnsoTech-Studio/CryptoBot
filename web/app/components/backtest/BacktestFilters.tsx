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
  canDeleteStrategies,
  deletingStrategyId,
  onDeleteStrategy,
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
  canDeleteStrategies: boolean;
  deletingStrategyId: string | null;
  onDeleteStrategy: (strategyId: string) => Promise<void>;
}) {
  const pairOptions = pairs.length > 0
    ? pairOptionsByVenue(pairs, draft.market)
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
                <option key={marketKey(pair)} value={marketKey(pair)}>{pair.symbol} · {providerLabel(pair.provider)}</option>
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
          <StrategyLibraryPicker
            mode="single"
            strategies={strategies}
            selectedStrategyIds={draft.strategyId ? [draft.strategyId] : []}
            disabled={disabled}
            canDeleteStrategies={canDeleteStrategies}
            deletingStrategyId={deletingStrategyId}
            onChange={(strategyId) => onChange({ strategyId: String(strategyId) })}
            onDeleteStrategy={onDeleteStrategy}
          />
        </Field>
      ) : (
        <Field label="Strategy kết hợp" hint="Chọn strategy đã lưu hoặc tổ hợp được chuyển từ Discovery.">
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
            <option value="">
              Tổ hợp demo · {draft.selectedStrategyIds
                .map((id) => strategies.find((strategy) => strategy.strategy_id === id)?.display_name ?? id)
                .join(" + ") || "Đang chuẩn bị strategy"}
            </option>
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
      )}

      <div className={styles.executionField}>
        <span className={styles.executionFieldLabel}>Execution settings</span>
        <details className={styles.executionDetails}>
          <summary>Mở cài đặt</summary>
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
    </div>
  );
}

function StrategyLibraryPicker({
  mode,
  strategies,
  selectedStrategyIds,
  disabled,
  canDeleteStrategies,
  deletingStrategyId,
  onChange,
  onDeleteStrategy,
}: {
  mode: BacktestMode;
  strategies: Strategy[];
  selectedStrategyIds: string[];
  disabled: boolean;
  canDeleteStrategies: boolean;
  deletingStrategyId: string | null;
  onChange: (value: string | string[]) => void;
  onDeleteStrategy: (strategyId: string) => Promise<void>;
}) {
  const selectedLabels = selectedStrategyIds.map((strategyId) =>
    strategies.find((strategy) => strategy.strategy_id === strategyId)?.strategy_id ?? strategyId,
  );
  const summary = mode === "single"
    ? selectedLabels[0] ?? "Chọn strategy"
    : selectedLabels.length > 0
      ? `${selectedLabels.length} strategy được chọn`
      : "Chọn strategy";

  return (
    <details className={styles.strategyPicker}>
      <summary aria-disabled={disabled || strategies.length === 0}>{summary}</summary>
      <div className={styles.strategyChecks} aria-label="Danh sách strategy trong registry">
        {strategies.map((strategy) => {
          const selected = selectedStrategyIds.includes(strategy.strategy_id);
          const canDelete = canDeleteStrategies && strategy.strategy_id.startsWith("generated.");
          const deleting = deletingStrategyId === strategy.strategy_id;
          return (
            <div className={styles.strategyOption} key={strategy.strategy_id}>
              <label className={styles.strategyCheck}>
                <input
                  type={mode === "single" ? "radio" : "checkbox"}
                  name={mode === "single" ? "backtest-strategy" : undefined}
                  checked={selected}
                  disabled={disabled || deleting}
                  onChange={() => {
                    if (mode === "single") {
                      onChange(strategy.strategy_id);
                      return;
                    }
                    onChange(selected
                      ? selectedStrategyIds.filter((id) => id !== strategy.strategy_id)
                      : [...selectedStrategyIds, strategy.strategy_id]);
                  }}
                />
                <span>
                  <strong>{strategy.strategy_id}</strong>
                  <small>{strategy.display_name}</small>
                </span>
              </label>
              {canDelete ? (
                <button
                  type="button"
                  className={styles.deleteStrategyButton}
                  disabled={disabled || deleting}
                  aria-label={`Xóa hẳn strategy ${strategy.strategy_id}`}
                  title="Xóa strategy khỏi registry"
                  onClick={() => {
                    if (window.confirm(`Xóa hẳn strategy ${strategy.strategy_id} khỏi registry? Thao tác này không thể hoàn tác.`)) {
                      void onDeleteStrategy(strategy.strategy_id);
                    }
                  }}
                >
                  <Icon name="trash" />
                </button>
              ) : null}
            </div>
          );
        })}
      </div>
    </details>
  );
}

/* Dataset snapshots are scoped to an exchange as well as a symbol. Showing
   each venue prevents an incomplete live capture on one venue from hiding a
   runnable snapshot for the same coin on another. */
function pairOptionsByVenue(pairs: MarketPair[], selected: BacktestDraft["market"]) {
  return [...pairs]
    .sort((left, right) => {
      const leftSelected = marketKey(left) === marketKey(selected);
      const rightSelected = marketKey(right) === marketKey(selected);
      if (leftSelected !== rightSelected) return leftSelected ? -1 : 1;
      return `${left.symbol}|${left.provider}`.localeCompare(`${right.symbol}|${right.provider}`);
    });
}

function providerLabel(provider: string) {
  switch (provider) {
    case "binance_usdm": return "Binance USD-M";
    case "okx_swap": return "OKX Swap";
    default: return provider;
  }
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
