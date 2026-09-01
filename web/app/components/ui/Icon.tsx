import type { SVGProps } from "react";

export type IconName =
  | "activity"
  | "arrow-down"
  | "arrow-up"
  | "bar-chart"
  | "bitcoin"
  | "bollinger"
  | "bell"
  | "calendar"
  | "candles"
  | "chart"
  | "check"
  | "check-circle"
  | "chevron-down"
  | "chevron-left"
  | "chevron-right"
  | "clock"
  | "close"
  | "code"
  | "coins"
  | "copy"
  | "dice"
  | "discovery"
  | "dna"
  | "dollar"
  | "download"
  | "document"
  | "expand"
  | "ethereum"
  | "flask"
  | "globe"
  | "graduation"
  | "help"
  | "info"
  | "link"
  | "ma"
  | "menu"
  | "minus"
  | "more-vertical"
  | "percent"
  | "play"
  | "plus"
  | "refresh"
  | "rss"
  | "save"
  | "scale"
  | "solana"
  | "support-resistance"
  | "settings"
  | "shield"
  | "sliders"
  | "strategy"
  | "target"
  | "trash"
  | "trophy"
  | "user"
  | "wand"
  | "wyckoff";

type IconProps = Omit<SVGProps<SVGSVGElement>, "children"> & {
  name: IconName;
  title?: string;
};

export function Icon({ name, title, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      {...props}
    >
      {title ? <title>{title}</title> : null}
      <IconPaths name={name} />
    </svg>
  );
}

function IconPaths({ name }: { name: IconName }) {
  switch (name) {
    case "activity":
      return <path d="M3 12h4l2.1-6 4.2 12 2.2-6H21" />;
    case "arrow-down":
      return <><path d="M12 5v14" /><path d="m6 13 6 6 6-6" /></>;
    case "arrow-up":
      return <><path d="M12 19V5" /><path d="m6 11 6-6 6 6" /></>;
    case "bar-chart":
      return <><path d="M5 20v-6M10 20V8M15 20v-9M20 20V5" /></>;
    case "bitcoin":
      return <><circle cx="12" cy="12" r="8.5" /><path d="M10 6.5v11M14 6.5v11M8 9h5.2a2.5 2.5 0 0 1 0 5H8h5.5a2.5 2.5 0 0 1 0 5H8" /></>;
    case "bollinger":
      return <><path d="M3 6h5M16 6h5M3 12h18M3 18h5M16 18h5" /><circle cx="12" cy="12" r="3.2" /></>;
    case "bell":
      return <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>;
    case "calendar":
      return <><rect x="3.5" y="5" width="17" height="15.5" rx="2.2" /><path d="M3.5 10h17M8.5 3v4M15.5 3v4" /></>;
    case "candles":
      return <><path d="M7 4v3.5M7 16.5V20M17 3v4.5M17 15.5V21" /><rect x="4.6" y="7.5" width="4.8" height="9" rx="1" /><rect x="14.6" y="7.5" width="4.8" height="8" rx="1" /></>;
    case "chart":
      return <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /><path d="m4 8 6-5 6 7 5-5" /></>;
    case "check":
      return <path d="m5 12.5 4.6 4.5L19 7.5" />;
    case "check-circle":
      return <><circle cx="12" cy="12" r="9" /><path d="m8 12.2 2.7 2.6L16 9.5" /></>;
    case "chevron-down":
      return <path d="m7 9.5 5 5 5-5" />;
    case "chevron-left":
      return <path d="m14 7-5 5 5 5" />;
    case "chevron-right":
      return <path d="m10 7 5 5-5 5" />;
    case "clock":
      return <><circle cx="12" cy="12" r="9" /><path d="M12 7.5V12l3.4 2" /></>;
    case "close":
      return <><path d="m6 6 12 12" /><path d="m18 6-12 12" /></>;
    case "code":
      return <><path d="m9 8-4 4 4 4" /><path d="m15 8 4 4-4 4" /></>;
    case "coins":
      return <><ellipse cx="8.5" cy="7" rx="5.5" ry="2.6" /><path d="M3 7v4.2c0 1.4 2.5 2.6 5.5 2.6s5.5-1.2 5.5-2.6V7" /><path d="M14 10.4c3 .2 5.5 1.4 5.5 2.7v4.2c0 1.5-2.5 2.7-5.5 2.7s-5.5-1.2-5.5-2.7v-2.7" /></>;
    case "copy":
      return <><rect x="9" y="9" width="11.5" height="11.5" rx="2.2" /><path d="M15 6.2A2.2 2.2 0 0 0 12.8 4H5.7A2.2 2.2 0 0 0 3.5 6.2v7.1A2.2 2.2 0 0 0 5.7 15.5" /></>;
    case "dice":
      return <><rect x="3.5" y="3.5" width="17" height="17" rx="3" /><circle cx="8.5" cy="8.5" r=".9" fill="currentColor" stroke="none" /><circle cx="15.5" cy="15.5" r=".9" fill="currentColor" stroke="none" /><circle cx="12" cy="12" r=".9" fill="currentColor" stroke="none" /></>;
    case "discovery":
      return <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /><path d="m9 13 2-5 2 5-2-1Z" /></>;
    case "dna":
      return <><path d="M6 3c0 6 12 6 12 12 0 3-1.4 5-3 6" /><path d="M18 3c0 6-12 6-12 12 0 3 1.4 5 3 6" /><path d="M8.2 7h7.6M7 11h10M8.2 15.5h7.6" /></>;
    case "dollar":
      return <><path d="M12 3.5v17" /><path d="M16 7.5a3.4 3.4 0 0 0-3.4-2.2h-1.2a3.1 3.1 0 0 0-.6 6.1l2.6.5a3.2 3.2 0 0 1-.6 6.3h-1.2A3.5 3.5 0 0 1 8 16" /></>;
    case "download":
      return <><path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M5 21h14" /></>;
    case "document":
      return <><path d="M6 2h8l4 4v16H6Z" /><path d="M14 2v5h5M9 12h6M9 16h6" /></>;
    case "expand":
      return <><path d="M9 4H4v5M20 9V4h-5M15 20h5v-5M4 15v5h5" /></>;
    case "ethereum":
      return <><path d="m12 3-5 9 5 3 5-3Z" /><path d="m7 13 5 8 5-8-5 3Z" /></>;
    case "flask":
      return <><path d="M9 3h6M10 3v6l-5 8.5A2.3 2.3 0 0 0 7 21h10a2.3 2.3 0 0 0 2-3.5L14 9V3" /><path d="M7.6 16h8.8" /><circle cx="10" cy="18" r=".65" fill="currentColor" stroke="none" /><circle cx="14.5" cy="14" r=".65" fill="currentColor" stroke="none" /></>;
    case "globe":
      return <><circle cx="12" cy="12" r="9" /><path d="M3.2 9.5h17.6M3.2 14.5h17.6" /><path d="M12 3c-2.4 2.4-3.6 5.4-3.6 9s1.2 6.6 3.6 9c2.4-2.4 3.6-5.4 3.6-9s-1.2-6.6-3.6-9Z" /></>;
    case "graduation":
      return <><path d="m2 9 10-5 10 5-10 5Z" /><path d="M6 11.2V16c2.8 2.1 9.2 2.1 12 0v-4.8M22 9v6" /></>;
    case "help":
      return <><circle cx="12" cy="12" r="9" /><path d="M9.8 9a2.4 2.4 0 1 1 3.5 2.1c-.9.5-1.3 1-1.3 2" /><path d="M12 17h.01" /></>;
    case "info":
      return <><circle cx="12" cy="12" r="9" /><path d="M12 11v6" /><path d="M12 7h.01" /></>;
    case "link":
      return <><path d="M10 13.8a4.2 4.2 0 0 0 6 0l2.6-2.6a4.2 4.2 0 0 0-6-6l-1.3 1.3" /><path d="M14 10.2a4.2 4.2 0 0 0-6 0L5.4 12.8a4.2 4.2 0 0 0 6 6l1.3-1.3" /></>;
    case "ma":
      return <><path d="M3 17c3-5 5-9 8-6s4 8 10-4" /><path d="M3 9c3 3 5 5 8 2s5-5 10-2" /></>;
    case "menu":
      return <><path d="M4 7h16M4 12h16M4 17h16" /></>;
    case "minus":
      return <path d="M6 12h12" />;
    case "more-vertical":
      return <><circle cx="12" cy="5.5" r="1.1" fill="currentColor" stroke="none" /><circle cx="12" cy="12" r="1.1" fill="currentColor" stroke="none" /><circle cx="12" cy="18.5" r="1.1" fill="currentColor" stroke="none" /></>;
    case "percent":
      return <><path d="m5.5 18.5 13-13" /><circle cx="7.5" cy="7.5" r="2.4" /><circle cx="16.5" cy="16.5" r="2.4" /></>;
    case "play":
      return <path d="M8 5.5v13l10.5-6.5Z" />;
    case "plus":
      return <><path d="M12 5.5v13" /><path d="M5.5 12h13" /></>;
    case "refresh":
      return <><path d="M20 7v5h-5" /><path d="M4 17v-5h5" /><path d="M6.1 9a7 7 0 0 1 11.4-2.6L20 9M4 15l2.5 2.6A7 7 0 0 0 17.9 15" /></>;
    case "rss":
      return <><path d="M5 11.5a7.5 7.5 0 0 1 7.5 7.5M5 6a13 13 0 0 1 13 13" /><circle cx="5.6" cy="18.4" r="1.4" fill="currentColor" stroke="none" /></>;
    case "save":
      return <><path d="M5.2 4h10.3L20 8.5V20H5.2A1.2 1.2 0 0 1 4 18.8V5.2A1.2 1.2 0 0 1 5.2 4Z" /><path d="M8 4v5h7M8 20v-5.5h8V20" /></>;
    case "scale":
      return <><path d="M12 4v16M6 20h12" /><path d="M4 8h16M6.5 8 4 13.5h5ZM17.5 8 15 13.5h5Z" /></>;
    case "support-resistance":
      return <><path d="M3 7h18M3 12h18M3 17h18" /><path d="M7 5v4M17 10v4M11 15v4" /></>;
    case "solana":
      return <><path d="M5 6h13l-3 3H2Z" /><path d="M8 11h13l-3 3H5Z" /><path d="M5 16h13l-3 3H2Z" /></>;
    case "settings":
      return <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" /></>;
    case "shield":
      return <><path d="M12 3 5 5.8v5.4c0 4.3 2.9 7.8 7 9.8 4.1-2 7-5.5 7-9.8V5.8Z" /><path d="m9 12 2.2 2.2L15.3 10" /></>;
    case "sliders":
      return <><path d="M4 7h10M18 7h2M4 17h4M12 17h8" /><circle cx="16" cy="7" r="2.1" /><circle cx="10" cy="17" r="2.1" /></>;
    case "strategy":
      return <><circle cx="6" cy="6" r="2" /><circle cx="18" cy="6" r="2" /><circle cx="12" cy="18" r="2" /><path d="m7.7 7.1 3.2 8.9M16.3 7.1 13.1 16M8 6h8" /></>;
    case "target":
      return <><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4.6" /><circle cx="12" cy="12" r=".9" fill="currentColor" stroke="none" /></>;
    case "trash":
      return <><path d="M4.5 7h15M9.5 7V4.8h5V7M6.5 7l.8 12.2A1.6 1.6 0 0 0 8.9 20.7h6.2a1.6 1.6 0 0 0 1.6-1.5L17.5 7" /><path d="M10.5 11v6M13.5 11v6" /></>;
    case "trophy":
      return <><path d="M8 4h8v5.2a4 4 0 0 1-8 0Z" /><path d="M8 5.5H5.4v1.6A3.2 3.2 0 0 0 8.4 10M16 5.5h2.6v1.6a3.2 3.2 0 0 1-3 2.9" /><path d="M12 13.2V17M8.6 20h6.8M9.8 20l.5-3h3.4l.5 3" /></>;
    case "user":
      return <><circle cx="12" cy="8" r="4" /><path d="M4.8 21a7.2 7.2 0 0 1 14.4 0" /></>;
    case "wand":
      return <><path d="m5 19 9.5-9.5" /><path d="m17 3 .8 2.2L20 6l-2.2.8L17 9l-.8-2.2L14 6l2.2-.8L17 3Z" /><path d="m8 4 .5 1.5L10 6l-1.5.5L8 8l-.5-1.5L6 6l1.5-.5L8 4Z" /><path d="m19 13 .4 1.1 1.1.4-1.1.4L19 16l-.4-1.1-1.1-.4 1.1-.4L19 13Z" /></>;
    case "wyckoff":
      return <><rect x="3.5" y="5" width="7" height="8" rx="1" /><rect x="13.5" y="11" width="7" height="8" rx="1" /><path d="m10.5 9 3 4M7 13v4M17 5v6" /></>;
    default:
      return null;
  }
}
