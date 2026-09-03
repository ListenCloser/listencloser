import { describe, expect, it } from "vitest";
import {
  GENERAL_TRANSCRIPTION_LIMITATION,
  getSymbolicTranscriptionQualification,
  qualifySymbolicSourceLabel,
} from "@/lib/transcription-qualification";

describe("getSymbolicTranscriptionQualification", () => {
  it("qualifies persisted general Auto transcription", () => {
    expect(getSymbolicTranscriptionQualification({ transcription_profile: "auto" }))
      .toBe(GENERAL_TRANSCRIPTION_LIMITATION);
  });

  it("does not apply the general-Auto limitation to persisted solo-piano transcription", () => {
    expect(getSymbolicTranscriptionQualification({ transcription_profile: "solo_piano" })).toBeNull();
  });

  it("does not invent a qualification when persisted authority is absent or unknown", () => {
    expect(getSymbolicTranscriptionQualification(undefined)).toBeNull();
    expect(getSymbolicTranscriptionQualification({})).toBeNull();
    expect(getSymbolicTranscriptionQualification({ transcription_profile: "future_profile" })).toBeNull();
  });

  it("applies the same persisted Auto limitation to Piano Roll and derived Score labels", () => {
    const metadata = { transcription_profile: "auto" };

    expect(qualifySymbolicSourceLabel("42 detected notes", metadata)).toBe(
      `42 detected notes · ${GENERAL_TRANSCRIPTION_LIMITATION}`,
    );
    expect(qualifySymbolicSourceLabel("Notation draft", metadata)).toBe(
      `Notation draft · ${GENERAL_TRANSCRIPTION_LIMITATION}`,
    );
  });

  it("leaves solo-piano symbolic labels unqualified by the general-Auto warning", () => {
    const metadata = { transcription_profile: "solo_piano" };

    expect(qualifySymbolicSourceLabel("42 detected notes", metadata)).toBe("42 detected notes");
    expect(qualifySymbolicSourceLabel("Notation draft", metadata)).toBe("Notation draft");
  });
});
