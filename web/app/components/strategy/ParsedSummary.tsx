"use client";

import { useState, type ReactNode } from "react";

import { DEFINITION_JSON } from "../../../lib/strategy-authoring";
import type { StrategySpec } from "../../../lib/api";
import { Panel } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./strategy.module.css";

/* Strategy definition panel. Copy is a real browser capability, so it works. */
export function DefinitionJson({ spec }: { spec: StrategySpec | null }) {
  const [copied, setCopied] = useState(false);
  const definition = spec ? JSON.stringify(spec, null, 2) : DEFINITION_JSON;

  async function copy() {
    try {
      await navigator.clipboard.writeText(definition);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1_600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <Panel
      title="Định nghĩa strategy (JSON)"
      className={styles.jsonPanel}
      action={
        <button type="button" className={styles.copyButton} onClick={() => void copy()}>
          <Icon name={copied ? "check" : "copy"} aria-hidden="true" />
          {copied ? "Đã sao chép" : "Sao chép"}
        </button>
      }
    >
      <pre className={styles.jsonBlock}>{highlightJson(definition)}</pre>
    </Panel>
  );
}

function highlightJson(value: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const tokenPattern = /("(?:\\.|[^"\\])*")|(-?\d+(?:\.\d+)?)/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = tokenPattern.exec(value))) {
    if (match.index > cursor) nodes.push(value.slice(cursor, match.index));
    const token = match[0];
    const isKey = token.startsWith('"') && value.slice(tokenPattern.lastIndex).trimStart().startsWith(":");
    nodes.push(
      <span key={`${match.index}-${token}`} className={isKey ? styles.jsonKey : token.startsWith('"') ? styles.jsonString : styles.jsonNumber}>
        {token}
      </span>,
    );
    cursor = tokenPattern.lastIndex;
  }

  if (cursor < value.length) nodes.push(value.slice(cursor));
  return nodes;
}
