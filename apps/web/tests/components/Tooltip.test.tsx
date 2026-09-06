import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import Tooltip from "@/components/ui/Tooltip";

describe("Tooltip", () => {
  it("exposes help on keyboard focus without changing the trigger name", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Play recording">
        <button type="button" aria-label="Play">Play</button>
      </Tooltip>,
    );

    const trigger = screen.getByRole("button", { name: "Play" });
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    await user.tab();

    const tooltip = await screen.findByRole("tooltip");
    expect(trigger).toHaveFocus();
    expect(trigger).toHaveAttribute("aria-describedby", tooltip.id);
    expect(trigger).not.toHaveAttribute("title");
    expect(tooltip).toHaveTextContent("Play recording");
  });

  it("supports the requested side placement", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Delete recording" placement="left">
        <button type="button" aria-label="Delete recording">Delete</button>
      </Tooltip>,
    );

    await user.tab();

    const tooltip = await screen.findByRole("tooltip");
    expect(tooltip).toHaveTextContent("Delete recording");
    expect(tooltip).toHaveAttribute("data-side", "left");
  });

  it("keeps hover help available for disabled native controls", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="A second playback source is required">
        <button type="button" disabled>Compare</button>
      </Tooltip>,
    );

    const trigger = screen.getByRole("button", { name: "Compare" });
    const hoverTarget = trigger.parentElement;
    expect(hoverTarget).toHaveAttribute("data-tooltip-disabled-trigger");

    await user.hover(hoverTarget!);

    expect(await screen.findByRole("tooltip")).toHaveTextContent("A second playback source is required");
    expect(trigger).toBeDisabled();
  });
});
