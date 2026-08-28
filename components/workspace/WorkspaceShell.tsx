"use client";

import { type ReactNode, useEffect, useRef } from "react";
import { TransportProvider } from "@/lib/stores/transport";
import { TimelineProvider } from "@/lib/stores/timeline";
import { WorkspaceProvider, useWorkspace } from "@/lib/stores/workspace";
import { presentableTitle } from "@/lib/format";
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
    if (!workspace.libraryCollapsed) toggleLibrary();
  }, [toggleLibrary, workspace.libraryCollapsed]);

  const activeWork = workspace.works.find((work) => work.id === workspace.activeWorkId) ?? null;
  const inspectorOpen = !workspace.inspectorCollapsed;
  const analysisAvailable = workspace.analysisState === "completed" && Boolean(workspace.activeWorkId);
  const serviceLabel = serviceStatus === "ready"
    ? "Ready"
    : serviceStatus === "checking"
      ? "Connecting"
      : "Offline";

  return (
    <div className="studio-shell studio-shell-v3">
      <header className="studio-header studio-header-v3">
        <div className="studio-brand-lockup" aria-label="Music Lab">
          <span className="studio-brand-mark" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M5 13.5V5.25L14 3v8.25" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="3.75" cy="13.5" r="2.25" fill="currentColor" />
              <circle cx="12.75" cy="11.25" r="2.25" fill="currentColor" />
            </svg>
          </span>
          <span className="studio-product-name">Music Lab</span>
        </div>

        <div className="studio-document-title" aria-live="polite">
          {activeWork ? (
            <>
              <span className="studio-document-name">{presentableTitle(activeWork.title)}</span>
              {workspace.isLoadingWork && <span className="studio-document-state">Opening…</span>}
            </>
          ) : (
            <span className="studio-document-name studio-document-name-muted">Untitled workspace</span>
          )}
        </div>

        <div className="studio-header-actions">
          <span className={`studio-service-state studio-service-${serviceStatus}`} title={`Processing service: ${serviceLabel}`}>
            <span className="studio-service-dot" aria-hidden="true" />
            <span className="studio-service-label">{serviceLabel}</span>
          </span>
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
              aria-label={inspectorOpen ? "Hide analysis" : "Show analysis"}
              aria-pressed={inspectorOpen}
              onClick={toggleInspector}
            >
              Analysis
            </button>
          )}
        </div>
      </header>

      <div className="studio-workspace studio-workspace-v3">
        <LibraryPanel signedIn={signedIn} canImport={serviceStatus === "ready"} />

        <div className="studio-canvas-area studio-canvas-area-v3">
          <RepresentationStack signedIn={signedIn} canImport={serviceStatus === "ready"} />
        </div>

        {analysisAvailable && (
          <>
            <aside className={`studio-inspector studio-inspector-v3${inspectorOpen ? " is-open" : ""}`}>
              <InspectorPanel />
            </aside>
            {inspectorOpen && (
              <button
                type="button"
                className="studio-inspector-backdrop"
                onClick={toggleInspector}
                aria-label="Close analysis"
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
  projectName?: string;
  serviceStatus?: ServiceStatus;
  children?: ReactNode;
}) {
  return (
    <TimelineProvider>
      <TransportProvider>
        <WorkspaceProvider>
          {children}
          <WorkspaceContent signedIn={signedIn} serviceStatus={serviceStatus} />
        </WorkspaceProvider>
      </TransportProvider>
    </TimelineProvider>
  );
}
