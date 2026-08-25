import type { SVGProps } from "react";

export type IconName =
  | "activity"
  | "bell"
  | "chart"
  | "chevron-down"
  | "close"
  | "discovery"
  | "download"
  | "document"
  | "flask"
  | "graduation"
  | "help"
  | "info"
  | "menu"
  | "refresh"
  | "settings"
  | "strategy"
  | "user";

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
    case "bell":
      return <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>;
    case "chart":
      return <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /><path d="m4 8 6-5 6 7 5-5" /></>;
    case "chevron-down":
      return <path d="m7 9.5 5 5 5-5" />;
    case "close":
      return <><path d="m6 6 12 12" /><path d="m18 6-12 12" /></>;
    case "discovery":
      return <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /><path d="m9 13 2-5 2 5-2-1Z" /></>;
    case "download":
      return <><path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M5 21h14" /></>;
    case "document":
      return <><path d="M6 2h8l4 4v16H6Z" /><path d="M14 2v5h5M9 12h6M9 16h6" /></>;
    case "flask":
      return <><path d="M9 3h6M10 3v6l-5 8.5A2.3 2.3 0 0 0 7 21h10a2.3 2.3 0 0 0 2-3.5L14 9V3" /><path d="M7.6 16h8.8" /><circle cx="10" cy="18" r=".65" fill="currentColor" stroke="none" /><circle cx="14.5" cy="14" r=".65" fill="currentColor" stroke="none" /></>;
    case "graduation":
      return <><path d="m2 9 10-5 10 5-10 5Z" /><path d="M6 11.2V16c2.8 2.1 9.2 2.1 12 0v-4.8M22 9v6" /></>;
    case "help":
      return <><circle cx="12" cy="12" r="9" /><path d="M9.8 9a2.4 2.4 0 1 1 3.5 2.1c-.9.5-1.3 1-1.3 2" /><path d="M12 17h.01" /></>;
    case "info":
      return <><circle cx="12" cy="12" r="9" /><path d="M12 11v6" /><path d="M12 7h.01" /></>;
    case "menu":
      return <><path d="M4 7h16M4 12h16M4 17h16" /></>;
    case "refresh":
      return <><path d="M20 7v5h-5" /><path d="M4 17v-5h5" /><path d="M6.1 9a7 7 0 0 1 11.4-2.6L20 9M4 15l2.5 2.6A7 7 0 0 0 17.9 15" /></>;
    case "settings":
      return <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" /></>;
    case "strategy":
      return <><circle cx="6" cy="6" r="2" /><circle cx="18" cy="6" r="2" /><circle cx="12" cy="18" r="2" /><path d="m7.7 7.1 3.2 8.9M16.3 7.1 13.1 16M8 6h8" /></>;
    case "user":
      return <><circle cx="12" cy="8" r="4" /><path d="M4.8 21a7.2 7.2 0 0 1 14.4 0" /></>;
    default:
      return null;
  }
}
