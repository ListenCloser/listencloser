import { describe, expect, it } from "vitest";
import {
  projectLandingDemoRange,
  projectLandingDemoTime,
  validateLandingDemoManifest,
  type LandingDemoManifest,
} from "@/lib/landing-demo";

const HASH_A = "a".repeat(64);
const HASH_B = "b".repeat(64);

function validManifest(): LandingDemoManifest {
  return {
    schemaVersion: 1,
    source: {
      assetPath: "/demo/source.m4a",
      sha256: HASH_A,
      provenance: "Canonical integration fixture; public-use approval tracked separately.",
      publicUseApproved: false,
      durationSeconds: 60,
    },
    window: {
      startSeconds: 10,
      endSeconds: 20,
    },
    waveform: {
      bins: [
        { min: -0.8, max: 0.7 },
        { min: -0.4, max: 0.5 },
      ],
    },
    notes: [
      {
        id: "note-1",
        pitch: 60,
        startSeconds: 9.5,
        endSeconds: 10.5,
        velocity: 92,
      },
      {
        id: "note-2",
        pitch: 64,
        startSeconds: 15,
        endSeconds: 16,
        velocity: null,
      },
    ],
    score: {
      musicxmlPath: "/demo/source.musicxml",
      sha256: HASH_B,
      measureStartsSeconds: [0, 5, 10, 15, 20, 25],
    },
    evidence: [
      {
        id: "evidence-1",
        kind: "density_change",
        label: "Note activity becomes denser",
        provenance: "deterministic note-event comparison",
        startSeconds: 14,
        endSeconds: 17,
      },
    ],
  };
}

describe("landing demo source-of-truth contract", () => {
  it("projects every temporal layer from the same seconds coordinate system", () => {
    const window = { startSeconds: 10, endSeconds: 20 };

    expect(projectLandingDemoTime(10, window)).toBe(0);
    expect(projectLandingDemoTime(15, window)).toBe(0.5);
    expect(projectLandingDemoTime(20, window)).toBe(1);
    expect(projectLandingDemoRange(8, 12, window)).toEqual({ start: 0, end: 0.2 });
    expect(projectLandingDemoRange(21, 22, window)).toBeNull();
  });

  it("rejects times outside the declared landing window instead of silently inventing/clamping positions", () => {
    const window = { startSeconds: 10, endSeconds: 20 };

    expect(() => projectLandingDemoTime(9.9, window)).toThrow(/outside/);
    expect(() => projectLandingDemoTime(20.1, window)).toThrow(/outside/);
    expect(() => projectLandingDemoRange(12, 12, window)).toThrow(/increasing/);
  });

  it("accepts an internally consistent engineering manifest before public-use approval", () => {
    expect(validateLandingDemoManifest(validManifest())).toEqual([]);
  });

  it("allows a landing excerpt to begin mid-measure while retaining real score alignment", () => {
    const manifest = validManifest();
    manifest.window = { startSeconds: 11, endSeconds: 14 };
    manifest.notes = [{
      id: "note-mid-measure",
      pitch: 67,
      startSeconds: 12,
      endSeconds: 13,
      velocity: 80,
    }];
    manifest.score.measureStartsSeconds = [0, 5, 10, 15, 20];
    manifest.evidence = [{
      id: "evidence-mid-measure",
      kind: "register",
      label: "Phrase sits higher here",
      provenance: "deterministic note-register comparison",
      startSeconds: 12,
      endSeconds: 13.5,
    }];

    expect(validateLandingDemoManifest(manifest)).toEqual([]);
  });

  it("blocks public landing use until provenance approval is explicit", () => {
    expect(validateLandingDemoManifest(validManifest(), { requirePublicUseApproval: true })).toContain(
      "source.publicUseApproved must be true before the manifest can ship on the public landing page",
    );
  });

  it("rejects hand-authored temporal geometry so render positions must come from seconds", () => {
    const manifest = validManifest() as LandingDemoManifest & { xPercent?: number };
    manifest.xPercent = 42;

    expect(validateLandingDemoManifest(manifest)).toContain(
      "manifest.xPercent must not be stored; derive temporal geometry from seconds at render time",
    );
  });

  it("rejects broken musical/source relationships", () => {
    const manifest = validManifest();
    manifest.waveform.bins[0] = { min: 0.9, max: 0.2 };
    manifest.notes[0].pitch = 200;
    manifest.notes[1].startSeconds = 30;
    manifest.notes[1].endSeconds = 31;
    manifest.score.measureStartsSeconds = [0, 9, 8];
    manifest.evidence[0].startSeconds = 30;
    manifest.evidence[0].endSeconds = 31;

    const errors = validateLandingDemoManifest(manifest);
    expect(errors).toEqual(expect.arrayContaining([
      "waveform.bins[0] must satisfy -1 <= min <= max <= 1",
      "notes[0].pitch must be an integer MIDI pitch from 0 to 127",
      "score.measureStartsSeconds must be strictly increasing",
      "evidence[0] must overlap the landing window",
    ]));
  });

  it("requires at least one real evidence span", () => {
    const manifest = validManifest();
    manifest.evidence = [];

    expect(validateLandingDemoManifest(manifest)).toContain(
      "evidence must contain at least one supported source-time span",
    );
  });
});
