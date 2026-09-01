import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TimelineProvider } from "@/lib/stores/timeline";
import { TransportProvider, useTransport } from "@/lib/stores/transport";
import { WorkspaceProvider, useWorkspace } from "@/lib/stores/workspace";

function transportWrapper({ children }: { children: ReactNode }) {
  return (
    <TimelineProvider>
      <TransportProvider>{children}</TransportProvider>
    </TimelineProvider>
  );
}

function workspaceWrapper({ children }: { children: ReactNode }) {
  return <WorkspaceProvider>{children}</WorkspaceProvider>;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("same-Work processing refresh continuity", () => {
  it("does not reload audio when the immutable source version is unchanged", () => {
    const load = vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => undefined);
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
    const { result } = renderHook(() => useTransport(), { wrapper: transportWrapper });

    const first = {
      id: "version-a",
      label: "Original audio",
      url: "https://storage.example/first-signed-url",
      kind: "audio" as const,
      role: "original" as const,
    };
    const refreshed = { ...first, url: "https://storage.example/refreshed-signed-url" };

    act(() => result.current.replaceSources([first], first.id));
    expect(load).toHaveBeenCalledTimes(1);

    act(() => result.current.replaceSources([refreshed], refreshed.id, true));

    expect(load).toHaveBeenCalledTimes(1);
    expect(result.current.transport.activeSource?.id).toBe(first.id);
    expect(result.current.transport.activeSource?.url).toBe(first.url);
  });

  it("keeps representation URLs stable when a poll returns a new signed URL for the same version", () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper: workspaceWrapper });
    const first = {
      kind: "waveform" as const,
      label: "Waveform",
      sourceUrl: "https://storage.example/first-signed-url",
      sourceLabel: "Playback source",
      confidence: null,
      provenance: "uploaded source",
      audioUrl: "https://storage.example/first-signed-url",
      versionId: "version-a",
    };
    const refreshed = {
      ...first,
      sourceUrl: "https://storage.example/refreshed-signed-url",
      audioUrl: "https://storage.example/refreshed-signed-url",
    };

    act(() => result.current.replaceRepresentations([first]));
    act(() => result.current.replaceRepresentations([refreshed]));

    expect(result.current.workspace.representations[0]?.sourceUrl).toBe(first.sourceUrl);
    expect(result.current.workspace.representations[0]?.audioUrl).toBe(first.audioUrl);
  });

  it("keeps confirmed Piano Roll and Score when a same-source poll temporarily omits them", () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper: workspaceWrapper });
    const waveform = {
      kind: "waveform" as const,
      label: "Waveform",
      sourceUrl: "https://storage.example/source-a",
      sourceLabel: "Playback source",
      confidence: null,
      provenance: "uploaded source",
      audioUrl: "https://storage.example/source-a",
      versionId: "source-version-a",
    };
    const pianoRoll = {
      kind: "piano_roll" as const,
      label: "Piano Roll",
      sourceUrl: "https://storage.example/notes-a",
      sourceLabel: "1 detected note",
      confidence: null,
      provenance: "transcription",
      notes: [{ pitch: 60, start: 0, end: 1, velocity: 80 }],
      versionId: "midi-version-a",
    };
    const score = {
      kind: "score" as const,
      label: "Score",
      sourceUrl: "https://storage.example/score-a",
      sourceLabel: "Notation draft",
      confidence: null,
      provenance: "score interpretation",
      musicxml: "<score-partwise />",
      versionId: "score-version-a",
    };

    act(() => result.current.replaceRepresentations([waveform, pianoRoll, score]));
    act(() => result.current.replaceRepresentations([{ ...waveform, sourceUrl: "https://storage.example/refreshed-source-a" }]));

    expect(result.current.workspace.representations.map((item) => item.kind)).toEqual([
      "waveform",
      "piano_roll",
      "score",
    ]);
    expect(result.current.workspace.representations.find((item) => item.kind === "piano_roll")?.versionId).toBe("midi-version-a");
    expect(result.current.workspace.representations.find((item) => item.kind === "score")?.versionId).toBe("score-version-a");
  });

  it("replaces a retained representation when a newer durable version arrives", () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper: workspaceWrapper });
    const waveform = {
      kind: "waveform" as const,
      label: "Waveform",
      sourceUrl: "https://storage.example/source-a",
      sourceLabel: "Playback source",
      confidence: null,
      provenance: "uploaded source",
      versionId: "source-version-a",
    };
    const oldPianoRoll = {
      kind: "piano_roll" as const,
      label: "Piano Roll",
      sourceUrl: "https://storage.example/notes-a",
      sourceLabel: "1 detected note",
      confidence: null,
      provenance: "transcription",
      notes: [{ pitch: 60, start: 0, end: 1, velocity: 80 }],
      versionId: "midi-version-a",
    };
    const newPianoRoll = {
      ...oldPianoRoll,
      sourceUrl: "https://storage.example/notes-b",
      versionId: "midi-version-b",
    };

    act(() => result.current.replaceRepresentations([waveform, oldPianoRoll]));
    act(() => result.current.replaceRepresentations([waveform, newPianoRoll]));

    const pianoRoll = result.current.workspace.representations.find((item) => item.kind === "piano_roll");
    expect(pianoRoll?.versionId).toBe("midi-version-b");
    expect(pianoRoll?.sourceUrl).toBe("https://storage.example/notes-b");
  });

  it("does accept a new URL when the immutable version changes", () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper: workspaceWrapper });
    const first = {
      kind: "waveform" as const,
      label: "Waveform",
      sourceUrl: "https://storage.example/version-a",
      sourceLabel: "Playback source",
      confidence: null,
      provenance: "uploaded source",
      versionId: "version-a",
    };
    const pianoRoll = {
      kind: "piano_roll" as const,
      label: "Piano Roll",
      sourceUrl: "https://storage.example/notes-a",
      sourceLabel: "1 detected note",
      confidence: null,
      provenance: "transcription",
      notes: [{ pitch: 60, start: 0, end: 1, velocity: 80 }],
      versionId: "midi-version-a",
    };
    const second = { ...first, sourceUrl: "https://storage.example/version-b", versionId: "version-b" };

    act(() => result.current.replaceRepresentations([first, pianoRoll]));
    act(() => result.current.replaceRepresentations([second]));

    expect(result.current.workspace.representations).toHaveLength(1);
    expect(result.current.workspace.representations[0]?.sourceUrl).toBe(second.sourceUrl);
    expect(result.current.workspace.representations[0]?.versionId).toBe(second.versionId);
  });
});
