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
  const { workspace, toggleLibrary, toggleInspector } = useWorkspace();
  const initializedResponsiveLayout = useRef(false);

  useEffect(() => {
    if (initializedResponsiveLayout.current) return;
    initializedResponsiveLayout.current = true;
    if (!window.matchMedia("(max-width: 820px)").matches) return;
    if (!workspace.libraryCollapsed) toggleLibrary();
  }, [toggleLibrary, workspace.libraryCollapsed]);

  const inspectorOpen = !workspace.inspectorCollapsed;
  const hasWork = Boolean(workspace.activeWorkId);

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
        <div className="studio-header-left">
          <span className="brand"><span className="brand-dot" />{projectName || "Music Lab"}</span>
        </div>
        <div className="studio-header-right">
          {hasWork && (
            <button
              type="button"
              className={`studio-inspector-btn ${inspectorOpen ? "active" : ""}`}
              aria-label={inspectorOpen ? "Hide analysis" : "Show analysis"}
              aria-pressed={inspectorOpen}
              onClick={toggleInspector}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.5" />
                <line x1="10.5" y1="10.5" x2="14" y2="14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
          )}
          <button className="icon-btn ghost" onClick={toggleLibrary} title={workspace.libraryCollapsed ? "Show library" : "Hide library"}>
            {workspace.libraryCollapsed ? "▸" : "◂"}
          </button>
        </div>
      </header>

      <div className="studio-workspace" style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <LibraryPanel signedIn={signedIn} canImport={serviceStatus === "ready"} />

        <div className="studio-canvas-area">
          <RepresentationStack signedIn={signedIn} canImport={serviceStatus === "ready"} />
        </div>

        {inspectorOpen && (
          <>
            <aside className="studio-inspector"><InspectorPanel /></aside>
            <div className="studio-inspector-backdrop" onClick={toggleInspector} aria-hidden="true" />
          </>
        )}
      </div>

      <TransportBar />
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
