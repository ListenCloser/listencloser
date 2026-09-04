import { describe, expect, it } from "vitest";
import type { WorkBundle } from "@/lib/domain.types";
import { findMelodyAuditionJob, findMelodyPlaybackSource } from "@/lib/melody-playback-client";

const bundle = {
  work: { id: "work-1", project_id: "project-1" },
  artifacts: [
    {
      artifact: { id: "artifact-transcription", kind: "audio_rendered" },
      latest_version: {
        id: "audio-transcription",
        metadata: { representation: "transcription_playback" },
      },
      versions: [],
      signed_url: "/transcription.wav",
    },
    {
      artifact: { id: "artifact-melody", kind: "audio_rendered" },
      latest_version: {
        id: "audio-melody",
        metadata: {
          representation: "melody_playback",
          source_midi_version_id: "midi-v1",
          source_insight_id: "melody-1",
        },
      },
      versions: [],
      signed_url: "/melody.wav",
    },
  ],
  jobs: [
    {
      id: "old-job",
      created_at: "2026-09-04T10:00:00Z",
      capability: { name: "melody_audition" },
      input_version_ids: ["midi-v1"],
      parameters: { insight_id: "melody-1" },
      lifecycle: { current: "failed" },
    },
    {
      id: "new-job",
      created_at: "2026-09-04T11:00:00Z",
      capability: { name: "melody_audition" },
      input_version_ids: ["midi-v1"],
      parameters: { insight_id: "melody-1" },
      lifecycle: { current: "running" },
    },
  ],
} as unknown as WorkBundle;

describe("melody playback discovery", () => {
  it("finds only the durable source for the exact MIDI Version and melody Insight", () => {
    expect(findMelodyPlaybackSource(bundle, "midi-v1", "melody-1")).toEqual({
      id: "audio-melody",
      url: "/melody.wav",
    });
    expect(findMelodyPlaybackSource(bundle, "midi-v2", "melody-1")).toBeNull();
    expect(findMelodyPlaybackSource(bundle, "midi-v1", "melody-2")).toBeNull();
  });

  it("returns the newest matching audition job rather than a stale terminal attempt", () => {
    expect(findMelodyAuditionJob(bundle, "midi-v1", "melody-1")?.id).toBe("new-job");
    expect(findMelodyAuditionJob(bundle, "midi-v2", "melody-1")).toBeNull();
  });
});
