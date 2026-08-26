import type { IconName } from "../ui/Icon";

export type NavigationItem = {
  href: string;
  icon: IconName;
  label: string;
  available: boolean;
  aliases?: string[];
};

export const navigationItems: NavigationItem[] = [
  { href: "/", icon: "activity", label: "Realtime", available: true },
  { href: "/strategies", icon: "strategy", label: "Strategy Engine", available: true },
  { href: "/discovery", icon: "discovery", label: "Discovery", available: true, aliases: ["/search", "/leaderboard"] },
  { href: "/backtests", icon: "chart", label: "Backtest", available: true },
  { href: "/news", icon: "document", label: "News Crawler", available: true },
  { href: "/settings", icon: "settings", label: "Settings", available: false },
];

export function isActiveRoute(pathname: string, item: NavigationItem) {
  if (item.href === "/") return pathname === "/";
  return [item.href, ...(item.aliases ?? [])].some((href) => pathname === href || pathname.startsWith(`${href}/`));
}

/* Titles and subtitles are copied verbatim from the five reference images. */
export function pageMeta(pathname: string): { title: string; subtitle: string } {
  if (pathname === "/") {
    return {
      title: "Realtime Chart – Đa khung thời gian",
      subtitle: "",
    };
  }
  if (pathname.startsWith("/strategies")) {
    return {
      title: "Tạo Strategy từ Prompt / URL",
      subtitle: "Người dùng nhập ngôn ngữ tự nhiên hoặc link website để hệ thống sinh strategy và lưu vào thư viện",
    };
  }
  if (pathname.startsWith("/backtests")) {
    return {
      title: "Backtest & Kết quả giao dịch",
      subtitle: "Chọn coin, thời gian test, vốn, strategy và đánh giá hiệu quả",
    };
  }
  if (pathname.startsWith("/discovery") || pathname.startsWith("/search") || pathname.startsWith("/leaderboard")) {
    return {
      title: "Strategy Engine & Loop Discovery",
      subtitle: "Tạo strategy đơn, strategy kết hợp và tự động tìm biến thể tốt nhất",
    };
  }
  if (pathname.startsWith("/news")) {
    return {
      title: "News Crawler & Phân tích thị trường",
      subtitle: "Thu thập tin tức, hiểu HTML bằng LLM, lưu template và phân tích sentiment",
    };
  }
  return {
    title: "Crypto Strategy Lab",
    subtitle: "Không gian nghiên cứu và mô phỏng chiến lược giao dịch",
  };
}
