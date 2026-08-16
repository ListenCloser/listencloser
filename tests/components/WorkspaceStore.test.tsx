import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { WorkspaceProvider, useWorkspace } from "@/lib/stores/workspace";
import type { AskMessage } from "@/lib/ask/types";

function wrapper({ children }: { children: ReactNode }) {
  return <WorkspaceProvider>{children}</WorkspaceProvider>;
}

function askMessages(): AskMessage[] {
  return [
    { id: "u1", role: "user", text: "What is happening here?" },
    { id: "a1", role: "assistant", response: { answer: "A passage.", references: [] } },
  ];
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
      result.current.setSelection({
        timeRange: { start: 1, end: 3, domain: "performance" },
        provenance: { origin: "waveform", timeExact: true, measureApproximate: false },
      });
    });

    expect(result.current.workspace.representations).toHaveLength(1);
    expect(result.current.workspace.selection).not.toBeNull();

    act(() => result.current.setActiveWorkId("work-b"));

    expect(result.current.workspace.activeWorkId).toBe("work-b");
    expect(result.current.workspace.isLoadingWork).toBe(true);
    expect(result.current.workspace.representations).toEqual([]);
    expect(result.current.workspace.insights).toEqual([]);
    expect(result.current.workspace.selection).toBeNull();
  });

  it("keeps the selection across representation and playback-source changes", () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper });

    act(() => {
      result.current.setSelection({
        timeRange: { start: 1, end: 3, domain: "performance" },
        provenance: { origin: "waveform", timeExact: true, measureApproximate: false },
      });
      result.current.setActiveRepresentation("piano_roll");
      result.current.setActiveRepresentation("score");
      result.current.setActiveRepresentation("listen");
    });

    expect(result.current.workspace.selection?.timeRange).toEqual({ start: 1, end: 3, domain: "performance" });
    expect(result.current.workspace.activeRepresentation).toBe("listen");
  });

  it("clears the selection when deleting the active work", () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper });

    act(() => {
      result.current.setWorks([
        { id: "work-a", project_id: "p", title: "A", composer: null, created_at: "", updated_at: "" },
      ]);
      result.current.setActiveWorkId("work-a");
      result.current.setSelection({
        timeRange: { start: 1, end: 3, domain: "performance" },
        provenance: { origin: "waveform", timeExact: true, measureApproximate: false },
      });
    });

    act(() => result.current.removeWork("work-a"));

    expect(result.current.workspace.selection).toBeNull();
  });

  it("clears studio state when switching works", () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper });

    act(() => {
      result.current.setActiveWorkId("work-a");
      result.current.requestVariation("version-1", 2);
    });
    expect(result.current.workspace.studioAction).not.toBeNull();

    act(() => result.current.setActiveWorkId("work-b"));
    expect(result.current.workspace.studioAction).toBeNull();
    expect(result.current.workspace.studioOperation.state).toBe("idle");
  });

  it("clears takes and studio state when deleting the active work", () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper });

    act(() => {
      result.current.setWorks([
        { id: "work-a", project_id: "p", title: "A", composer: null, created_at: "", updated_at: "" },
      ]);
      result.current.setActiveWorkId("work-a");
      result.current.setTakes([{ versionId: "v", label: "Transcription", parentVersionId: null }]);
      result.current.requestVariation("v", 1);
    });

    act(() => result.current.removeWork("work-a"));

    expect(result.current.workspace.activeWorkId).toBeNull();
    expect(result.current.workspace.takes).toEqual([]);
    expect(result.current.workspace.studioAction).toBeNull();
    expect(result.current.workspace.isLoadingWork).toBe(false);
  });

  it("clears the ask conversation when switching works", () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper });

    act(() => {
      result.current.setActiveWorkId("work-a");
      result.current.appendAskMessage(askMessages()[0]);
      result.current.appendAskMessage(askMessages()[1]);
    });
    expect(result.current.workspace.askConversation).toHaveLength(2);

    act(() => result.current.setActiveWorkId("work-b"));

    expect(result.current.workspace.askConversation).toEqual([]);
  });

  it("clears the ask conversation when deleting the active work", () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper });

    act(() => {
      result.current.setWorks([
        { id: "work-a", project_id: "p", title: "A", composer: null, created_at: "", updated_at: "" },
      ]);
      result.current.setActiveWorkId("work-a");
      result.current.appendAskMessage(askMessages()[0]);
    });

    act(() => result.current.removeWork("work-a"));

    expect(result.current.workspace.askConversation).toEqual([]);
  });

  it("keeps the ask conversation across representation changes", () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper });

    act(() => {
      result.current.setActiveWorkId("work-a");
      result.current.appendAskMessage(askMessages()[0]);
      result.current.appendAskMessage(askMessages()[1]);
      result.current.setActiveRepresentation("score");
      result.current.setActiveRepresentation("listen");
    });

    expect(result.current.workspace.askConversation).toHaveLength(2);
  });

  it("does not clear the ask conversation when switching inspector modes", () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper });

    act(() => {
      result.current.setActiveWorkId("work-a");
      result.current.appendAskMessage(askMessages()[0]);
      result.current.setInspectorMode("ask");
      result.current.setInspectorMode("analysis");
    });

    expect(result.current.workspace.inspectorMode).toBe("analysis");
    expect(result.current.workspace.askConversation).toHaveLength(1);
  });

  it("appends messages in order and clears via clearAskConversation", () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper });

    act(() => {
      result.current.appendAskMessage(askMessages()[0]);
      result.current.appendAskMessage(askMessages()[1]);
    });
    expect(result.current.workspace.askConversation.map((m) => m.id)).toEqual(["u1", "a1"]);

    act(() => result.current.clearAskConversation());
    expect(result.current.workspace.askConversation).toEqual([]);
  });
});
