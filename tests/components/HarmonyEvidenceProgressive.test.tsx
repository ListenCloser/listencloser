import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import HarmonyEvidence, {
  buildExactHarmonyProjection,
  harmonyEvidenceSummary,
} from "@/components/workspace/inspector/HarmonyEvidence";
import type { Insight } from "@/lib/domain.types";

function insight(
  id: string,
  kind: string,
  claim: string,
  evidence: Record<string, unknown> = {},
  versionId = "midi-v1",
): Insight {
  return {
    id,
    kind,
    claim,
    confidence: 0.9,
    evidence,
    version_id: versionId,
    provenance: { engine: "test" },
    span: { start_seconds: 4, end_seconds: 6 },
  } as unknown as Insight;
}

describe("HarmonyEvidence flat analysis presentation", () => {
  it("uses one primary Harmony column and only shows supported secondary theory labels", () => {
    const insights = [
      insight("chord", "chord", "C major"),
      insight("degree", "roman_numeral", "I (C major)", { numeral: "I" }),
    ];

    render(
      <HarmonyEvidence
        insights={insights}
        bpm={120}
        onSeek={vi.fn()}
        setSelection={vi.fn()}
      />,
    );

    expect(screen.getByRole("columnheader", { name: "Harmony" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Degree" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Function" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^C major$/ })).toBeInTheDocument();
    expect(screen.getByText("Degree", { exact: true })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^I$/ })).toBeInTheDocument();
    expect(screen.queryByText("—")).not.toBeInTheDocument();
    expect(screen.queryByText("Evidence details")).not.toBeInTheDocument();
  });

  it("describes the available analysis instead of surfacing a raw row count", () => {
    const chordOnly = [insight("chord", "chord", "C major")];
    const enriched = [
      ...chordOnly,
      insight("degree", "roman_numeral", "I (C major)", { numeral: "I" }),
      insight("function", "harmonic_function", "Tonic", { function: "tonic" }),
    ];

    expect(harmonyEvidenceSummary(chordOnly, 120)).toBe("Chord timeline");
    expect(harmonyEvidenceSummary(enriched, 120)).toContain("degree and function context");
  });

  it("projects only explicit seconds from the exact Piano Roll Version", () => {
    const exact = [
      insight("chord", "chord", "C major"),
      insight("degree", "roman_numeral", "I (C major)", { numeral: "I" }),
      insight("function", "harmonic_function", "Tonic", { function: "tonic" }),
      insight("other-version", "chord", "G major", {}, "midi-v2"),
    ];

    const projection = buildExactHarmonyProjection(exact, "midi-v1", 120);

    expect(projection).toEqual([
      expect.objectContaining({
        id: "chord",
        versionId: "midi-v1",
        start: 4,
        end: 6,
        chord: "C major",
        romanNumeral: "I",
        harmonicFunction: "Tonic",
        provenance: { engine: "test" },
      }),
    ]);
  });

  it("fails closed when a chord only has beat-relative timing", () => {
    const beatOnly = insight("beat-chord", "chord", "A minor");
    beatOnly.span = {
      ...beatOnly.span,
      start_seconds: null,
      end_seconds: null,
      start_beat: 8,
      end_beat: 12,
    };

    expect(buildExactHarmonyProjection([beatOnly], "midi-v1", 120)).toEqual([]);
  });

  it("treats an explicit no-chord marker as local abstention", () => {
    const noChord = insight("no-chord", "chord", "N", { root: "N", quality: "N" });

    expect(buildExactHarmonyProjection([noChord], "midi-v1", 120)).toEqual([]);
  });
});
