"use client";

import { type ReactNode, useEffect, useRef } from "react";
import { TransportProvider } from "@/lib/stores/transport";
import { SelectionProvider } from "@/lib/stores/selection";
import { TimelineProvider } from "@/lib/stores/timeline";
import { WorkspaceProvider, useWorkspace } from "@/lib/stores/workspace";
import TransportBar from "./TransportBar";
import LibraryPanel from "./LibraryPanel";
import RepresentationStack from "./RepresentationStack";
import InspectorPanel from "./InspectorPanel";

export type ServiceStatus = "checking" | "ready" | "unavailable";

function WorkspaceContent({ signedIn = false, projectName, serviceStatus }: { signedIn?: boolean; projectName?: string; serviceStatus: ServiceStatus }) {
  const { workspace, toggleInspector, toggleLibrary } = useWorkspace();
  const initializedResponsiveLayout = useRef(false);

  useEffect(() => {
    if (initializedResponsiveLayout.current) return;
    initializedResponsiveLayout.current = true;
    if (!window.matchMedia("(max-width: 820px)").matches) return;
    if (!workspace.libraryCollapsed) toggleLibrary();
    if (!workspace.inspectorCollapsed) toggleInspector();
  }, [toggleInspector, toggleLibrary, workspace.inspectorCollapsed, workspace.libraryCollapsed]);

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
      <div className="studio-header"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--s-4)",
          padding: "var(--s-2) var(--s-4)",
          background: "var(--panel)",
          borderBottom: "1px solid var(--border)",
          minHeight: 44,
        }}
      >
        <div className="brand" style={{ fontSize: "var(--fs-sm)", flexShrink: 0 }}>
          <span className="brand-dot" />
          {projectName || "hello-ai"}
        </div>

        {workspace.activeWorkId && (
          <span className="badge" style={{ color: "var(--success)", background: "var(--success-soft)" }}>
            Persisted session
          </span>
        )}

        <span className="badge" style={{ color: serviceStatus === "ready" ? "var(--success)" : serviceStatus === "unavailable" ? "var(--danger)" : "var(--muted)", background: serviceStatus === "ready" ? "var(--success-soft)" : serviceStatus === "unavailable" ? "var(--danger-soft)" : "var(--panel-3)" }}>
          {serviceStatus === "ready" ? "Service online" : serviceStatus === "unavailable" ? "Service offline" : "Checking service"}
        </span>

        <div style={{ flex: 1 }} />

        {workspace.inspectorCollapsed && (
          <button
            className="icon-btn ghost"
            onClick={toggleInspector}
            style={{ padding: "4px 10px", fontSize: "var(--fs-xs)" }}
          >
            Inspector
          </button>
        )}
      </div>

      <TransportBar />

      <div className="studio-workspace" style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <LibraryPanel signedIn={signedIn} canImport={serviceStatus === "ready"} />

        <RepresentationStack signedIn={signedIn} canImport={serviceStatus === "ready"} />

        <InspectorPanel />
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
        <SelectionProvider>
          <WorkspaceProvider>
            {children}
            <WorkspaceContent signedIn={signedIn} projectName={projectName} serviceStatus={serviceStatus} />
          </WorkspaceProvider>
        </SelectionProvider>
      </TransportProvider>
    </TimelineProvider>
  );
}
