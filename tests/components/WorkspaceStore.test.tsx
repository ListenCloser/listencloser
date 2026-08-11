import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { WorkspaceProvider, useWorkspace } from "@/lib/stores/workspace";

function wrapper({ children }: { children: ReactNode }) {
  return <WorkspaceProvider>{children}</WorkspaceProvider>;
}

describe("WorkspaceProvider", () => {
  it("clears the previous work before selecting another work", () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper });

    act(() => {
      result.current.setActiveWorkId("work-a");
      result.current.replaceRepresentations([{
        kind: "waveform",
        label: "Waveform",
        sourceUrl: "a.wav",
        sourceLabel: "Work A",
        confidence: null,
        provenance: "test",
      }]);
      result.current.setInsights([{
        id: "insight-a",
        version_id: "version-a",
        kind: "key",
        claim: "Key: C major",
        span: { start_seconds: null, end_seconds: null, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
        entity_ids: [],
        evidence: {},
        confidence: 0.8,
        provenance: {},
        created_at: new Date().toISOString(),
        created_by: null,
        produced_by_job_id: null,
      }]);
    });

    expect(result.current.workspace.representations).toHaveLength(1);

    act(() => result.current.setActiveWorkId("work-b"));

    expect(result.current.workspace.activeWorkId).toBe("work-b");
    expect(result.current.workspace.isLoadingWork).toBe(true);
    expect(result.current.workspace.representations).toEqual([]);
    expect(result.current.workspace.insights).toEqual([]);
  });
});
