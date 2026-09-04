import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ScoreSourceControl from "@/components/workspace/ScoreSourceControl";

describe("ScoreSourceControl", () => {
  it("presents every attached source beside generated interpretations", () => {
    render(
      <ScoreSourceControl
        selection={{ kind: "source", versionId: "source-v2" }}
        sources={[
          { versionId: "source-v1", label: "Attached · first.musicxml" },
          { versionId: "source-v2", label: "Attached · second.musicxml" },
        ]}
        onSelectEngine={vi.fn()}
        onSelectSource={vi.fn()}
        onAttach={vi.fn()}
      />,
    );

    const source = screen.getByRole("combobox", { name: "Score source" });
    expect(source).toHaveValue("source:source-v2");
    expect(screen.getByRole("option", { name: "Attached · first.musicxml" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Attached · second.musicxml" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "MuseScore" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "PM2S · MuseScore import" })).toBeInTheDocument();
  });

  it("emits exact source Version ids and generated engine choices", async () => {
    const user = userEvent.setup();
    const onSelectEngine = vi.fn();
    const onSelectSource = vi.fn();
    render(
      <ScoreSourceControl
        selection={{ kind: "engine", engine: "musescore" }}
        sources={[{ versionId: "source-v7", label: "Attached · score.musicxml" }]}
        onSelectEngine={onSelectEngine}
        onSelectSource={onSelectSource}
        onAttach={vi.fn()}
      />,
    );

    const source = screen.getByRole("combobox", { name: "Score source" });
    await user.selectOptions(source, "source:source-v7");
    expect(onSelectSource).toHaveBeenLastCalledWith("source-v7");

    await user.selectOptions(source, "engine:pm2s");
    expect(onSelectEngine).toHaveBeenLastCalledWith("pm2s");
  });

  it("keeps saved score choices usable when new attachment is disabled", () => {
    render(
      <ScoreSourceControl
        selection={{ kind: "source", versionId: "source-v1" }}
        sources={[{ versionId: "source-v1", label: "Attached · score.musicxml" }]}
        attachDisabled
        onSelectEngine={vi.fn()}
        onSelectSource={vi.fn()}
        onAttach={vi.fn()}
      />,
    );

    expect(screen.getByRole("combobox", { name: "Score source" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Attach score" })).toBeDisabled();
  });

  it("exposes a compact attach action", async () => {
    const user = userEvent.setup();
    const onAttach = vi.fn();
    render(
      <ScoreSourceControl
        selection={null}
        sources={[]}
        onSelectEngine={vi.fn()}
        onSelectSource={vi.fn()}
        onAttach={onAttach}
      />,
    );

    expect(screen.getByRole("option", { name: "Choose score" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Attach score" }));
    expect(onAttach).toHaveBeenCalledTimes(1);
  });
});
