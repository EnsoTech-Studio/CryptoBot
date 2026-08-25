import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";

import "./globals.css";

import { WorkspaceShell } from "./WorkspaceShell";

export const metadata: Metadata = {
  title: "Crypto Strategy Lab",
  description:
    "Simulation-only research cockpit: live market structure, deterministic backtests, ranked candidates and provenance in one workspace.",
  applicationName: "Crypto Strategy Lab",
  openGraph: {
    title: "Crypto Strategy Lab",
    description:
      "Simulation-only research cockpit: live market structure, deterministic backtests, ranked candidates and provenance in one workspace.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#f7f8fc",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="vi" data-theme="light" data-scroll-behavior="smooth" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        <WorkspaceShell>{children}</WorkspaceShell>
      </body>
    </html>
  );
}
