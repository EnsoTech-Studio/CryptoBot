"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { NewsSource } from "../../../lib/api";
import { ASSET_PRESETS, REFRESH_OPTIONS } from "../../../lib/news-mock";
import { Button, Field, Select } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./news.module.css";

export function NewsControls({
  asset,
  refreshMinutes,
  onAsset,
  onRefresh,
  sources,
  selectedSourceIds,
  sourcesState,
  onToggleSource,
  onToggleAllSources,
  onAnalyze,
  analyzeBusy,
}: {
  asset: string;
  refreshMinutes: number;
  onAsset: (asset: string) => void;
  onRefresh: (minutes: number) => void;
  sources: NewsSource[];
  selectedSourceIds: string[];
  sourcesState: "loading" | "ready" | "error";
  onToggleSource: (sourceId: string) => void;
  onToggleAllSources: () => void;
  onAnalyze: () => void;
  analyzeBusy: boolean;
}) {
  const [sourceMenuOpen, setSourceMenuOpen] = useState(false);
  const pickerRef = useRef<HTMLDivElement>(null);
  const selected = useMemo(() => new Set(selectedSourceIds), [selectedSourceIds]);
  const allSelected = sources.length > 0 && selectedSourceIds.length === sources.length;
  const sourceLabel = sourceSelectLabel(sources, selectedSourceIds, sourcesState);
  const sourceMenuDisabled = sourcesState !== "ready" || sources.length === 0;

  useEffect(() => {
    if (!sourceMenuOpen) return;
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!pickerRef.current?.contains(event.target as Node)) setSourceMenuOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSourceMenuOpen(false);
    };
    window.addEventListener("mousedown", closeOnOutsideClick);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("mousedown", closeOnOutsideClick);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [sourceMenuOpen]);

  return (
    <div className={styles.controlStrip}>
      <Field label="Pair (Asset)">
        <Select value={asset} onChange={(event) => onAsset(event.target.value)}>
          {ASSET_PRESETS.map((preset) => (
            <option key={preset} value={preset}>
              {preset}
            </option>
          ))}
        </Select>
      </Field>

      <Field label="Auto refresh">
        <div
          className={styles.refreshGroup}
          role="group"
          aria-label="Chu kỳ tự động làm mới"
        >
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

      <div className={styles.sourceField}>
        <span className={styles.sourceFieldLabel}>Nguồn tin cần phân tích</span>
        <div ref={pickerRef} className={styles.sourcePicker}>
          <button
            type="button"
            className={styles.sourceSelectButton}
            aria-haspopup="listbox"
            aria-expanded={sourceMenuOpen}
            disabled={sourceMenuDisabled}
            onClick={() => setSourceMenuOpen((open) => !open)}
          >
            <span>{sourceLabel}</span>
            <Icon name="chevron-down" aria-hidden="true" />
          </button>

          {sourceMenuOpen ? (
            <div className={styles.sourceMenu} role="listbox" aria-label="Chọn nguồn phân tích">
              <label className={`${styles.sourceOption} ${styles.sourceBulkOption}`}>
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={onToggleAllSources}
                />
                <span className={styles.sourceMeta}>
                  <b>{allSelected ? "Bỏ chọn tất cả" : "Chọn tất cả"}</b>
                  <em>{sources.length} nguồn đang bật</em>
                </span>
              </label>

              {sources.map((source) => (
                <label key={source.id} className={styles.sourceOption}>
                  <input
                    type="checkbox"
                    checked={selected.has(source.id)}
                    onChange={() => onToggleSource(source.id)}
                  />
                  <span className={styles.sourceMeta}>
                    <b>{source.display_name}</b>
                    <em>{source.kind.toUpperCase()}</em>
                  </span>
                </label>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      <div className={styles.stripActions}>
        <Button
          variant="primary"
          onClick={onAnalyze}
          disabled={
            analyzeBusy ||
            selectedSourceIds.length === 0 ||
            sourcesState !== "ready"
          }
        >
          <Icon name="play" aria-hidden="true" />
          {analyzeBusy ? "Đang phân tích..." : "Phân tích"}
        </Button>
      </div>
    </div>
  );
}

function sourceSelectLabel(
  sources: NewsSource[],
  selectedSourceIds: string[],
  state: "loading" | "ready" | "error",
) {
  if (state === "loading") return "Đang tải nguồn...";
  if (state === "error") return "Không tải được nguồn";
  if (sources.length === 0) return "Chưa có nguồn";
  if (selectedSourceIds.length === 0) return "Chọn nguồn";
  if (selectedSourceIds.length === sources.length) return "Tất cả nguồn";

  const selected = new Set(selectedSourceIds);
  const first = sources.find((source) => selected.has(source.id));
  if (!first) return "Chọn nguồn";
  return selectedSourceIds.length === 1
    ? first.display_name
    : `${first.display_name} +${selectedSourceIds.length - 1}`;
}
