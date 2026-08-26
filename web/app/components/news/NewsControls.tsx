"use client";

import { ASSET_PRESETS, REFRESH_OPTIONS, SOURCE_MODES, type SourceMode } from "../../../lib/news-mock";
import { Button, Field, Select } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./news.module.css";

/* Control strip. Website and HTML are visibly disabled: research only accepts
   `kind: "rss"` (app/schemas.py NewsSourceCreateIn), so offering them would be
   a lie. Crawl and source config need admin proxies that Go does not expose
   yet, so both are disabled with an explanatory title. */
export function NewsControls({
  mode,
  asset,
  refreshMinutes,
  isAdmin,
  onMode,
  onAsset,
  onRefresh,
  onCrawl,
}: {
  mode: SourceMode;
  asset: string;
  refreshMinutes: number;
  isAdmin: boolean;
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
              disabled={!option.supported}
              title={option.supported ? undefined : `${option.label} chưa được backend hỗ trợ (chỉ RSS)`}
              onClick={() => option.supported && onMode(option.value)}
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
          disabled
          title="Cấu hình nguồn cần endpoint quản trị GET/POST /api/v1/admin/news-sources qua Go API"
        >
          <Icon name="settings" aria-hidden="true" />
          Cấu hình nguồn
        </Button>
        <Button
          variant="primary"
          disabled={!isAdmin}
          title={isAdmin ? undefined : "Bắt đầu crawl cần quyền ADMIN và endpoint POST /api/v1/admin/news/collect qua Go API"}
          onClick={onCrawl}
        >
          <Icon name="play" aria-hidden="true" />
          Bắt đầu crawl
        </Button>
      </div>
    </div>
  );
}
