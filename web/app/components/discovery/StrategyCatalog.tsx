"use client";

import Link from "next/link";

import { CATALOG_MOCK, type CatalogEntry } from "../../../lib/discovery-mock";
import type { Strategy } from "../../../lib/api";
import { Icon } from "../ui/Icon";
import { Panel } from "../ui/Foundation";
import styles from "./discovery.module.css";

export function StrategyCatalog({
  strategies,
  referenceMode,
  selectedIds,
  onToggle,
  registryIds,
}: {
  strategies: Strategy[];
  referenceMode: boolean;
  selectedIds: string[];
  onToggle: (strategyId: string) => void;
  registryIds: Set<string>;
}) {
  const entries = referenceMode ? CATALOG_MOCK : strategies
    .filter((strategy) => !strategy.is_composite)
    .map(catalogEntryFor);
  return (
    <Panel
      title="Strategy đơn"
      info="Danh sách strategy đơn dùng làm thành phần cho strategy kết hợp."
      className={styles.tallPanel}
    >
      <div className={styles.catalogList}>
        {entries.length > 0 ? entries.map((entry, index) => (
          <CatalogRow
            key={entry.strategyId ?? `${entry.label}-${index}`}
            entry={entry}
            selected={entry.strategyId ? selectedIds.includes(entry.strategyId) : false}
            available={Boolean(entry.strategyId && registryIds.has(entry.strategyId))}
            onToggle={onToggle}
          />
        )) : <p className={styles.catalogEmpty}>Chưa có strategy nào trong registry.</p>}
      </div>

      <div className={styles.catalogFooter}>
        <Link href="/strategies" className={styles.createButton}>
          <Icon name="plus" aria-hidden="true" />
          Tạo strategy đơn mới
        </Link>
      </div>
    </Panel>
  );
}

function catalogEntryFor(strategy: Strategy): CatalogEntry {
  const icon = strategy.strategy_id === "rsi" ? "activity"
    : strategy.strategy_id === "bollinger" ? "bollinger"
    : strategy.strategy_id === "support_resistance" ? "support-resistance"
    : strategy.strategy_id === "ma_cross" || strategy.strategy_id === "ema_cross" ? "ma"
    : strategy.strategy_id === "macd" ? "chart"
    : "candles";
  const tone = strategy.family === "trend" ? "brand"
    : strategy.family === "momentum" || strategy.family === "information" ? "violet"
    : strategy.family === "volatility" ? "green"
    : strategy.family === "structure" ? "amber"
    : "neutral";
  return {
    strategyId: strategy.strategy_id,
    label: strategy.display_name,
    description: strategy.description || "Chưa có mô tả strategy.",
    icon,
    tone,
  };
}

function CatalogRow({
  entry,
  selected,
  available,
  onToggle,
}: {
  entry: CatalogEntry;
  selected: boolean;
  available: boolean;
  onToggle: (strategyId: string) => void;
}) {
  const toneClass = styles[`icon${entry.tone[0].toUpperCase()}${entry.tone.slice(1)}`] ?? "";
  return (
    <button
      type="button"
      className={styles.catalogRow}
      aria-pressed={selected}
      disabled={!available}
      title={available ? undefined : `${entry.label} chưa có trong strategy registry`}
      onClick={() => entry.strategyId && onToggle(entry.strategyId)}
    >
      <span className={`${styles.catalogIcon} ${toneClass}`}>
        <Icon name={entry.icon} aria-hidden="true" />
      </span>
      <span className={styles.catalogCopy}>
        <strong>{entry.label}</strong>
        <span>{entry.description}</span>
      </span>
      <span className={styles.catalogChevron} aria-hidden="true">
        <Icon name="chevron-right" />
      </span>
    </button>
  );
}
