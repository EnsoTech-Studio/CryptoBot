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
  { href: "/strategies", icon: "strategy", label: "Strategy Engine", available: false },
  { href: "/search", icon: "discovery", label: "Discovery", available: true, aliases: ["/leaderboard"] },
  { href: "/backtests", icon: "chart", label: "Backtest", available: true },
  { href: "/news", icon: "document", label: "News Crawler", available: true },
  { href: "/settings", icon: "settings", label: "Settings", available: false },
];

export function isActiveRoute(pathname: string, item: NavigationItem) {
  if (item.href === "/") return pathname === "/";
  return [item.href, ...(item.aliases ?? [])].some((href) => pathname === href || pathname.startsWith(`${href}/`));
}

export function pageMeta(pathname: string): { title: string; subtitle: string } {
  if (pathname === "/") {
    return {
      title: "Realtime Chart – Đa khung thời gian",
      subtitle: "",
    };
  }
  if (pathname.startsWith("/backtests")) {
    return {
      title: "Backtest & Kết quả giao dịch",
      subtitle: "Chọn coin, thời gian test, vốn, strategy và đánh giá hiệu quả",
    };
  }
  if (pathname.startsWith("/search")) {
    return {
      title: "Strategy Engine & Loop Discovery",
      subtitle: "Tạo strategy kết hợp và tự động tìm biến thể có kết quả tốt nhất",
    };
  }
  if (pathname.startsWith("/leaderboard")) {
    return {
      title: "Bảng xếp hạng Strategy",
      subtitle: "So sánh các strategy từ kết quả backtest đã được xác minh",
    };
  }
  if (pathname.startsWith("/news")) {
    return {
      title: "News Crawler & Phân tích thị trường",
      subtitle: "Thu thập tin tức, quản lý nguồn và phân tích sentiment",
    };
  }
  return {
    title: "Crypto Strategy Lab",
    subtitle: "Không gian nghiên cứu và mô phỏng chiến lược giao dịch",
  };
}
