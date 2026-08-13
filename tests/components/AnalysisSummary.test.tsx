import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Insight } from "@/lib/domain.types";
import { useWorkspace } from "@/lib/stores/workspace";
import { AnalysisSummary } from "@/components/workspace/AnalysisSummary";

vi.mock("@/lib/stores/workspace", () => ({
  useWorkspace: vi.fn(),
}));

const mockedUseWorkspace = vi.mocked(useWorkspace);

function insight(overrides: Partial<Insight>): Insight {
  return {
    id: overrides.id ?? "insight-1",
    version_id: "version-1",
    kind: overrides.kind ?? "rhythm",
    claim: overrides.claim ?? "Rhythm: 4 notes/sec",
    span: { start_seconds: null, end_seconds: null, start_beat: null, end_beat: null, start_measure: null, end_measure: null },
    entity_ids: [],
    evidence: overrides.evidence ?? {},
    confidence: overrides.confidence ?? null,
    provenance: overrides.provenance ?? {},
    created_at: new Date().toISOString(),
    created_by: null,
    produced_by_job_id: null,
  };
}

function seed(insights: Insight[]) {
  mockedUseWorkspace.mockReturnValue({ workspace: { insights } } as ReturnType<typeof useWorkspace>);
}

beforeEach(() => {
  mockedUseWorkspace.mockReset();
});

describe("AnalysisSummary truthfulness", () => {
  it("shows a subtle unavailable state (not empty fact cards) when no supported evidence exists", () => {
    seed([insight({ kind: "rhythm" })]);
    render(<AnalysisSummary onSeek={() => {}} bpm={120} />);

    expect(screen.getByText("The automatic summary came back empty")).toBeInTheDocument();
    expect(screen.queryByText("Not confidently detected")).not.toBeInTheDocument();
  });

  it("does not surface a weak key (confidence < 0.5) as a primary fact", () => {
    seed([
      insight({ id: "weak-key", kind: "key", claim: "Key: C major", confidence: 0.3, evidence: { tonic: "C", mode: "major" } }),
      insight({ id: "rhythm", kind: "rhythm" }),
    ]);
    render(<AnalysisSummary onSeek={() => {}} bpm={120} />);

    expect(screen.queryByText("C major")).not.toBeInTheDocument();
    expect(screen.getByText("The automatic summary came back empty")).toBeInTheDocument();
  });

  it("renders supported evidence (confidence >= 0.5) normally", () => {
    seed([
      insight({ id: "strong-key", kind: "key", claim: "Key: A minor", confidence: 0.82, evidence: { tonic: "A", mode: "minor" } }),
      insight({ id: "tempo", kind: "tempo", claim: "Tempo: 112 BPM", confidence: 0.9, evidence: { bpm: 112 } }),
      insight({ id: "meter", kind: "time_signature", claim: "Time Signature: 4/4", confidence: 0.9, evidence: { numerator: 4, denominator: 4 } }),
    ]);
    render(<AnalysisSummary onSeek={() => {}} bpm={120} />);

    expect(screen.getByText("A minor")).toBeInTheDocument();
    expect(screen.getByText("112 BPM")).toBeInTheDocument();
    expect(screen.getByText("4/4")).toBeInTheDocument();
    expect(screen.queryByText("Not confidently detected")).not.toBeInTheDocument();
  });

  it("prefers audio_tempo over the MIDI tempo fact", () => {
    seed([
      insight({ id: "midi-tempo", kind: "tempo", claim: "Tempo: 120 BPM", confidence: 0.9, evidence: { bpm: 120 } }),
      insight({ id: "audio-tempo", kind: "audio_tempo", claim: "Recording tempo: 96 BPM", confidence: 0.7, evidence: { bpm: 96 } }),
    ]);
    render(<AnalysisSummary onSeek={() => {}} bpm={120} />);

    expect(screen.getByText("96 BPM")).toBeInTheDocument();
    expect(screen.queryByText("120 BPM")).not.toBeInTheDocument();
  });

  it("notes which summary details were not detected confidently", () => {
    seed([
      insight({ id: "strong-key", kind: "key", claim: "Key: A minor", confidence: 0.82, evidence: { tonic: "A", mode: "minor" } }),
      insight({ id: "tempo", kind: "tempo", claim: "Tempo: 112 BPM", confidence: 0.9, evidence: { bpm: 112 } }),
    ]);
    render(<AnalysisSummary onSeek={() => {}} bpm={120} />);

    expect(screen.getByText("A minor")).toBeInTheDocument();
    expect(screen.getByText("112 BPM")).toBeInTheDocument();
    expect(screen.getByText("The time signature wasn't detected confidently.")).toBeInTheDocument();
  });
});
