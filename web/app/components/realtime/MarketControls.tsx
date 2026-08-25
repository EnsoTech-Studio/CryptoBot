"use client";

import { marketKey } from "../../../lib/market";
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
    panelHandlers,
    realtimeEnabled,
    setRealtimeEnabled,
    streamLabel,
  } = useWorkspace();
  const selectedKey = marketKey(selectedMarket);
  const activeTimeframe = panels[focusIndex]?.timeframe ?? availableTimeframes[0];
  const pairOptions = marketPairs.length > 0
    ? marketPairs
    : [{ ...selectedMarket, base_asset: selectedMarket.symbol, quote_asset: "", timeframes: availableTimeframes }];

  function chooseTimeframe(timeframe: string) {
    const existingIndex = panels.findIndex((panel) => panel.timeframe === timeframe);
    if (existingIndex >= 0) {
      setFocusIndex(existingIndex);
      return;
    }
    panelHandlers(focusIndex).onTimeframe(timeframe);
  }

  return (
    <div className={styles.controls}>
      <label className={styles.controlGroup}>
        <span className={styles.controlLabel}>Pair / Coin</span>
        <span className={styles.selectWrap}>
          <select
            value={selectedKey}
            disabled={marketPairsState !== "ready" || marketPairs.length === 0}
            onChange={(event) => {
              const next = marketPairs.find((pair) => marketKey(pair) === event.target.value);
              if (next) selectMarket(next);
            }}
            aria-describedby={marketPairsState === "unavailable" ? "pair-catalog-error" : undefined}
          >
            {pairOptions.map((pair) => (
              <option key={marketKey(pair)} value={marketKey(pair)}>{pair.symbol}</option>
            ))}
          </select>
          <Icon name="chevron-down" aria-hidden="true" />
        </span>
      </label>

      <div className={`${styles.controlGroup} ${styles.timeframeGroup}`}>
        <span className={styles.controlLabel}>Khung thời gian</span>
        <div className={styles.timeframes} role="group" aria-label="Chọn khung thời gian đang tập trung">
          {availableTimeframes.map((timeframe) => (
            <button
              key={timeframe}
              type="button"
              className={activeTimeframe === timeframe ? styles.timeframeActive : ""}
              aria-pressed={activeTimeframe === timeframe}
              onClick={() => chooseTimeframe(timeframe)}
            >
              {timeframe}
            </button>
          ))}
        </div>
      </div>

      <div className={`${styles.controlGroup} ${styles.realtimeControl}`}>
        <span className={styles.controlLabel}>Cập nhật thị trường</span>
        <div className={styles.realtimeRow}>
          <Toggle checked={realtimeEnabled} label="Realtime" onChange={setRealtimeEnabled} />
          <span className={styles.connectionBadge} data-state={streamLabel.toLowerCase()}>
            <StatusDot tone={streamLabel === "Live" ? "live" : streamLabel === "Syncing" ? "syncing" : streamLabel === "Paused" ? "neutral" : "error"} />
            {streamLabel}
          </span>
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
