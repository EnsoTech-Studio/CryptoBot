"use client";

import { LEADERBOARD_MOCK, type MockLeaderRow } from "../../../lib/discovery-mock";
import { shortLabel } from "../../../lib/discovery";
import type { DiscoveryArchive, LeaderboardEntry, SearchRun } from "../../../lib/api";
import { Button, Panel } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./discovery.module.css";

/* Column 3, middle. Real entries win whenever the API returns any; the mock
   rows only fill the reference layout on a cold database.

   The reference column reads "Profit (USDT)". The API returns
   total_return_pct and never the run's starting equity, so a real row shows
   Return (%) with the header switched — no fabricated USDT figure. */
export function DiscoveryLeaderboard({
  entries,
  archive,
  run,
  archiveState,
  referenceMode,
  onRefresh,
  onTrace,
}: {
  entries: LeaderboardEntry[];
  archive: DiscoveryArchive | null;
  run: SearchRun | null;
  archiveState: "idle" | "loading" | "ready" | "unavailable";
  referenceMode: boolean;
  onRefresh: () => void;
  onTrace: (id: string) => void;
}) {
  const archiveRows = archive
    ? [...archive.candidates]
        .sort((left, right) => (right.score ?? -Infinity) - (left.score ?? -Infinity))
    : [];
  const discoveryRun = run?.generator_id === "discovery";
  const live = !discoveryRun && entries.length > 0;
  const showMock = referenceMode && !discoveryRun && !live;
  const archiveMessage = archiveState === "unavailable"
    ? "Không tải được Discovery archive."
    : archiveState === "loading"
      ? "Đang tải Discovery archive…"
      : "Chưa có assessment từ Discovery loop.";

  return (
    <Panel
      title={discoveryRun ? "Discovery archive" : "Leaderboard (Top strategies)"}
      action={
        <Button variant="ghost" onClick={onRefresh} aria-label="Làm mới leaderboard">
          <Icon name="refresh" aria-hidden="true" />
        </Button>
      }
    >
      <table className={styles.leaderTable}>
        <thead>
          <tr>
            <th>Rank</th>
            <th>Strategy</th>
            <th>{showMock || live ? (showMock ? "Profit (USDT)" : "Return (%)") : "Score"}</th>
            <th>{discoveryRun ? "State / Winrate" : "Winrate"}</th>
          </tr>
        </thead>
        <tbody>
          {discoveryRun
            ? archiveRows.length > 0
              ? archiveRows.slice(0, 5).map((candidate, index) => (
                  <tr key={candidate.candidate_id}>
                    <RankCell rank={index + 1} />
                    <td><PartList parts={candidateParts(candidate.candidate_definition)} /></td>
                    <td className={`${styles.profitCell} ${(candidate.score ?? 0) < 0 ? styles.profitNegative : ""}`}>
                      {candidate.score === null ? "—" : `${candidate.score >= 0 ? "+" : ""}${candidate.score.toFixed(4)}`}
                    </td>
                    <td className={styles.winrateCell}>
                      <span>{candidateState(candidate.accepted, candidate.lineage)}</span>
                      <small>{validationWinRate(candidate.assessment)}</small>
                    </td>
                  </tr>
                ))
              : <tr><td className={styles.leaderEmpty} colSpan={4}>{archiveMessage}</td></tr>
            : live
              ? entries.slice(0, 5).map((entry) => (
                  <tr key={entry.id}>
                    <RankCell rank={entry.rank} />
                    <td>
                      <PartList parts={[shortLabel(entry.strategy_id)]} />
                    </td>
                    <td className={`${styles.profitCell} ${entry.total_return_pct < 0 ? styles.profitNegative : ""}`}>
                      {entry.total_return_pct >= 0 ? "+" : ""}
                      {entry.total_return_pct.toFixed(2)}%
                    </td>
                    <td className={styles.winrateCell}>{entry.win_rate_pct.toFixed(2)}%</td>
                  </tr>
                ))
              : showMock
                ? LEADERBOARD_MOCK.map((row) => <MockRow key={row.rank} row={row} />)
                : <tr><td className={styles.leaderEmpty} colSpan={4}>Chưa có kết quả Discovery.</td></tr>}
        </tbody>
      </table>
      {live ? (
        <div className={styles.runActions}>
          <Button variant="ghost" onClick={() => onTrace(entries[0].id)}>
            Provenance top 1
          </Button>
        </div>
      ) : null}
    </Panel>
  );
}

function candidateState(accepted: boolean | null, lineage: Record<string, unknown>): string {
  if (accepted === true) return "Accepted";
  if (accepted === false) return "Rejected";
  const phase = String(lineage.phase ?? "queued");
  return phase === "validation" ? "Validating" : phase === "train" ? "Training" : "Queued";
}

function candidateParts(definition: Record<string, unknown>): string[] {
  if (definition.strategy_id === "composite" && Array.isArray(definition.children)) {
    return definition.children
      .filter((child): child is Record<string, unknown> => Boolean(child) && typeof child === "object")
      .map((child) => shortLabel(String(child.strategy_id ?? "unknown")));
  }
  return [shortLabel(String(definition.strategy_id ?? "unknown"))];
}

function validationWinRate(assessment: Record<string, unknown> | null): string {
  const metrics = assessment?.validation_metrics;
  if (!Array.isArray(metrics) || metrics.length === 0) return "Winrate —";
  const values = metrics
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item) => Number(item.win_rate_pct))
    .filter((value) => Number.isFinite(value));
  if (values.length === 0) return "Winrate —";
  const average = values.reduce((sum, value) => sum + value, 0) / values.length;
  return `Winrate ${average.toFixed(2)}%`;
}

function MockRow({ row }: { row: MockLeaderRow }) {
  return (
    <tr>
      <RankCell rank={row.rank} />
      <td>
        <PartList parts={row.parts} />
      </td>
      <td className={styles.profitCell}>+{row.profitUsdt.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
      <td className={styles.winrateCell}>{row.winratePct.toFixed(2)}%</td>
    </tr>
  );
}

/* Medals carry a number as well as a colour, so rank survives greyscale and
   screen readers. */
function RankCell({ rank }: { rank: number }) {
  const medal = rank === 1 ? styles.medalGold : rank === 2 ? styles.medalSilver : rank === 3 ? styles.medalBronze : null;
  return (
    <td className={styles.rankCell}>
      {medal ? (
        <span className={`${styles.medal} ${medal}`}>
          {rank === 1 ? <Icon name="trophy" aria-hidden="true" /> : rank}
          <span className="sr-only">Hạng {rank}</span>
        </span>
      ) : (
        <span className={styles.rankPlain}>{rank}</span>
      )}
    </td>
  );
}

function PartList({ parts }: { parts: string[] }) {
  return (
    <span className={styles.partList}>
      {parts.map((part, index) => (
        <span key={`${part}-${index}`} className={styles.partList}>
          {index > 0 ? <b className={styles.partPlus}>+</b> : null}
          <em className={partTone(part)}>{part}</em>
        </span>
      ))}
    </span>
  );
}

function partTone(part: string) {
  switch (part) {
    case "MA":
    case "EMA":
      return styles.partBrand;
    case "RSI":
      return styles.partViolet;
    case "Bollinger":
      return styles.partGreen;
    case "S/R":
      return styles.partAmber;
    default:
      return styles.partNeutral;
  }
}
