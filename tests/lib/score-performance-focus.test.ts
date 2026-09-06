import {
  resolveScorePerformanceFocus,
  type ScorePerformanceAlignmentReport,
} from "@/lib/score-performance-focus";
import type { RenderedScoreNoteIdentity } from "@/lib/score-note-identity";

const rendered: RenderedScoreNoteIdentity = {
  measureIndex: 0,
  pitch: 60,
  voice: 1,
  staff: 1,
  isGrace: false,
  relativeOnset: { numerator: 0, denominator: 1 },
  noteheads: [],
};

function report(overrides: Partial<ScorePerformanceAlignmentReport> = {}): ScorePerformanceAlignmentReport {
  return {
    score_version_id: "score-v1",
    performance_version_id: "midi-v1",
    sufficiency: "sufficient",
    projection_precision: "adequate",
    method: {
      package: "parangonar",
      package_version: "3.3.3",
      matcher: "DualDTWNoteMatcher",
    },
    relations: [{
      kind: "matched",
      score_events: [{ event_id: "s1" }],
      performance_events: [{ event_id: "p1" }],
    }],
    event_identity: {
      schema_version: 1,
      score_events: [{
        event_id: "s1",
        measure_index: 0,
        pitch: 60,
        voice: 1,
        staff: 1,
        is_grace: false,
        rel_onset_div: 0,
        total_measure_divs: 1920,
      }],
      performance_events: [{
        event_id: "p1",
        pitch: 60,
        onset_seconds: 1,
        duration_seconds: 0.5,
        velocity: 88,
      }],
    },
    ...overrides,
  };
}

const notes = [{
  id: "entity-1",
  pitch: 60,
  start: 1,
  end: 1.5,
  velocity: 88,
}];

describe("resolveScorePerformanceFocus", () => {
  it("resolves an admitted exact pair through both identity bridges", () => {
    expect(resolveScorePerformanceFocus(
      rendered,
      report(),
      "score-v1",
      "midi-v1",
      notes,
    )).toEqual({
      scoreEventId: "s1",
      performanceEventIds: ["p1"],
      pianoRollNoteIds: ["entity-1"],
    });
  });

  it("refuses to cross displayed Version authority", () => {
    expect(resolveScorePerformanceFocus(rendered, report(), "other-score", "midi-v1", notes)).toBeNull();
    expect(resolveScorePerformanceFocus(rendered, report(), "score-v1", "corrected-midi", notes)).toBeNull();
  });

  it("withholds insufficient and unsupported relations", () => {
    expect(resolveScorePerformanceFocus(
      rendered,
      report({ sufficiency: "insufficient" }),
      "score-v1",
      "midi-v1",
      notes,
    )).toBeNull();
    expect(resolveScorePerformanceFocus(
      rendered,
      report({ projection_precision: "unsupported" }),
      "score-v1",
      "midi-v1",
      notes,
    )).toBeNull();
  });

  it("does not project score-only evidence", () => {
    expect(resolveScorePerformanceFocus(
      rendered,
      report({
        relations: [{
          kind: "score_only",
          score_events: [{ event_id: "s1" }],
          performance_events: [],
        }],
      }),
      "score-v1",
      "midi-v1",
      notes,
    )).toBeNull();
  });

  it("fails closed when one score event appears in multiple relations", () => {
    const duplicated = report();
    duplicated.relations = [duplicated.relations[0], duplicated.relations[0]];
    expect(resolveScorePerformanceFocus(
      rendered,
      duplicated,
      "score-v1",
      "midi-v1",
      notes,
    )).toBeNull();
  });

  it("projects grouped performed events only when every child maps uniquely", () => {
    const grouped = report({
      relations: [{
        kind: "grouped",
        score_events: [{ event_id: "s1" }],
        performance_events: [{ event_id: "p1" }, { event_id: "p2" }],
      }],
      event_identity: {
        schema_version: 1,
        score_events: report().event_identity.score_events,
        performance_events: [
          report().event_identity.performance_events[0],
          {
            event_id: "p2",
            pitch: 64,
            onset_seconds: 1.5,
            duration_seconds: 0.25,
            velocity: 90,
          },
        ],
      },
    });

    expect(resolveScorePerformanceFocus(
      rendered,
      grouped,
      "score-v1",
      "midi-v1",
      [
        ...notes,
        { id: "entity-2", pitch: 64, start: 1.5, end: 1.75, velocity: 90 },
      ],
    )?.pianoRollNoteIds).toEqual(["entity-1", "entity-2"]);

    expect(resolveScorePerformanceFocus(
      rendered,
      grouped,
      "score-v1",
      "midi-v1",
      notes,
    )).toBeNull();
  });

  it("withholds a relation whose performed event descriptor is missing", () => {
    const missing = report();
    missing.event_identity.performance_events = [];
    expect(resolveScorePerformanceFocus(
      rendered,
      missing,
      "score-v1",
      "midi-v1",
      notes,
    )).toBeNull();
  });
});
