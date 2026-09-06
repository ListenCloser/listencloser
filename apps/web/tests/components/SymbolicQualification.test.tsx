import { useEffect } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import RepresentationStack from "@/components/workspace/RepresentationStack";
import { qualifySymbolicSourceLabel } from "@/lib/transcription-qualification";
import { useWorkspace, WorkspaceProvider } from "@/lib/stores/workspace";

vi.mock("@/lib/score-renderer", () => ({ preloadScoreRenderer: vi.fn() }));

vi.mock("@/components/workspace/representations/registry", () => {
  const score = {
    id: "score",
    title: "Score",
    description: "test score",
    temporal: true,
    available: () => true,
    component: () => <div data-testid="score-view" />,
  };
  return {
    REPRESENTATIONS: [score],
    availableRepresentations: () => [score],
  };
});

function ScoreHarness({ profile }: { profile: "auto" | "solo_piano" }) {
  const { replaceRepresentations } = useWorkspace();

  useEffect(() => {
    replaceRepresentations([{
      kind: "score",
      label: "Score",
      sourceUrl: "score.musicxml",
      sourceLabel: qualifySymbolicSourceLabel("Notation draft", { transcription_profile: profile }),
      confidence: null,
      provenance: "score interpretation",
      musicxml: "<score-partwise />",
    }]);
  }, [profile, replaceRepresentations]);

  return null;
}

describe("symbolic transcription qualification", () => {
  it("surfaces the persisted Auto limitation with a derived Score", async () => {
    render(
      <WorkspaceProvider>
        <ScoreHarness profile="auto" />
        <RepresentationStack signedIn canImport />
      </WorkspaceProvider>,
    );

    expect(await screen.findByRole("note", { name: "Symbolic representation source" })).toHaveTextContent(
      "Notation draft · General transcription draft — dense or full mixes may miss notes or add extra notes.",
    );
  });

  it("does not show the general-Auto warning for persisted solo-piano output", async () => {
    render(
      <WorkspaceProvider>
        <ScoreHarness profile="solo_piano" />
        <RepresentationStack signedIn canImport />
      </WorkspaceProvider>,
    );

    const source = await screen.findByRole("note", { name: "Symbolic representation source" });
    expect(source).toHaveTextContent("Notation draft");
    expect(source).not.toHaveTextContent("dense or full mixes");
  });
});
