import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { TransportProvider, useTransport } from "@/lib/stores/transport";
import { WorkspaceProvider, useWorkspace } from "@/lib/stores/workspace";

const src = (role: "original" | "transcription" | "derived", id: string) => ({
  id,
  label: role === "original" ? "Original audio" : "Transcription playback",
  url: `data:audio/wav;base64,${id}`,
  kind: "audio" as const,
  role,
});

const waveform = {
  kind: "waveform" as const,
  label: "Waveform",
  sourceUrl: "a.wav",
  sourceLabel: "Source",
  confidence: null,
  provenance: "test",
  audioUrl: "a.wav",
};

const pianoRoll = {
  kind: "piano_roll" as const,
  label: "Piano Roll",
  sourceUrl: "b.mid",
  sourceLabel: "10 detected notes",
  confidence: null,
  provenance: "test",
  notes: [{ pitch: 60, start: 0, end: 1, velocity: 80 }],
};

function wrapper({ children }: { children: ReactNode }) {
  return (
    <WorkspaceProvider>
      <TransportProvider>{children}</TransportProvider>
    </WorkspaceProvider>
  );
}

function useSession() {
  const workspace = useWorkspace();
  const transport = useTransport();
  return { workspace, transport };
}

describe("Workspace session state transitions", () => {
  it("does not interrupt playback or reset position when the representation changes", () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => {
      result.current.transport.replaceSources([src("original", "a")], "a");
      result.current.transport.seek(7);
    });
    const transportBefore = { ...result.current.transport.transport };
    const activeSourceBefore = result.current.transport.transport.activeSource;

    act(() => {
      result.current.workspace.setActiveRepresentation("listen");
      result.current.workspace.setActiveRepresentation("piano_roll");
      result.current.workspace.setActiveRepresentation("score");
      result.current.workspace.setActiveRepresentation("analysis");
    });

    expect(result.current.transport.transport.position).toBe(transportBefore.position);
    expect(result.current.transport.transport.isPlaying).toBe(transportBefore.isPlaying);
    expect(result.current.transport.transport.duration).toBe(transportBefore.duration);
    expect(result.current.transport.transport.activeSource).toBe(activeSourceBefore);
    expect(result.current.workspace.workspace.activeRepresentation).toBe("analysis");
  });

  it("keeps the same representation when the playback source changes", () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => {
      result.current.workspace.setActiveRepresentation("score");
      result.current.transport.replaceSources([src("original", "a")], "a");
      result.current.transport.setActiveSource({ ...src("transcription", "b"), label: "Transcription" });
    });

    expect(result.current.workspace.workspace.activeRepresentation).toBe("score");
    expect(result.current.transport.transport.activeSource?.id).toBe("b");
    expect(result.current.transport.transport.activeSource?.role).toBe("transcription");
  });

  it("preserves position and the active source when the same work is reloaded", () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => {
      result.current.transport.replaceSources([src("original", "a")], "a");
      result.current.transport.seek(7);
      result.current.workspace.setActiveRepresentation("score");
    });

    act(() => {
      result.current.transport.replaceSources([src("original", "a")], "a", true);
      result.current.workspace.replaceRepresentations([waveform, pianoRoll]);
    });

    expect(result.current.transport.transport.position).toBe(7);
    expect(result.current.transport.transport.activeSource?.id).toBe("a");
    expect(result.current.transport.transport.isPlaying).toBe(false);
    expect(result.current.workspace.workspace.activeRepresentation).toBe("score");
  });

  it("resets representation and representations when switching works", () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => {
      result.current.workspace.setActiveWorkId("work-a");
      result.current.workspace.replaceRepresentations([waveform, pianoRoll]);
      result.current.workspace.setActiveRepresentation("piano_roll");
    });

    act(() => result.current.workspace.setActiveWorkId("work-b"));

    expect(result.current.workspace.workspace.representations).toEqual([]);
    expect(result.current.workspace.workspace.activeRepresentation).toBeNull();
    expect(result.current.workspace.workspace.isLoadingWork).toBe(true);
  });

  it("clears the work session when the active work is deleted", () => {
    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => {
      result.current.workspace.setWorks([{ id: "work-a", project_id: "p", title: "A", composer: null, created_at: "", updated_at: "" }]);
      result.current.workspace.setActiveWorkId("work-a");
      result.current.workspace.replaceRepresentations([waveform, pianoRoll]);
      result.current.workspace.setActiveRepresentation("piano_roll");
      result.current.transport.replaceSources([src("original", "a")], "a");
      result.current.transport.seek(3);
    });

    act(() => result.current.workspace.removeWork("work-a"));
    act(() => result.current.transport.clearActiveSource());

    expect(result.current.workspace.workspace.activeWorkId).toBeNull();
    expect(result.current.workspace.workspace.representations).toEqual([]);
    expect(result.current.workspace.workspace.activeRepresentation).toBeNull();
    expect(result.current.transport.transport.activeSource).toBeNull();
    expect(result.current.transport.transport.sources).toEqual([]);
    expect(result.current.transport.transport.position).toBe(0);
    expect(result.current.transport.transport.duration).toBe(0);
    expect(result.current.transport.transport.isPlaying).toBe(false);
  });
});