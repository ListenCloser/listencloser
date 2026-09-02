import { describe, expect, it } from "vitest";
import {
  GENERAL_TRANSCRIPTION_LIMITATION,
  getSymbolicTranscriptionQualification,
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
});
