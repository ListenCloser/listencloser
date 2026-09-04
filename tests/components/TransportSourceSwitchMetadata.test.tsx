import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TimelineProvider } from "@/lib/stores/timeline";
import { TransportProvider, useTransport } from "@/lib/stores/transport";

function wrapper({ children }: { children: ReactNode }) {
  return (
    <TimelineProvider>
      <TransportProvider>{children}</TransportProvider>
    </TimelineProvider>
  );
}

const source = (id: string, label: string, role: "original" | "derived") => ({
  id,
  label,
  url: `data:audio/wav;base64,${id}`,
  kind: "audio" as const,
  role,
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TransportProvider source metadata timing", () => {
  it("restores the exact position when loadedmetadata fires during load", () => {
    const { result } = renderHook(() => useTransport(), { wrapper });
    const audio = result.current.audioRef.current;
    expect(audio).not.toBeNull();
    Object.defineProperty(audio!, "duration", {
      configurable: true,
      get: () => 30,
    });

    vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(function loadNow() {
      this.currentTime = 0;
      this.dispatchEvent(new Event("loadedmetadata"));
    });

    act(() => {
      result.current.replaceSources([source("original", "Original", "original")], "original");
      result.current.seek(12);
    });
    expect(result.current.transport.position).toBe(12);

    act(() => {
      result.current.setActiveSource(source("vocals", "Vocals", "derived"));
    });

    expect(audio!.currentTime).toBe(12);
    expect(result.current.positionRef.current).toBe(12);
    expect(result.current.transport.position).toBe(12);
    expect(result.current.transport.activeSource?.id).toBe("vocals");
  });
});
