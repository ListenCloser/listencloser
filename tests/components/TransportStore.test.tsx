import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { TimelineProvider } from "@/lib/stores/timeline";
import { TransportProvider, useTransport } from "@/lib/stores/transport";

function wrapper({ children }: { children: ReactNode }) {
  return (
    <TimelineProvider>
      <TransportProvider>{children}</TransportProvider>
    </TimelineProvider>
  );
}

const src = (role: "original" | "transcription" | "derived", id: string) => ({
  id,
  label: role === "original" ? "Original audio" : "Transcription playback",
  url: `data:audio/wav;base64,${id}`,
  kind: "audio" as const,
  role,
});

describe("TransportProvider", () => {
  it("resets loop state when replacing sources", () => {
    const { result } = renderHook(() => useTransport(), { wrapper });

    act(() => {
      result.current.replaceSources([src("original", "a")], "a");
      result.current.setLoop(0, 10);
      result.current.toggleLoop();
    });
    expect(result.current.transport.loopEnabled).toBe(true);

    act(() => {
      result.current.replaceSources([src("transcription", "b")], "b");
    });
    expect(result.current.transport.loopEnabled).toBe(false);
    expect(result.current.transport.loopStart).toBeNull();
    expect(result.current.transport.loopEnd).toBeNull();
    expect(result.current.transport.position).toBe(0);
  });

  it("resets loop state when clearing the active source", () => {
    const { result } = renderHook(() => useTransport(), { wrapper });

    act(() => {
      result.current.replaceSources([src("original", "a")], "a");
      result.current.setLoop(0, 10);
      result.current.toggleLoop();
    });
    act(() => result.current.clearActiveSource());
    expect(result.current.transport.loopEnabled).toBe(false);
    expect(result.current.transport.activeSource).toBeNull();
    expect(result.current.transport.sources).toEqual([]);
  });

  it("keeps a score source as a distinct active source", () => {
    const { result } = renderHook(() => useTransport(), { wrapper });
    const score = {
      id: "score-audio",
      label: "Score rendition",
      url: "data:audio/wav;base64,score",
      kind: "audio" as const,
      role: "score" as const,
    };

    act(() => {
      result.current.replaceSources([src("transcription", "t"), score], "score-audio");
    });
    expect(result.current.transport.activeSource?.id).toBe("score-audio");
    expect(result.current.transport.activeSource?.role).toBe("score");
    expect(result.current.transport.sources.map((s) => s.role)).toEqual(["transcription", "score"]);
  });

  it("preserves position and active source when replacing with preservePosition", () => {
    const { result } = renderHook(() => useTransport(), { wrapper });

    act(() => {
      result.current.replaceSources([src("original", "a")], "a");
      result.current.seek(7);
    });
    expect(result.current.transport.position).toBe(7);

    act(() => {
      result.current.replaceSources([src("original", "a")], "a", true);
    });
    expect(result.current.transport.position).toBe(7);
    expect(result.current.transport.activeSource?.id).toBe("a");
  });

  it("falls back to the requested source when the preserved source is gone", () => {
    const { result } = renderHook(() => useTransport(), { wrapper });

    act(() => {
      result.current.replaceSources([src("original", "a")], "a");
      result.current.seek(7);
    });

    act(() => {
      result.current.replaceSources([src("transcription", "b")], "b", true);
    });
    expect(result.current.transport.position).toBe(7);
    expect(result.current.transport.activeSource?.id).toBe("b");
  });
});
