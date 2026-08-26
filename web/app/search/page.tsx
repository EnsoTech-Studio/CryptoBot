import { redirect } from "next/navigation";

/* Old links and bookmarks keep working; Discovery now owns this workspace. */
export default function SearchPage() {
  redirect("/discovery");
}
