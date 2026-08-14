"use client";

import { type ReactNode, useEffect, useRef } from "react";
import { TransportProvider } from "@/lib/stores/transport";
import { TimelineProvider } from "@/lib/stores/timeline";
import { WorkspaceProvider, useWorkspace } from "@/lib/stores/workspace";
import TransportBar from "./TransportBar";
import LibraryPanel from "./LibraryPanel";
import RepresentationStack from "./RepresentationStack";
import InspectorPanel from "./Inspector";

export type ServiceStatus = "checking" | "ready" | "unavailable";

function WorkspaceContent({ signedIn = false, projectName, serviceStatus }: { signedIn?: boolean; projectName?: string; serviceStatus: ServiceStatus }) {
  const { workspace, toggleLibrary } = useWorkspace();
  const initializedResponsiveLayout = useRef(false);

  useEffect(() => {
    if (initializedResponsiveLayout.current) return;
    initializedResponsiveLayout.current = true;
    if (!window.matchMedia("(max-width: 820px)").matches) return;
    if (!workspace.libraryCollapsed) toggleLibrary();
  }, [toggleLibrary, workspace.libraryCollapsed]);

  return (
    <div className="studio-shell"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        background: "var(--bg)",
        color: "var(--text)",
        fontFamily: "var(--font-sans)",
        overflow: "hidden",
      }}
    >
      <header className="studio-header">
        <div className="studio-title">
          <span className="brand"><span className="brand-dot" />{projectName || "Music Lab"}</span>
        </div>
      </header>

      <TransportBar />

      <div className="studio-workspace" style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <LibraryPanel signedIn={signedIn} canImport={serviceStatus === "ready"} />

        <RepresentationStack signedIn={signedIn} canImport={serviceStatus === "ready"} />

        {!workspace.inspectorCollapsed && <aside className="studio-inspector"><InspectorPanel /></aside>}

      </div>

    </div>
  );
}

export default function WorkspaceShell({
  signedIn = false,
  projectName,
  serviceStatus = "checking",
  children,
}: {
  signedIn?: boolean;
  projectName?: string;
  serviceStatus?: ServiceStatus;
  children?: ReactNode;
}) {
  return (
    <TimelineProvider>
      <TransportProvider>
        <WorkspaceProvider>
          {children}
          <WorkspaceContent signedIn={signedIn} projectName={projectName} serviceStatus={serviceStatus} />
        </WorkspaceProvider>
      </TransportProvider>
    </TimelineProvider>
  );
}
