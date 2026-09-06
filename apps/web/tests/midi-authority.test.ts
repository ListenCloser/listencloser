import { describe, expect, it } from "vitest";
import type { WorkBundle } from "../src/lib/domain.types";
import {
  describeMidiRepresentation,
  resolveExplicitPianoRollMidi,
  resolveMidiAuthority,
} from "../src/lib/midi-authority";

function artifact(
  id: string,
  kind: string,
  versionId: string,
  options: {
    parentVersionId?: string | null;
    producedByJobId?: string | null;
    metadata?: Record<string, unknown>;
    signedUrl?: string | null;
  } = {},
) {
  return {
    artifact: { id, work_id: "work", kind },
    latest_version: {
      id: versionId,
      artifact_id: id,
      parent_version_id: options.parentVersionId ?? null,
      produced_by_job_id: options.producedByJobId ?? null,
      metadata: options.metadata ?? {},
    },
    versions: [],
    signed_url: options.signedUrl === undefined
      ? `https://example.test/${versionId}`
      : options.signedUrl,
  };
}

function bundle(): WorkBundle {
  return {
    work: { id: "work" },
    jobs: [
      { id: "correct-job", capability: { name: "correct" } },
      { id: "variation-job", capability: { name: "variation" } },
      { id: "score-job", capability: { name: "score" } },
    ],
    artifacts: [
      artifact("creative", "midi_corrected", "creative-v1", {
        parentVersionId: "performance-v1",
        producedByJobId: "variation-job",
        metadata: { operation: "transpose", semitones: 2 },
      }),
      artifact("pm2s", "midi_corrected", "pm2s-v1", {
        parentVersionId: "performance-v1",
        metadata: { score_engine_requested: "pm2s" },
      }),
      artifact("notation", "midi_corrected", "notation-v1", {
        parentVersionId: "performance-v1",
        producedByJobId: "score-job",
        metadata: { score_engine_requested: "musescore" },
      }),
      artifact("edited", "midi_corrected", "edited-v1", {
        parentVersionId: "performance-v1",
        producedByJobId: "correct-job",
      }),
      artifact("ambiguous", "midi_corrected", "ambiguous-v1", {
        parentVersionId: "performance-v1",
      }),
      artifact("performance", "midi_performance", "performance-v1"),
    ],
  } as unknown as WorkBundle;
}

function descriptorRole(work: WorkBundle, artifactId: string) {
  const item = work.artifacts.find((candidate) => candidate.artifact.id === artifactId);
  if (!item) throw new Error(`missing fixture artifact ${artifactId}`);
  return describeMidiRepresentation(work, item)?.role;
}

describe("describeMidiRepresentation", () => {
  it("distinguishes current MIDI producer roles from durable provenance", () => {
    const work = bundle();
    expect(descriptorRole(work, "performance")).toBe("performance_transcription");
    expect(descriptorRole(work, "edited")).toBe("edited_performance");
    expect(descriptorRole(work, "creative")).toBe("creative_take");
    expect(descriptorRole(work, "pm2s")).toBe("score_reconstruction");
    expect(descriptorRole(work, "notation")).toBe("notation_normalized");
  });

  it("fails closed for a legacy midi_corrected row with no semantic provenance", () => {
    expect(descriptorRole(bundle(), "ambiguous")).toBe("unknown");
  });
});

describe("resolveMidiAuthority", () => {
  it("keeps the default Piano Roll on exact performance evidence regardless of derived artifact order", () => {
    const authority = resolveMidiAuthority(bundle());
    expect(authority.canonicalPerformance?.versionId).toBe("performance-v1");
    expect(authority.defaultPianoRoll?.versionId).toBe("performance-v1");
  });

  it("does not guess a default from corrected, creative, score, or ambiguous MIDI", () => {
    const work = bundle();
    work.artifacts = work.artifacts.filter((item) => item.artifact.kind !== "midi_performance");
    const authority = resolveMidiAuthority(work);
    expect(authority.canonicalPerformance).toBeNull();
    expect(authority.defaultPianoRoll).toBeNull();
  });
});

describe("resolveExplicitPianoRollMidi", () => {
  it("allows exact intentional focus of edited performance and creative takes", () => {
    const work = bundle();
    expect(resolveExplicitPianoRollMidi(work, "edited-v1")?.role).toBe("edited_performance");
    expect(resolveExplicitPianoRollMidi(work, "creative-v1")?.role).toBe("creative_take");
  });

  it("never treats score-domain or ambiguous MIDI as performance Piano Roll authority", () => {
    const work = bundle();
    expect(resolveExplicitPianoRollMidi(work, "pm2s-v1")).toBeNull();
    expect(resolveExplicitPianoRollMidi(work, "notation-v1")).toBeNull();
    expect(resolveExplicitPianoRollMidi(work, "ambiguous-v1")).toBeNull();
  });
});
