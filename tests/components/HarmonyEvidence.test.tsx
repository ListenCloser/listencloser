import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import HarmonyEvidence, {
  groupHarmonicMoments,
  harmonicFunctionEvidenceLabel,
  romanNumeralEvidenceLabel,
} from "@/components/workspace/HarmonyEvidence";
import type { Insight } from "@/lib/domain.types";

function insight(
  id: string,
  kind: "chord" | "roman_numeral" | "harmonic_function",
  claim: string,
  start: number,
  end: number,
  evidence: Record<string, unknown>,
): Insight {
  return {
    id,
    version_id: "version-1",
    kind,
    claim,
    span: {
      start_seconds: start,
      end_seconds: end,
      start_beat: null,
      end_beat: null,
      start_measure: null,
      end_measure: null,
    },
    entity_ids: [],
    evidence,
    confidence: null,
    provenance: {},
    created_at: "2026-08-30T00:00:00Z",
    created_by: null,
    produced_by_job_id: null,
  } as Insight;
}

const chord = insight("chord-1", "chord", "C maj", 0, 2, { root: "C", quality: "maj" });
const numeral = insight("rn-1", "roman_numeral", "I (A minor)", 0, 2, {
  numeral: "I",
  key_context: "A minor",
});
const harmonicFunction = insight("hf-1", "harmonic_function", "TONIC (I)", 0, 2, {
  function: "TONIC",
  numeral: "I",
  key_context: "A minor",
});
const nextChord = insight("chord-2", "chord", "G min", 2, 4, { root: "G", quality: "min" });

describe("HarmonyEvidence", () => {
  it("groups derived labels into one row per shared musical moment", () => {
    const moments = groupHarmonicMoments([harmonicFunction, nextChord, numeral, chord], 120);

    expect(moments).toHaveLength(2);
    expect(moments[0]).toMatchObject({
      startSeconds: 0,
      chord: { id: "chord-1" },
      romanNumeral: { id: "rn-1" },
      harmonicFunction: { id: "hf-1" },
    });
    expect(moments[1]).toMatchObject({ startSeconds: 2, chord: { id: "chord-2" } });
  });

  it("removes duplicated key/numeral context from visible labels only", () => {
    expect(romanNumeralEvidenceLabel(numeral)).toBe("I");
    expect(harmonicFunctionEvidenceLabel(harmonicFunction)).toBe("Tonic");
  });

  it("keeps each compact evidence value independently seekable and selectable", async () => {
    const user = userEvent.setup();
    const onSeek = vi.fn();
    const setSelection = vi.fn();

    render(
      <HarmonyEvidence
        insights={[chord, numeral, harmonicFunction, nextChord]}
        bpm={120}
        onSeek={onSeek}
        setSelection={setSelection}
      />,
    );

    expect(screen.getByRole("table", { name: "Harmonic timeline" })).toBeInTheDocument();
    expect(screen.getByTitle("I (A minor)")).toHaveTextContent("I");
    expect(screen.getByTitle("TONIC (I)")).toHaveTextContent("Tonic");
    expect(screen.queryByText("A minor")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^Degree I at 0:00\./ }));

    expect(onSeek).toHaveBeenCalledWith(0);
    expect(setSelection).toHaveBeenCalledWith({
      timeRange: { start: 0, end: 2, domain: "notation" },
      provenance: { origin: "score", timeExact: false, measureApproximate: true },
    });
  });
});
