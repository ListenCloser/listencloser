import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import HarmonyEvidence, { harmonyEvidenceSummary } from "@/components/workspace/inspector/HarmonyEvidence";
import type { Insight } from "@/lib/domain.types";

function insight(id: string, kind: string, claim: string, evidence: Record<string, unknown> = {}): Insight {
  return {
    id,
    kind,
    claim,
    confidence: 0.9,
    evidence,
    span: { start_seconds: 4, end_seconds: 6 },
  } as unknown as Insight;
}

describe("HarmonyEvidence progressive disclosure", () => {
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
  });

  it("describes the available evidence instead of surfacing a raw row count", () => {
    const chordOnly = [insight("chord", "chord", "C major")];
    const enriched = [
      ...chordOnly,
      insight("degree", "roman_numeral", "I (C major)", { numeral: "I" }),
      insight("function", "harmonic_function", "Tonic", { function: "tonic" }),
    ];

    expect(harmonyEvidenceSummary(chordOnly, 120)).toBe("Chord timeline");
    expect(harmonyEvidenceSummary(enriched, 120)).toContain("degree and function context");
  });
});
