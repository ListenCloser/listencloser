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

function WorkspaceContent({
  signedIn = false,
  serviceStatus,
}: {
  signedIn?: boolean;
  serviceStatus: ServiceStatus;
}) {
  const { workspace, toggleLibrary, toggleInspector } = useWorkspace();
  const initializedResponsiveLayout = useRef(false);

  useEffect(() => {
    if (initializedResponsiveLayout.current) return;
    initializedResponsiveLayout.current = true;
    if (!window.matchMedia("(max-width: 820px)").matches) return;

    // Compact layouts are staged rather than simultaneous: the musical canvas
    // is the default surface and Library / Breakdown open only when requested.
    if (!workspace.libraryCollapsed) toggleLibrary();
    if (!workspace.inspectorCollapsed) toggleInspector();
  }, [toggleInspector, toggleLibrary, workspace.inspectorCollapsed, workspace.libraryCollapsed]);

  const inspectorOpen = !workspace.inspectorCollapsed;
  const analysisAvailable = workspace.analysisState === "completed" && Boolean(workspace.activeWorkId);
  // Import is a processing-dependent action. "Checking" is not equivalent to
  // ready: enabling the control optimistically creates a race where health can
  // resolve unavailable between the click and file selection.
  const canImport = serviceStatus === "ready";

  return (
    <div className="studio-shell studio-shell-v3">
      <header className="studio-header studio-header-v3">
        <div aria-hidden="true" />

        <div className="studio-header-spacer" aria-hidden="true" />

        <div className="studio-header-actions">
          {serviceStatus === "unavailable" && (
            <span className="studio-service-state studio-service-unavailable">
              <span className="studio-service-dot" aria-hidden="true" />
              <span className="studio-service-label">Processing offline</span>
            </span>
          )}
          <button
            type="button"
            className="studio-mobile-action studio-library-btn"
            onClick={toggleLibrary}
            aria-label={workspace.libraryCollapsed ? "Show library" : "Hide library"}
            aria-pressed={!workspace.libraryCollapsed}
          >
            Library
          </button>
          {analysisAvailable && (
            <button
              type="button"
              className={`studio-mobile-action studio-inspector-btn${inspectorOpen ? " active" : ""}`}
              aria-label={inspectorOpen ? "Hide breakdown" : "Show breakdown"}
              aria-pressed={inspectorOpen}
              onClick={toggleInspector}
            >
              Breakdown
            </button>
          )}
        </div>
      </header>

      <div className="studio-workspace studio-workspace-v3">
        <LibraryPanel signedIn={signedIn} canImport={canImport} />

        <div className="studio-canvas-area studio-canvas-area-v3">
          <RepresentationStack signedIn={signedIn} canImport={canImport} />
        </div>

        {analysisAvailable && (
          <>
            <aside
              className={`studio-inspector studio-inspector-v3${inspectorOpen ? " is-open" : ""}`}
              aria-hidden={!inspectorOpen}
              inert={!inspectorOpen}
            >
              <InspectorPanel />
            </aside>
            {inspectorOpen && (
              <button
                type="button"
                className="studio-inspector-backdrop"
                onClick={toggleInspector}
                aria-label="Close breakdown"
              />
            )}
          </>
        )}
      </div>

      <TransportBar />
    </div>
  );
}

export default function WorkspaceShell({
  signedIn = false,
  serviceStatus = "checking",
  children,
}: {
  signedIn?: boolean;
  serviceStatus?: ServiceStatus;
  children?: ReactNode;
}) {
  return (
    <TimelineProvider>
      <TransportProvider>
        <WorkspaceProvider initialLoading={signedIn}>
          {children}
          <WorkspaceContent signedIn={signedIn} serviceStatus={serviceStatus} />
        </WorkspaceProvider>
      </TransportProvider>
    </TimelineProvider>
  );
}
