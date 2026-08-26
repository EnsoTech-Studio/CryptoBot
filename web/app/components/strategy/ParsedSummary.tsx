"use client";

import { useState } from "react";

import { DEFINITION_JSON, PARSED_BLOCKS } from "../../../lib/strategy-authoring";
import { Panel } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./strategy.module.css";

/* Column 2. Illustrative parse of the sample prompt; a real analyze endpoint
   would replace these blocks wholesale. */
export function ParsedSummary() {
  return (
    <Panel title="Strategy đã phân tích" className={styles.parsedPanel}>
      <div className={styles.parsedList}>
        {PARSED_BLOCKS.map((block) => (
          <div key={block.title} className={`${styles.parsedBlock} ${styles[`block${block.tone[0].toUpperCase()}${block.tone.slice(1)}`]}`}>
            <span className={styles.parsedTitle}>
              <Icon name={block.icon} aria-hidden="true" />
              {block.title}
            </span>
            <ul className={styles.parsedLines}>
              {block.lines.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Panel>
  );
}

/* Column 3. Copy is a real browser capability, so it works. */
export function DefinitionJson() {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(DEFINITION_JSON);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1_600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <Panel
      title="Định nghĩa strategy (JSON)"
      action={
        <button type="button" className={styles.copyButton} onClick={() => void copy()}>
          <Icon name={copied ? "check" : "copy"} aria-hidden="true" />
          {copied ? "Đã sao chép" : "Sao chép"}
        </button>
      }
    >
      <pre className={styles.jsonBlock}>{DEFINITION_JSON}</pre>
    </Panel>
  );
}
