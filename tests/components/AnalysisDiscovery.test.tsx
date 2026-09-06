import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AnalysisDiscovery from "@/components/workspace/AnalysisDiscovery";

const workspaceState = vi.hoisted(() => ({
  current: {} as Record<string, unknown>,
}));

vi.mock("@/lib/stores/workspace", () => ({
  useWorkspace: () => workspaceState.current,
}));

function renderDiscovery() {
  render(
    <AnalysisDiscovery
      open
      onOpenChange={() => undefined}
      structure={{ actionLabel: "Add", onAction: () => undefined }}
      pitch={{ actionLabel: "Add", onAction: () => undefined }}
    />,
  );
}

describe("AnalysisDiscovery", () => {
  beforeEach(() => {
    workspaceState.current = {
      workspace: {
        selection: null,
        analysisState: "idle",
        inspectorCollapsed: false,
      },
      setInspectorMode: vi.fn(),
      toggleInspector: vi.fn(),
    };
  });

  it("keeps contextual capabilities out of the chooser until they are eligible", () => {
    renderDiscovery();

    expect(screen.getByText("Structure Map")).toBeInTheDocument();
    expect(screen.getByText("Pitch Contour")).toBeInTheDocument();
    expect(screen.queryByText("Similar moments")).not.toBeInTheDocument();
    expect(screen.queryByText("Changes")).not.toBeInTheDocument();
  });

  it("reveals passage and evidence actions when the workspace makes them meaningful", () => {
    workspaceState.current = {
      workspace: {
        selection: {
          timeRange: { start: 12, end: 18, domain: "performance" },
          provenance: { timeExact: true },
        },
        analysisState: "completed",
        inspectorCollapsed: false,
      },
      setInspectorMode: vi.fn(),
      toggleInspector: vi.fn(),
    };

    renderDiscovery();

    expect(screen.getByText("Similar moments")).toBeInTheDocument();
    expect(screen.getByText("Changes")).toBeInTheDocument();
  });
});
