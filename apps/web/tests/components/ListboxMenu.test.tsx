import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ListboxMenu from "@/components/ui/ListboxMenu";

function expectActiveOption(listbox: HTMLElement, option: HTMLElement) {
  expect(option.id).not.toBe("");
  expect(listbox).toHaveAttribute("aria-activedescendant", option.id);
}

describe("ListboxMenu", () => {
  it("opens on arrow keys, moves the active option, selects, and returns focus", async () => {
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
    await user.tab();
    expect(trigger).toHaveFocus();
    await user.keyboard("{ArrowDown}");

    const listbox = screen.getByRole("listbox");
    const original = screen.getByRole("option", { name: "Original" });
    const transcription = screen.getByRole("option", { name: "Transcription" });
    await waitFor(() => expect(listbox).toHaveFocus());
    await waitFor(() => expectActiveOption(listbox, original));

    await user.keyboard("{ArrowDown}");
    expectActiveOption(listbox, transcription);
    await user.keyboard("{Enter}");

    expect(onSelect).toHaveBeenCalledWith("transcription");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("skips disabled options in both keyboard directions", async () => {
    const user = userEvent.setup();
    render(
      <ListboxMenu
        triggerLabel="Original"
        triggerAria="Playback source: Original"
        selectedId="original"
        options={[
          { id: "original", label: "Original" },
          { id: "unavailable", label: "Unavailable", disabled: true },
          { id: "score", label: "Score" },
        ]}
        onSelect={() => {}}
      />,
    );

    const trigger = screen.getByRole("button", { name: "Playback source: Original" });
    await user.tab();
    expect(trigger).toHaveFocus();
    await user.keyboard("{ArrowDown}");

    const listbox = screen.getByRole("listbox");
    const original = screen.getByRole("option", { name: "Original" });
    const unavailable = screen.getByRole("option", { name: "Unavailable" });
    const score = screen.getByRole("option", { name: "Score" });
    expect(unavailable).toHaveAttribute("aria-disabled", "true");
    await waitFor(() => expect(listbox).toHaveFocus());
    await waitFor(() => expectActiveOption(listbox, original));

    await user.keyboard("{ArrowDown}");
    expectActiveOption(listbox, score);

    await user.keyboard("{ArrowUp}");
    expectActiveOption(listbox, original);
  });

  it("supports Home and End navigation", async () => {
    const user = userEvent.setup();
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
        onSelect={() => {}}
      />,
    );

    const trigger = screen.getByRole("button", { name: "Playback source: Original" });
    await user.tab();
    expect(trigger).toHaveFocus();
    await user.keyboard("{ArrowDown}");

    const listbox = screen.getByRole("listbox");
    const original = screen.getByRole("option", { name: "Original" });
    const score = screen.getByRole("option", { name: "Score" });
    await waitFor(() => expect(listbox).toHaveFocus());

    await user.keyboard("{End}");
    expectActiveOption(listbox, score);
    await user.keyboard("{Home}");
    expectActiveOption(listbox, original);
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
    await user.tab();
    expect(trigger).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    await waitFor(() => expect(screen.getByRole("listbox")).toHaveFocus());
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("closes on Tab and continues to the next focusable control", async () => {
    const user = userEvent.setup();
    render(
      <>
        <ListboxMenu
          triggerLabel="Original"
          triggerAria="Playback source: Original"
          selectedId="original"
          options={[{ id: "original", label: "Original" }, { id: "score", label: "Score" }]}
          onSelect={() => {}}
        />
        <button type="button">After source picker</button>
      </>,
    );

    const trigger = screen.getByRole("button", { name: "Playback source: Original" });
    await user.tab();
    expect(trigger).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    await waitFor(() => expect(screen.getByRole("listbox")).toHaveFocus());

    await user.tab();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "After source picker" })).toHaveFocus();
  });

  it("keeps outside controls interactive while open and dismisses on outside click", async () => {
    const user = userEvent.setup();
    const onOutsideClick = vi.fn();
    render(
      <>
        <ListboxMenu
          triggerLabel="Original"
          triggerAria="Playback source: Original"
          selectedId="original"
          options={[{ id: "original", label: "Original" }, { id: "score", label: "Score" }]}
          onSelect={() => {}}
        />
        <button type="button" onClick={onOutsideClick}>Representation tab stand-in</button>
      </>,
    );

    const trigger = screen.getByRole("button", { name: "Playback source: Original" });
    await user.tab();
    expect(trigger).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    await waitFor(() => expect(screen.getByRole("listbox")).toHaveFocus());

    const outsideControl = screen.getByRole("button", { name: "Representation tab stand-in" });
    await user.click(outsideControl);

    expect(onOutsideClick).toHaveBeenCalledOnce();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});
