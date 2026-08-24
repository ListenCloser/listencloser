import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { TimelineProvider } from "@/lib/stores/timeline";
import { TransportProvider, useTransport } from "@/lib/stores/transport";
import { WorkspaceProvider, useWorkspace } from "@/lib/stores/workspace";

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

const score = {
  id: "score-audio",
  label: "Score",
  url: "data:audio/wav;base64,score",
  kind: "audio" as const,
  role: "score" as const,
};

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

    act(() => {
      result.current.replaceSources([src("transcription", "t"), score], "score-audio");
    });
    expect(result.current.transport.activeSource?.id).toBe("score-audio");
    expect(result.current.transport.activeSource?.role).toBe("score");
    expect(result.current.transport.sources.map((s) => s.role)).toEqual(["transcription", "score"]);
  });

  it("enters compare mode with the chosen pair and starts on side A", () => {
    const { result } = renderHook(() => useTransport(), { wrapper });

    act(() => {
      result.current.replaceSources([src("original", "a"), src("transcription", "b"), score], "a");
    });
    act(() => {
      result.current.startCompare(src("original", "a"), score);
    });

    expect(result.current.transport.compareEnabled).toBe(true);
    expect(result.current.transport.compareA?.id).toBe("a");
    expect(result.current.transport.compareB?.id).toBe("score-audio");
    expect(result.current.transport.activeSide).toBe("A");
    expect(result.current.transport.activeSource?.id).toBe("a");
  });

  it("toggling the compare side switches the active source without losing it", () => {
    const { result } = renderHook(() => useTransport(), { wrapper });

    act(() => {
      result.current.replaceSources([src("original", "a"), src("transcription", "b"), score], "a");
      result.current.startCompare(src("original", "a"), score);
    });

    act(() => {
      result.current.setCompareSide("B");
    });
    expect(result.current.transport.activeSide).toBe("B");
    expect(result.current.transport.activeSource?.id).toBe("score-audio");

    act(() => {
      result.current.setCompareSide("A");
    });
    expect(result.current.transport.activeSide).toBe("A");
    expect(result.current.transport.activeSource?.id).toBe("a");
    expect(result.current.transport.compareEnabled).toBe(true);
  });

  it("swapping a compare side keeps the other side intact", () => {
    const { result } = renderHook(() => useTransport(), { wrapper });

    act(() => {
      result.current.replaceSources([src("original", "a"), src("transcription", "b"), score], "a");
      result.current.startCompare(src("original", "a"), score);
      result.current.setCompareSource("B", src("transcription", "b"));
    });

    expect(result.current.transport.compareB?.id).toBe("b");
    expect(result.current.transport.compareA?.id).toBe("a");
    expect(result.current.transport.compareEnabled).toBe(true);
  });

  it("exiting compare keeps the active source but clears the pair", () => {
    const { result } = renderHook(() => useTransport(), { wrapper });

    act(() => {
      result.current.replaceSources([src("original", "a"), src("transcription", "b"), score], "a");
      result.current.startCompare(src("original", "a"), score);
      result.current.setCompareSide("B");
    });
    expect(result.current.transport.activeSource?.id).toBe("score-audio");

    act(() => result.current.exitCompare());

    expect(result.current.transport.compareEnabled).toBe(false);
    expect(result.current.transport.compareA).toBeNull();
    expect(result.current.transport.compareB).toBeNull();
    expect(result.current.transport.activeSide).toBe("A");
    expect(result.current.transport.activeSource?.id).toBe("score-audio");
  });

  it("clears compare state when the active source is cleared", () => {
    const { result } = renderHook(() => useTransport(), { wrapper });

    act(() => {
      result.current.replaceSources([src("original", "a"), src("transcription", "b"), score], "a");
      result.current.startCompare(src("original", "a"), score);
      result.current.clearActiveSource();
    });

    expect(result.current.transport.compareEnabled).toBe(false);
    expect(result.current.transport.compareA).toBeNull();
    expect(result.current.transport.compareB).toBeNull();
    expect(result.current.transport.activeSource).toBeNull();
    expect(result.current.transport.sources).toEqual([]);
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

  it("preserves position when switching between sources", () => {
    const { result } = renderHook(() => useTransport(), { wrapper });

    act(() => {
      result.current.replaceSources([src("original", "orig"), src("transcription", "trans"), score], "orig");
      result.current.seek(20);
    });
    expect(result.current.transport.position).toBe(20);

    // Switch to Transcription
    act(() => {
      result.current.setActiveSource(src("transcription", "trans"));
    });
    expect(result.current.transport.position).toBe(20);
    expect(result.current.transport.activeSource?.id).toBe("trans");

    // Switch to Score
    act(() => {
      result.current.setActiveSource(score);
    });
    expect(result.current.transport.position).toBe(20);
    expect(result.current.transport.activeSource?.id).toBe("score-audio");

    // Switch back to Original
    act(() => {
      result.current.setActiveSource(src("original", "orig"));
    });
    expect(result.current.transport.position).toBe(20);
    expect(result.current.transport.activeSource?.id).toBe("orig");
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

describe("TransportProvider domain-aware loop", () => {
  const perfSrc = { id: "perf", label: "Original", url: "data:audio/wav;base64,perf", kind: "audio" as const, role: "original" as const };
  const scoreSrc = { id: "score", label: "Score", url: "data:audio/wav;base64,score", kind: "audio" as const, role: "score" as const };

  function wrapperWithWorkspace({ children }: { children: ReactNode }) {
    return (
      <TimelineProvider>
        <TransportProvider>
          <WorkspaceProvider>{children}</WorkspaceProvider>
        </TransportProvider>
      </TimelineProvider>
    );
  }

  function useSession() {
    const transport = useTransport();
    const workspace = useWorkspace();
    return { transport, workspace };
  }

  it("enables loop selection when domain matches (performance ↔ performance)", () => {
    const { result } = renderHook(() => useSession(), { wrapper: wrapperWithWorkspace });

    act(() => {
      result.current.transport.replaceSources([perfSrc], "perf");
      result.current.workspace.setSelection({
        timeRange: { start: 2, end: 6, domain: "performance" },
        provenance: { origin: "waveform", timeExact: true, measureApproximate: false },
      });
    });

    // After state is settled, simulate clicking "Loop selection"
    act(() => {
      if (result.current.workspace.workspace.selection?.timeRange && result.current.transport.transport.activeSource) {
        const sel = result.current.workspace.workspace.selection;
        const active = result.current.transport.transport.activeSource;
        const selDomain = sel.timeRange?.domain ?? null;
        const activeDomain = active.role === "score" ? "notation" : "performance";
        if (selDomain === activeDomain) {
          result.current.transport.setLoop(sel.timeRange!.start, sel.timeRange!.end);
          result.current.transport.toggleLoop();
        }
      }
    });

    expect(result.current.transport.transport.loopEnabled).toBe(true);
    expect(result.current.transport.transport.loopStart).toBe(2);
    expect(result.current.transport.transport.loopEnd).toBe(6);
  });

  it("does not enable loop selection when domain mismatches (score active with performance selection)", () => {
    const { result } = renderHook(() => useSession(), { wrapper: wrapperWithWorkspace });

    act(() => {
      result.current.transport.replaceSources([perfSrc, scoreSrc], "score");
      result.current.workspace.setSelection({
        timeRange: { start: 2, end: 6, domain: "performance" },
        provenance: { origin: "waveform", timeExact: true, measureApproximate: false },
      });
    });

    // After state is settled, simulate clicking "Loop selection"
    act(() => {
      if (result.current.workspace.workspace.selection?.timeRange && result.current.transport.transport.activeSource) {
        const sel = result.current.workspace.workspace.selection;
        const active = result.current.transport.transport.activeSource;
        const selDomain = sel.timeRange?.domain ?? null;
        const activeDomain = active.role === "score" ? "notation" : "performance";
        if (selDomain === activeDomain) {
          result.current.transport.setLoop(sel.timeRange!.start, sel.timeRange!.end);
          result.current.transport.toggleLoop();
        }
      }
    });

    // Loop should not be enabled because domains mismatch (selection performance, active notation)
    expect(result.current.transport.transport.loopEnabled).toBe(false);
  });
});
