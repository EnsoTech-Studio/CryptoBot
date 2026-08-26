"use client";

import { CATALOG_MOCK, type CatalogEntry } from "../../../lib/discovery-mock";
import { Icon } from "../ui/Icon";
import { Panel } from "../ui/Foundation";
import styles from "./discovery.module.css";

/* Column 1. The six rows come from CATALOG_MOCK for reference parity; entries
   whose `strategyId` is null (SMC, Wyckoff) exist in the mockup but not in the
   registry, so they render and can be inspected but never enter a draft. */
export function StrategyCatalog({
  selectedIds,
  onToggle,
  registryIds,
}: {
  selectedIds: string[];
  onToggle: (strategyId: string) => void;
  registryIds: Set<string>;
}) {
  return (
    <Panel
      title="Strategy đơn"
      info="Danh sách strategy đơn dùng làm thành phần cho strategy kết hợp."
      className={styles.tallPanel}
    >
      <div className={styles.catalogList}>
        {CATALOG_MOCK.map((entry) => (
          <CatalogRow
            key={entry.label}
            entry={entry}
            selected={entry.strategyId ? selectedIds.includes(entry.strategyId) : false}
            available={Boolean(entry.strategyId && registryIds.has(entry.strategyId))}
            onToggle={onToggle}
          />
        ))}
      </div>

      <div className={styles.catalogFooter}>
        <button type="button" className={styles.createButton} disabled title="Tạo strategy đơn mới cần API authoring, sẽ mở ở màn Strategy Engine">
          <Icon name="plus" aria-hidden="true" />
          Tạo strategy đơn mới
        </button>
      </div>
    </Panel>
  );
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
