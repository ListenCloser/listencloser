import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ListboxMenu from "@/components/ui/ListboxMenu";

describe("ListboxMenu", () => {
  it("opens on arrow keys, roves options, selects, and returns focus", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <ListboxMenu
        triggerLabel="Original"
        triggerAria="Playback source: Original"
        selectedId="original"
        options={[
          { id: "original", label: "Original" },
          { id: "transcription", label: "Transcription" },
          { id: "score", label: "Score" },
        ]}
        onSelect={onSelect}
      />,
    );

    const trigger = screen.getByRole("button", { name: "Playback source: Original" });
    trigger.focus();
    await user.keyboard("{ArrowDown}");

    const original = screen.getByRole("option", { name: "Original" });
    const transcription = screen.getByRole("option", { name: "Transcription" });
    expect(original).toHaveFocus();

    await user.keyboard("{ArrowDown}");
    expect(transcription).toHaveFocus();
    await user.keyboard("{Enter}");

    expect(onSelect).toHaveBeenCalledWith("transcription");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("closes on Escape and restores trigger focus", async () => {
    const user = userEvent.setup();
    render(
      <ListboxMenu
        triggerLabel="Score"
        triggerAria="Playback source: Score"
        selectedId="score"
        options={[{ id: "score", label: "Score" }, { id: "original", label: "Original" }]}
        onSelect={() => {}}
      />,
    );

    const trigger = screen.getByRole("button", { name: "Playback source: Score" });
    trigger.focus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("option", { name: "Score" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
