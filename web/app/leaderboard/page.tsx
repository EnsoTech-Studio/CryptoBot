import { redirect } from "next/navigation";

/* The leaderboard is a section of Discovery now, not its own screen. */
export default function LeaderboardPage() {
  redirect("/discovery");
}
