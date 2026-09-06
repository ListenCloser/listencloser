import {
  MIDI_SERIALIZATION_TOLERANCE_SECONDS,
  matchPerformanceEventToPianoRollNote,
  matchPerformanceEventsToPianoRollNoteIds,
  type AlignmentPerformanceEventIdentity,
  type PianoRollEntityNote,
} from "@/lib/performance-note-identity";

function event(
  eventId: string,
  overrides: Partial<AlignmentPerformanceEventIdentity> = {},
): AlignmentPerformanceEventIdentity {
  return {
    event_id: eventId,
    pitch: 64,
    onset_seconds: 2,
    duration_seconds: 0.5,
    velocity: 91,
    ...overrides,
  };
}

function note(id: string, overrides: Partial<PianoRollEntityNote> = {}): PianoRollEntityNote {
  return {
    id,
    pitch: 64,
    start: 2,
    end: 2.5,
    velocity: 91,
    ...overrides,
  };
}

describe("matchPerformanceEventToPianoRollNote", () => {
  it("accepts only bounded MIDI serialization drift", () => {
    const drift = MIDI_SERIALIZATION_TOLERANCE_SECONDS * 0.75;
    expect(matchPerformanceEventToPianoRollNote(event("p1"), [
      note("entity-1", { start: 2 + drift, end: 2.5 - drift }),
    ])?.id).toBe("entity-1");
  });

  it("does not use time alone", () => {
    expect(matchPerformanceEventToPianoRollNote(event("p1"), [
      note("wrong-pitch", { pitch: 65 }),
      note("wrong-velocity", { velocity: 90 }),
    ])).toBeNull();
  });

  it("does not choose the nearest candidate outside the bounded round-trip contract", () => {
    const outside = MIDI_SERIALIZATION_TOLERANCE_SECONDS + 0.0001;
    expect(matchPerformanceEventToPianoRollNote(event("p1"), [
      note("too-far", { start: 2 + outside, end: 2.5 + outside }),
    ])).toBeNull();
  });

  it("fails closed when two entities satisfy the same parser descriptor", () => {
    expect(matchPerformanceEventToPianoRollNote(event("p1"), [
      note("entity-1"),
      note("entity-2"),
    ])).toBeNull();
  });
});

describe("matchPerformanceEventsToPianoRollNoteIds", () => {
  it("requires every performed event in a grouped relation to map uniquely", () => {
    const events = [
      event("p1"),
      event("p2", { pitch: 67, onset_seconds: 2.5, duration_seconds: 0.25, velocity: 80 }),
    ];
    const notes = [
      note("entity-1"),
      note("entity-2", { pitch: 67, start: 2.5, end: 2.75, velocity: 80 }),
    ];
    expect(matchPerformanceEventsToPianoRollNoteIds(events, notes)).toEqual([
      "entity-1",
      "entity-2",
    ]);
  });

  it("withholds the whole projection when any event cannot be resolved", () => {
    expect(matchPerformanceEventsToPianoRollNoteIds([
      event("p1"),
      event("p2", { pitch: 67 }),
    ], [note("entity-1")])).toBeNull();
  });
});
