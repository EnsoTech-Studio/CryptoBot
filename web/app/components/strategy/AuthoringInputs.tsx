"use client";

import { PROMPT_LIMIT, URL_HINT } from "../../../lib/strategy-authoring";
import { Button, Panel, PlannedNotice, TextInput } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./strategy.module.css";

/* Column 1. Analyze and extract stay disabled: there is no
   POST /api/v1/strategy-authoring/* endpoint, and plan 02 forbids simulating a
   successful analysis. Typing and clearing work so the input is still real. */
export function AuthoringInputs({
  prompt,
  url,
  onPrompt,
  onUrl,
}: {
  prompt: string;
  url: string;
  onPrompt: (value: string) => void;
  onUrl: (value: string) => void;
}) {
  return (
    <>
      <Panel title="Nhập mô tả strategy" info="Mô tả chiến lược bằng ngôn ngữ tự nhiên.">
        <textarea
          className={styles.promptArea}
          value={prompt}
          maxLength={PROMPT_LIMIT}
          aria-label="Mô tả strategy"
          onChange={(event) => onPrompt(event.target.value)}
        />
        <span className={styles.promptCount}>{prompt.length}/{PROMPT_LIMIT}</span>
        <div className={styles.promptActions}>
          <Button
            variant="primary"
            disabled
            title="Phân tích prompt cần endpoint POST /api/v1/strategy-authoring/analyze"
          >
            <Icon name="wand" aria-hidden="true" />
            Phân tích bằng LLM
          </Button>
          <Button variant="secondary" onClick={() => onPrompt("")}>
            <Icon name="trash" aria-hidden="true" />
            Xóa
          </Button>
        </div>
      </Panel>

      <Panel title="Nhập URL chiến lược" info="Trích xuất định nghĩa strategy từ một trang web công khai.">
        <span className={styles.urlField}>
          <Icon name="link" aria-hidden="true" />
          <TextInput
            type="url"
            value={url}
            aria-label="URL chiến lược"
            onChange={(event) => onUrl(event.target.value)}
          />
        </span>
        <p className={styles.urlHint}>{URL_HINT}</p>
        <button
          type="button"
          className={styles.extractButton}
          disabled
          title="Trích xuất cần endpoint server-side có kiểm soát SSRF và giới hạn nội dung"
        >
          <Icon name="globe" aria-hidden="true" />
          Trích xuất từ website
        </button>
        <PlannedNotice>
          Trích xuất từ URL phải chạy phía server với allowlist và chống SSRF. Chưa có contract nên nút đang tắt.
        </PlannedNotice>
      </Panel>
    </>
  );
}
