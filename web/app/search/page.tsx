"use client";

import { SearchPanel } from "../components/Operations";
import { LeaderboardPanel } from "../components/LeaderboardPanel";

export default function SearchPage() {
  return (
    <>
      <section className="operation-grid single">
        <SearchPanel />
      </section>
      <LeaderboardPanel />
    </>
  );
}
