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

  it("preserves an explicit derived playback choice when the same Work refreshes", () => {
    const load = vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => undefined);
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
    const { result } = renderHook(() => useTransport(), { wrapper: transportWrapper });

    const original = {
      id: "original-version",
      label: "Original",
      url: "https://storage.example/original-first",
      kind: "audio" as const,
      role: "original" as const,
    };
    const score = {
      id: "score-version",
      label: "Score",
      url: "https://storage.example/score-first",
      kind: "audio" as const,
      role: "score" as const,
    };

    act(() => result.current.replaceSources([original, score], original.id));
    act(() => result.current.setActiveSource(score));
    expect(result.current.transport.activeSource?.id).toBe(score.id);
    expect(load).toHaveBeenCalledTimes(2);

    act(() => result.current.replaceSources([
      { ...original, url: "https://storage.example/original-refreshed" },
      { ...score, url: "https://storage.example/score-refreshed" },
    ], original.id, true));

    expect(load).toHaveBeenCalledTimes(2);
    expect(result.current.transport.activeSource?.id).toBe(score.id);
    expect(result.current.transport.activeSource?.url).toBe(score.url);
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

  it("does accept a new URL when the immutable version changes", () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper: workspaceWrapper });
    const first = {
      kind: "waveform" as const,
      label: "Waveform",
      sourceUrl: "https://storage.example/version-a",
      sourceLabel: "Playback source",
      confidence: null,
      provenance: "uploaded source",
      audioUrl: "https://storage.example/version-a",
      versionId: "version-a",
    };
    const second = { ...first, sourceUrl: "https://storage.example/version-b", versionId: "version-b" };

    act(() => result.current.replaceRepresentations([first]));
    act(() => result.current.replaceRepresentations([second]));

    expect(result.current.workspace.representations[0]?.sourceUrl).toBe(second.sourceUrl);
    expect(result.current.workspace.representations[0]?.versionId).toBe(second.versionId);
  });
});
