import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SimilarMoments from "@/components/workspace/inspector/SimilarMoments";
import type { MusicalSelection } from "@/lib/stores/workspace";

const mocks = vi.hoisted(() => ({
  workspace: {
    activeWorkId: "work-1" as string | null,
    representations: [
      { kind: "waveform" as const, versionId: "audio-version-1" },
    ],
    selection: null as MusicalSelection | null,
  },
  transport: {
    activeSource: { role: "original" } as { role: string } | null,
    sources: [{ id: "original", role: "original" }],
  },
  setSelection: vi.fn(),
  seek: vi.fn(),
  play: vi.fn(),
  setActiveSource: vi.fn(),
  requestWorkspaceOrientation: vi.fn(),
  getSimilarMoments: vi.fn(),
}));

vi.mock("@/lib/stores/workspace", () => ({
  useWorkspace: () => ({
    workspace: mocks.workspace,
    setSelection: mocks.setSelection,
  }),
}));

vi.mock("@/lib/stores/transport", () => ({
  useTransport: () => ({
    transport: mocks.transport,
    audioRef: { current: null },
    seek: mocks.seek,
    play: mocks.play,
    setActiveSource: mocks.setActiveSource,
  }),
}));

vi.mock("@/lib/inspector/orientation", () => ({
  requestWorkspaceOrientation: mocks.requestWorkspaceOrientation,
}));

vi.mock("@/lib/relation-api-client", () => ({
  getSimilarMoments: mocks.getSimilarMoments,
}));

function selection(start: number, end: number, timeExact = true): MusicalSelection {
  return {
    timeRange: { start, end, domain: "performance" },
    provenance: { origin: "waveform", timeExact, measureApproximate: !timeExact },
  };
}

function supportedResponse() {
  return {
    status: "supported" as const,
    evidence_report_version_id: "report-version-1",
    observation: {
      source_version_id: "audio-version-1",
      evidence_report_version_id: "report-version-1",
      evidence_report_type: "perceptual_series" as const,
      preprocessing_version: "perceptual_mono_22050_pcm16_v1",
      sample_rate: 22050,
      query_start_seconds: 10,
      query_end_seconds: 14,
      max_matches: 3,
      method: {
        id: "perceptual_descriptor_shape" as const,
        version: "1.0" as const,
        dimensions: [
          "onset_strength",
          "spectral_centroid",
          "band_low",
          "band_low_mid",
          "band_mid",
          "band_high",
        ],
        distance: "mean_length_normalized_z_euclidean" as const,
        candidate_window: "same_evidence_frame_count_as_query" as const,
        overlap_exclusion:
          "exclude_query_overlap_and_mutually_overlapping_returned_windows" as const,
        score_semantics: "lower_is_closer_under_this_method_not_confidence" as const,
        semantic_claims: "none" as const,
        parameters: { minimum_query_frames: 4, max_matches: 3 },
      },
      matches: [
        {
          start_seconds: 30,
          end_seconds: 34,
          distance: 0.125,
          component_distances: {
            onset_strength: 0.1,
            spectral_centroid: 0.2,
            band_low: 0.1,
            band_low_mid: 0.1,
            band_mid: 0.1,
            band_high: 0.15,
          },
        },
      ],
      no_match_reason: null,
    },
    reasons: [],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.workspace.activeWorkId = "work-1";
  mocks.workspace.representations = [
    { kind: "waveform", versionId: "audio-version-1" },
  ];
  mocks.workspace.selection = selection(10, 14);
  mocks.transport.activeSource = { role: "original" };
});

describe("SimilarMoments", () => {
  it("queries only after an exact selection is explicitly submitted", async () => {
    const user = userEvent.setup();
    mocks.getSimilarMoments.mockResolvedValue(supportedResponse());
    render(<SimilarMoments />);

    expect(screen.getByText("Selected 0:10–0:14")).toBeVisible();
    expect(mocks.getSimilarMoments).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Find similar moments" }));

    expect(mocks.getSimilarMoments).toHaveBeenCalledWith("work-1", {
      source_version_id: "audio-version-1",
      query_start_seconds: 10,
      query_end_seconds: 14,
      max_matches: 3,
    });
    expect(await screen.findByText("0:30–0:34")).toBeVisible();
    expect(screen.getByText(/not motif, chorus, melody, or section labels/i)).toBeVisible();
  });

  it("hears a candidate through shared transport without replacing the captured query", async () => {
    const user = userEvent.setup();
    mocks.getSimilarMoments.mockResolvedValue(supportedResponse());
    render(<SimilarMoments />);

    await user.click(screen.getByRole("button", { name: "Find similar moments" }));
    await screen.findByText("0:30–0:34");
    await user.click(screen.getByRole("button", { name: "Hear" }));

    expect(mocks.seek).toHaveBeenCalledWith(30);
    expect(mocks.play).toHaveBeenCalledTimes(1);
    expect(mocks.setSelection).not.toHaveBeenCalled();
    expect(screen.getByText("Selected 0:10–0:14")).toBeVisible();
  });

  it("focuses a candidate through shared selection while retaining the original subject", async () => {
    const user = userEvent.setup();
    mocks.getSimilarMoments.mockResolvedValue(supportedResponse());
    const view = render(<SimilarMoments />);

    await user.click(screen.getByRole("button", { name: "Find similar moments" }));
    await screen.findByText("0:30–0:34");
    await user.click(screen.getByRole("button", { name: "Focus" }));

    expect(mocks.seek).toHaveBeenCalledWith(30);
    expect(mocks.setSelection).toHaveBeenCalledWith({
      timeRange: { start: 30, end: 34, domain: "performance" },
      provenance: { origin: null, timeExact: true, measureApproximate: false },
    });
    expect(mocks.requestWorkspaceOrientation).toHaveBeenCalledTimes(1);

    mocks.workspace.selection = selection(30, 34);
    view.rerender(<SimilarMoments />);
    expect(screen.getByText("Selected 0:10–0:14")).toBeVisible();
  });

  it("renders distance as method evidence rather than confidence", async () => {
    const user = userEvent.setup();
    mocks.getSimilarMoments.mockResolvedValue(supportedResponse());
    render(<SimilarMoments />);

    await user.click(screen.getByRole("button", { name: "Find similar moments" }));
    await screen.findByText("0:30–0:34");
    await user.click(screen.getByText("Method & evidence"));

    expect(screen.getByText(/Aggregate distance: 0.125. This value is not confidence/i)).toBeVisible();
    expect(screen.getByText(/Evidence Version: report-version-1/i)).toBeVisible();
    expect(screen.getByText(/Source Version: audio-version-1/i)).toBeVisible();
  });

  it("does not fabricate a semantic no-match threshold", async () => {
    const user = userEvent.setup();
    const response = supportedResponse();
    response.observation.matches = [];
    response.observation.no_match_reason = "no_valid_non_overlapping_candidate_windows";
    mocks.getSimilarMoments.mockResolvedValue(response);
    render(<SimilarMoments />);

    await user.click(screen.getByRole("button", { name: "Find similar moments" }));

    expect(await screen.findByText(/No valid non-overlapping candidate window/i)).toBeVisible();
    expect(screen.getByText(/does not yet use a semantic no-match threshold/i)).toBeVisible();
  });

  it("stays hidden for approximate selections", () => {
    mocks.workspace.selection = selection(10, 14, false);
    render(<SimilarMoments />);

    expect(screen.queryByRole("region", { name: "Similar moments" })).not.toBeInTheDocument();
  });
});
