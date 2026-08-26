"use client";

import { QUICK_COMBOS } from "../../../lib/discovery-mock";
import { MAX_COMBINED, familyTone, shortLabel, type DiscoveryDraft } from "../../../lib/discovery";
import type { Strategy } from "../../../lib/api";
import { Button, Chip, Panel } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./discovery.module.css";

/* Column 2, upper half: selected chips plus the quick-combination shortcuts. */
export function CombinedStrategyBuilder({
  draft,
  strategies,
  onRemove,
  onApplyCombo,
}: {
  draft: DiscoveryDraft;
  strategies: Strategy[];
  onRemove: (strategyId: string) => void;
  onApplyCombo: (ids: string[]) => void;
}) {
  const activeCombo = QUICK_COMBOS.find(
    (combo) =>
      combo.ids.length === draft.selectedStrategyIds.length &&
      combo.ids.every((id) => draft.selectedStrategyIds.includes(id)),
  );

  return (
    <Panel title="Strategy kết hợp" info={`Kết hợp 2-${MAX_COMBINED} strategy đơn thành một strategy composite.`}>
      <span className={styles.subLabel}>Chọn các strategy để kết hợp</span>
      <div className={styles.chipField}>
        {draft.selectedStrategyIds.length === 0 ? (
          <span className={styles.chipPlaceholder}>Chọn strategy ở cột bên trái</span>
        ) : (
          draft.selectedStrategyIds.map((id) => (
            <Chip
              key={id}
              label={shortLabel(id)}
              tone={familyTone(strategies.find((item) => item.strategy_id === id)?.family)}
              onRemove={() => onRemove(id)}
            />
          ))
        )}
        <Icon name="chevron-down" aria-hidden="true" />
      </div>

      <span className={styles.subLabel}>Gợi ý kết hợp nhanh</span>
      <div className={styles.comboRow}>
        {QUICK_COMBOS.map((combo) => (
          <button
            key={combo.label}
            type="button"
            className={`${styles.comboButton} ${activeCombo?.label === combo.label ? styles.comboActive : ""}`}
            aria-pressed={activeCombo?.label === combo.label}
            onClick={() => onApplyCombo(combo.ids)}
          >
            {combo.label}
          </button>
        ))}
      </div>
    </Panel>
  );
}

/* Column 2, footer: the two primary actions from the reference. */
export function BuilderActions({
  canSubmit,
  onBacktest,
  onSave,
}: {
  canSubmit: boolean;
  onBacktest: () => void;
  onSave: () => void;
}) {
  return (
    <div className={styles.builderActions}>
      <Button variant="primary" disabled={!canSubmit} onClick={onSave}>
        Lưu strategy kết hợp
      </Button>
      <Button variant="secondary" disabled={!canSubmit} onClick={onBacktest}>
        <Icon name="play" aria-hidden="true" />
        Backtest ngay
      </Button>
    </div>
  );
}
