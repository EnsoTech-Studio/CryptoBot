"use client";

import { useMemo, useState } from "react";

import { formatNumber } from "../../lib/format";
import type { LeaderboardEntry } from "../../lib/api";
import { useWorkspace } from "../providers/workspace";
import { TableSkeleton, Unavailable } from "./States";

type SortKey = "rank" | "score" | "total_return_pct" | "max_drawdown_pct";
type SortDir = "asc" | "desc";

const COLUMNS: Array<{ key: SortKey; label: string; sortable: boolean }> = [
  { key: "rank", label: "Rank", sortable: true },
  { key: "score", label: "Score", sortable: true },
  { key: "total_return_pct", label: "Return", sortable: true },
  { key: "max_drawdown_pct", label: "MDD", sortable: true },
];

export function LeaderboardPanel() {
  const { leaderboard, leaderboardState, refreshStaticData, loadProvenance } = useWorkspace();
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({ key: "rank", dir: "asc" });

  const rows = useMemo(() => {
    const copy = [...leaderboard];
    copy.sort((a, b) => {
      const delta = a[sort.key] - b[sort.key];
      return sort.dir === "asc" ? delta : -delta;
    });
    return copy;
  }, [leaderboard, sort]);

  function toggleSort(key: SortKey) {
    setSort((current) => current.key === key
      ? { key, dir: current.dir === "asc" ? "desc" : "asc" }
      : { key, dir: key === "max_drawdown_pct" || key === "rank" ? "asc" : "desc" });
  }

  return (
    <section id="leaderboard" className="surface leaderboard">
      <div className="surface-head">
        <div>
          <p className="eyebrow">Leaderboard / verified results</p>
          <h2>Top-K strategy snapshots</h2>
          <p className="surface-subtitle">Ranked against one immutable dataset and evaluator.</p>
        </div>
        <button className="ghost-action" onClick={() => void refreshStaticData()}>Refresh</button>
      </div>

      {leaderboardState === "loading" ? (
        <TableSkeleton rows={6} cols={5} />
      ) : leaderboardState === "unavailable" ? (
        <Unavailable title="Leaderboard unavailable">
          The results service did not respond. This is not an empty board — retry once the API is reachable.
        </Unavailable>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {COLUMNS.map((col) => (
                  <th key={col.key} aria-sort={sort.key === col.key ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}>
                    {col.sortable ? (
                      <button type="button" className="sort-button" onClick={() => toggleSort(col.key)}>
                        {col.label}
                        <span className="sort-caret" aria-hidden="true">{sort.key === col.key ? (sort.dir === "asc" ? "↑" : "↓") : "↕"}</span>
                      </button>
                    ) : col.label}
                  </th>
                ))}
                <th>Strategy</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr><td colSpan={6} className="table-empty">No ranked snapshots yet. Start a search loop to populate the board.</td></tr>
              ) : rows.map((entry) => <LeaderboardRow key={entry.id} entry={entry} onTrace={() => void loadProvenance(entry.id)} />)}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function LeaderboardRow({ entry, onTrace }: { entry: LeaderboardEntry; onTrace: () => void }) {
  return (
    <tr>
      <td><span className="rank-number">{String(entry.rank).padStart(2, "0")}</span></td>
      <td>{formatNumber(entry.score)}</td>
      <td className={entry.total_return_pct >= 0 ? "positive" : "negative"}>{formatNumber(entry.total_return_pct)}%</td>
      <td>{formatNumber(entry.max_drawdown_pct)}%</td>
      <td><strong className="strategy-cell">{entry.strategy_id}</strong><span>{entry.candidate_hash.slice(0, 10)} · v{entry.strategy_version}</span></td>
      <td><button className="ghost-action table-action" onClick={onTrace}>Trace</button></td>
    </tr>
  );
}
