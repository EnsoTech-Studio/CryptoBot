"use client";

import { ASSET_PRESETS, REFRESH_OPTIONS, SOURCE_MODES, type SourceMode } from "../../../lib/news-mock";
import { Button, Field, Select } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./news.module.css";

/* The API remains the source of truth for real crawling. The local mock keeps
   every control interactive so the complete reference screen is inspectable. */
export function NewsControls({
  mode,
  asset,
  refreshMinutes,
  onMode,
  onAsset,
  onRefresh,
  onCrawl,
}: {
  mode: SourceMode;
  asset: string;
  refreshMinutes: number;
  onMode: (mode: SourceMode) => void;
  onAsset: (asset: string) => void;
  onRefresh: (minutes: number) => void;
  onCrawl: () => void;
}) {
  return (
    <div className={styles.controlStrip}>
      <Field label="Nguồn">
        <div className={styles.modeGroup} role="group" aria-label="Chế độ nguồn tin">
          {SOURCE_MODES.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`${styles.modeButton} ${mode === option.value ? styles.modeActive : ""} ${option.value === "rss" ? styles.modeRss : option.value === "html" ? styles.modeHtml : ""}`}
              aria-pressed={mode === option.value}
              onClick={() => onMode(option.value)}
            >
              <Icon name={option.icon} aria-hidden="true" />
              {option.label}
            </button>
          ))}
        </div>
      </Field>

      <Field label="Pair (Asset)">
        <Select value={asset} onChange={(event) => onAsset(event.target.value)}>
          {ASSET_PRESETS.map((preset) => (
            <option key={preset} value={preset}>{preset}</option>
          ))}
        </Select>
      </Field>

      <Field label="Auto refresh">
        <div className={styles.refreshGroup} role="group" aria-label="Chu kỳ tự động làm mới">
          {REFRESH_OPTIONS.map((minutes) => (
            <button
              key={minutes}
              type="button"
              className={refreshMinutes === minutes ? styles.refreshActive : ""}
              aria-pressed={refreshMinutes === minutes}
              onClick={() => onRefresh(minutes)}
            >
              {minutes} phút
            </button>
          ))}
        </div>
      </Field>

      <span />

      <div className={styles.stripActions}>
        <Button
          variant="secondary"
        >
          <Icon name="settings" aria-hidden="true" />
          Cấu hình nguồn
        </Button>
        <Button
          variant="primary"
          onClick={onCrawl}
        >
          <Icon name="play" aria-hidden="true" />
          Bắt đầu crawl
        </Button>
      </div>
    </div>
  );
}
