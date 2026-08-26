"use client";

import { LEADERBOARD_MOCK, type MockLeaderRow } from "../../../lib/discovery-mock";
import { shortLabel } from "../../../lib/discovery";
import type { LeaderboardEntry } from "../../../lib/api";
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
  onRefresh,
  onTrace,
}: {
  entries: LeaderboardEntry[];
  onRefresh: () => void;
  onTrace: (id: string) => void;
}) {
  const live = entries.length > 0;

  return (
    <Panel
      title="Leaderboard (Top strategies)"
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
              <th>{live ? "Return (%)" : "Profit (USDT)"}</th>
              <th>Winrate</th>
            </tr>
          </thead>
          <tbody>
            {live
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
              : LEADERBOARD_MOCK.map((row) => <MockRow key={row.rank} row={row} />)}
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
