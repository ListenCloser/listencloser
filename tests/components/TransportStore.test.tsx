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
});
