import {
  buildRenderedScoreNoteIdentities,
  matchRenderedScoreNoteEvent,
  relativeMeasurePosition,
  type AlignmentScoreEventIdentity,
  type RenderedScoreNoteIdentity,
} from "@/lib/score-note-identity";

function rendered(overrides: Partial<RenderedScoreNoteIdentity> = {}): RenderedScoreNoteIdentity {
  return {
    measureIndex: 3,
    pitch: 64,
    voice: 1,
    staff: 2,
    isGrace: false,
    relativeOnset: { numerator: 1, denominator: 6 },
    noteheads: [document.createElementNS("http://www.w3.org/2000/svg", "path")],
    ...overrides,
  };
}

function candidate(
  eventId: string,
  overrides: Partial<AlignmentScoreEventIdentity> = {},
): AlignmentScoreEventIdentity {
  return {
    event_id: eventId,
    measure_index: 3,
    pitch: 64,
    voice: 1,
    staff: 2,
    is_grace: false,
    rel_onset_div: 320,
    total_measure_divs: 1920,
    ...overrides,
  };
}

describe("relativeMeasurePosition", () => {
  it("keeps OSMD score coordinates rational instead of converting to seconds", () => {
    expect(relativeMeasurePosition(
      { Numerator: 1, Denominator: 8, WholeValue: 0 },
      { Numerator: 3, Denominator: 4, WholeValue: 0 },
    )).toEqual({ numerator: 1, denominator: 6 });
  });

  it("handles whole-value fractions exactly", () => {
    expect(relativeMeasurePosition(
      { Numerator: 1, Denominator: 2, WholeValue: 1 },
      { Numerator: 0, Denominator: 1, WholeValue: 2 },
    )).toEqual({ numerator: 3, denominator: 4 });
  });
});

describe("matchRenderedScoreNoteEvent", () => {
  it("matches equivalent rational positions across different division resolutions", () => {
    const result = matchRenderedScoreNoteEvent(rendered(), [
      candidate("s1", { rel_onset_div: 160, total_measure_divs: 960 }),
    ]);
    expect(result?.event_id).toBe("s1");
  });

  it("uses measure, pitch, voice, staff, grace and rational onset together", () => {
    const result = matchRenderedScoreNoteEvent(rendered(), [
      candidate("wrong-measure", { measure_index: 2 }),
      candidate("wrong-pitch", { pitch: 65 }),
      candidate("wrong-voice", { voice: 2 }),
      candidate("wrong-staff", { staff: 1 }),
      candidate("wrong-grace", { is_grace: true }),
      candidate("wrong-onset", { rel_onset_div: 640 }),
      candidate("right"),
    ]);
    expect(result?.event_id).toBe("right");
  });

  it("fails closed for same-identity unison ambiguity", () => {
    expect(matchRenderedScoreNoteEvent(rendered(), [candidate("s1"), candidate("s2")])).toBeNull();
  });

  it("fails closed when parser metrical identity is unavailable", () => {
    expect(matchRenderedScoreNoteEvent(rendered(), [
      candidate("missing", { rel_onset_div: null }),
    ])).toBeNull();
    expect(matchRenderedScoreNoteEvent(rendered(), [
      candidate("invalid", { total_measure_divs: 0 }),
    ])).toBeNull();
  });
});

describe("buildRenderedScoreNoteIdentities", () => {
  it("derives identity from OSMD source objects and not playback time or pixels", () => {
    const notehead = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const osmd = {
      GraphicSheet: {
        MeasureList: [[{
          staffEntries: [{
            graphicalVoiceEntries: [{
              notes: [{
                sourceNote: {
                  halfTone: 64,
                  IsGraceNote: false,
                  ParentVoiceEntry: {
                    Timestamp: { Numerator: 1, Denominator: 8, WholeValue: 0 },
                    ParentVoice: { VoiceId: 1 },
                    IsGrace: false,
                  },
                  ParentStaffEntry: { ParentStaff: { Id: 2 } },
                  SourceMeasure: {
                    measureListIndex: 3,
                    Duration: { Numerator: 3, Denominator: 4, WholeValue: 0 },
                  },
                  isRest: () => false,
                },
                getNoteheadSVGs: () => [notehead],
              }],
            }],
          }],
        }]],
      },
    };

    expect(buildRenderedScoreNoteIdentities(osmd)).toEqual([{
      measureIndex: 3,
      pitch: 64,
      voice: 1,
      staff: 2,
      isGrace: false,
      relativeOnset: { numerator: 1, denominator: 6 },
      noteheads: [notehead],
    }]);
  });

  it("withholds notes when exact source identity is incomplete", () => {
    const osmd = {
      GraphicSheet: {
        MeasureList: [[{
          staffEntries: [{
            graphicalVoiceEntries: [{
              notes: [{
                sourceNote: {
                  halfTone: 60,
                  ParentVoiceEntry: {
                    Timestamp: { Numerator: 0, Denominator: 1 },
                    ParentVoice: {},
                  },
                  ParentStaffEntry: { ParentStaff: { Id: 1 } },
                  SourceMeasure: {
                    measureListIndex: 0,
                    Duration: { Numerator: 1, Denominator: 1 },
                  },
                },
                getNoteheadSVGs: () => [document.createElement("span")],
              }],
            }],
          }],
        }]],
      },
    };

    expect(buildRenderedScoreNoteIdentities(osmd)).toEqual([]);
  });
});
