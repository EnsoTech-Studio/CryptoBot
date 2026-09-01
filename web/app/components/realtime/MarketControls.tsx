"use client";

import { marketDisplayName, marketKey } from "../../../lib/market";
import { dataSourceLabel } from "../../../lib/data-mode";
import { useWorkspace } from "../../providers/workspace";
import { StatusDot, Toggle } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./realtime.module.css";

export function MarketControls() {
  const {
    marketPairs,
    marketPairsState,
    selectedMarket,
    selectMarket,
    retryMarketPairs,
    availableTimeframes,
    panels,
    focusIndex,
    setFocusIndex,
    realtimeEnabled,
    setRealtimeEnabled,
    streamLabel,
    dataMode,
  } = useWorkspace();
  const selectedKey = marketKey(selectedMarket);
  const pairOptions = marketPairs.length > 0
    ? marketPairs
    : [{ ...selectedMarket, base_asset: selectedMarket.symbol, quote_asset: "", timeframes: availableTimeframes }];

  return (
    <div className={styles.controls}>
      <label className={styles.controlGroup}>
        <span className={styles.controlLabel}>Pair / Coin</span>
        <span className={styles.selectWrap}>
          <span className={styles.coinBadge} aria-hidden="true">₿</span>
          <select
            value={selectedKey}
            disabled={marketPairs.length === 0}
            onChange={(event) => {
              const next = marketPairs.find((pair) => marketKey(pair) === event.target.value);
              if (next) selectMarket(next);
            }}
            aria-describedby={marketPairsState === "unavailable" ? "pair-catalog-error" : undefined}
          >
            {pairOptions.map((pair) => (
              <option key={marketKey(pair)} value={marketKey(pair)}>{marketDisplayName(pair)}</option>
            ))}
          </select>
          <Icon name="chevron-down" aria-hidden="true" />
        </span>
      </label>

      <div className={`${styles.controlGroup} ${styles.timeframeGroup}`}>
        <span className={styles.controlLabel}>Khung thời gian</span>
        <div className={styles.timeframes} role="tablist" aria-label="Khung thời gian biểu đồ">
          {["1m", "5m", "15m", "1h", "4h"]
            .filter((timeframe) => availableTimeframes.includes(timeframe))
            .map((timeframe) => {
              const panelIndex = panels.findIndex((panel) => panel.timeframe === timeframe);
              const active = focusIndex === panelIndex;
              return (
                <button
                  key={timeframe}
                  type="button"
                  className={active ? styles.timeframeActive : undefined}
                  role="tab"
                  aria-selected={active}
                  onClick={() => setFocusIndex(panelIndex >= 0 ? panelIndex : 0)}
                >
                  {timeframe}
                </button>
              );
            })}
        </div>
      </div>

      <div className={`${styles.controlGroup} ${styles.realtimeControl}`}>
        <span className={styles.controlLabel}>Realtime</span>
        <div className={styles.realtimeRow}>
          <Toggle checked={realtimeEnabled} label="Realtime" onChange={setRealtimeEnabled} />
          <button
            type="button"
            className={styles.connectionBadge}
            data-state={streamLabel.toLowerCase()}
            disabled={dataMode !== "mock" || marketPairsState === "loading"}
            onClick={() => void retryMarketPairs()}
            title={dataMode === "mock" ? "Thử kết nối lại market backend" : undefined}
          >
            <StatusDot tone={streamLabel === "Live" || streamLabel === "Mock" ? "live" : streamLabel === "Syncing" ? "syncing" : streamLabel === "Paused" ? "neutral" : "error"} />
            {marketPairsState === "loading" ? "Đang thử kết nối" : !realtimeEnabled ? "Đã tạm dừng" : dataMode === "mock" ? dataSourceLabel(dataMode) : streamLabel === "Live" ? "Đang nhận dữ liệu" : streamLabel}
          </button>
        </div>
      </div>

      {marketPairsState === "unavailable" ? (
        <div className={styles.catalogError} id="pair-catalog-error" role="status">
          <span>Không tải được danh sách pair.</span>
          <button type="button" onClick={() => void retryMarketPairs()}>
            <Icon name="refresh" /> Thử lại
          </button>
        </div>
      ) : null}
    </div>
  );
}
