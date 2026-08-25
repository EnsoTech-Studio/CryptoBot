"use client";

import type { ReactNode } from "react";

import { WorkspaceProvider, useWorkspace } from "./providers/workspace";
import { InstrumentHeader } from "./components/InstrumentHeader";
import { Inspector } from "./components/Inspector";
import { LeftRail } from "./components/LeftRail";

/* One shell for every route. The provider sits above it, so navigating between
   pages keeps the market sockets, polls and inspector state alive. */
export function WorkspaceShell({ children }: { children: ReactNode }) {
  return (
    <WorkspaceProvider>
      <Shell>{children}</Shell>
    </WorkspaceProvider>
  );
}

function Shell({ children }: { children: ReactNode }) {
  const { inspectorOpen } = useWorkspace();
  return (
    <div className={`terminal-shell ${inspectorOpen ? "has-inspector" : ""}`}>
      <a className="skip-link" href="#workspace-main">Skip to content</a>
      <LeftRail />
      <section className="terminal-main" id="workspace-main">
        <InstrumentHeader />
        {children}
      </section>
      <Inspector />
    </div>
  );
}
